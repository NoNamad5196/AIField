import asyncio
import discord
from discord import app_commands
import config
from scorer import NewsItem
from llm import generate
from prompts.perlica_system import (
    PERLICA_SYSTEM_PROMPT,
    breaking_news_user_prompt,
    verification_user_prompt,
)


class PerlicaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self._ready_event = asyncio.Event()
        self._scheduler = None
        self._synced = False
        self.tree = app_commands.CommandTree(self)
        self._setup_commands()

    def set_scheduler(self, scheduler) -> None:
        self._scheduler = scheduler

    async def on_ready(self):
        print(f"[Perlica] 온라인: {self.user}")
        if not self._synced:
            if config.AIFIELD_GUILD_ID:
                guild = discord.Object(id=config.AIFIELD_GUILD_ID)
                await self.tree.sync(guild=guild)
                print(f"[Perlica] 슬래시 명령어 동기화 완료 (guild {config.AIFIELD_GUILD_ID})")
            else:
                await self.tree.sync()
                print("[Perlica] 슬래시 명령어 전역 동기화 완료 (반영까지 최대 1시간)")
            self._synced = True
        self._ready_event.set()

    async def wait_ready(self):
        await self._ready_event.wait()

    async def _get_channel(self, channel_id: int):
        return self.get_channel(channel_id) or await self.fetch_channel(channel_id)

    async def _safe_send(self, channel, content: str):
        """Discord 2000자 제한 대응 — 초과 시 줄 단위로 분할 발송."""
        if len(content) <= 2000:
            await channel.send(content)
            return
        chunk, lines = "", content.splitlines(keepends=True)
        for line in lines:
            if len(chunk) + len(line) > 1900:
                await channel.send(chunk)
                await asyncio.sleep(0.5)
                chunk = line
            else:
                chunk += line
        if chunk:
            await channel.send(chunk)

    def _setup_commands(self):
        @self.tree.command(name="status", description="AIField 봇 상태 및 DB 통계 확인")
        async def cmd_status(interaction: discord.Interaction):
            if self._scheduler is None:
                await interaction.response.send_message("⚠️ 스케줄러 초기화 중...", ephemeral=True)
                return
            s = self._scheduler.get_status()
            db = s["db"]
            by_level = " | ".join(
                f"L{lvl}:{cnt}" for lvl, cnt in sorted(db["by_level"].items())
            ) or "없음"
            await interaction.response.send_message(
                f"**AIField 상태**\n"
                f"```\n"
                f"DB 총 수집  : {db['total']}건\n"
                f"미브리핑    : {db['unbriefed']}건\n"
                f"버퍼 대기   : {s['buffer_count']}건\n"
                f"레벨별      : {by_level}\n"
                f"다음 브리핑 : {s['next_briefing']} ({s['next_briefing_in']} 후)\n"
                f"```",
                ephemeral=True,
            )

        @self.tree.command(name="briefing-now", description="즉시 브리핑 발송 (브리핑 채널)")
        async def cmd_briefing_now(interaction: discord.Interaction):
            if self._scheduler is None:
                await interaction.response.send_message("⚠️ 스케줄러 초기화 중...", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            await self._scheduler.force_briefing()
            await interaction.followup.send("✅ 브리핑 발송 완료!", ephemeral=True)

        @self.tree.command(name="scan-now", description="즉시 수집 실행 (한 사이클)")
        async def cmd_scan_now(interaction: discord.Interaction):
            if self._scheduler is None:
                await interaction.response.send_message("⚠️ 스케줄러 초기화 중...", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            await self._scheduler.scan_once()
            await interaction.followup.send("✅ 수집 완료!", ephemeral=True)

    async def _safe_reply(self, original_msg, content: str):
        """원본 메시지에 답글. 2000자 초과 시 첫 청크만 reply, 나머지는 채널 전송."""
        if len(content) <= 2000:
            await original_msg.reply(content)
            return
        await original_msg.reply(content[:2000])
        await asyncio.sleep(0.5)
        await self._safe_send(original_msg.channel, content[2000:])

    async def post_breaking_news(self, item: NewsItem) -> int:
        """속보를 #aifield-live에 올리고 message_id 반환."""
        content = await generate(
            PERLICA_SYSTEM_PROMPT,
            breaking_news_user_prompt(item),
            fallback=_format_breaking_news(item),
        )
        channel = await self._get_channel(config.AIFIELD_LIVE_CHANNEL_ID)
        first = content[:2000]
        message = await channel.send(first)
        if len(content) > 2000:
            await asyncio.sleep(0.5)
            await self._safe_send(channel, content[2000:])
        return message.id

    async def post_verification(self, message_id: int, item: NewsItem):
        """진천우 루머에 답글로 검증 결과 달기."""
        content = await generate(
            PERLICA_SYSTEM_PROMPT,
            verification_user_prompt(item),
            fallback=_format_verification(item),
        )
        channel = await self._get_channel(config.AIFIELD_LIVE_CHANNEL_ID)
        original = await channel.fetch_message(message_id)
        await self._safe_reply(original, content)

    async def post_briefing(self, content: str):
        """#aifield-briefing에 브리핑 게시."""
        channel = await self._get_channel(config.AIFIELD_BRIEFING_CHANNEL_ID)
        await self._safe_send(channel, content)


def _format_breaking_news(item: NewsItem) -> str:
    official_tag = "✅ 공식 발표 확인" if item.is_official else "❌ 미확인"
    return (
        f"🚨 **속보**\n\n"
        f"관리자, 확인했어. 공식 출처 기준으로 정리할게.\n\n"
        f"**{item.title}**\n"
        f"{item.summary}\n\n"
        f"📍 출처: {item.source}\n"
        f"{official_tag}\n"
        f"🔺 특이점 영향도: {item.singularity_impact}/5 | "
        f"⚡ 긴급도: {item.urgency}/5\n"
        f"🛡️ 신뢰도: {item.reliability}/5 | "
        f"🔧 실용성: {item.practicality}/5\n"
        f"📊 알림 레벨: Level {item.alert_level}\n\n"
        f"*AI는 또 한 걸음 앞으로 나아갔어.*"
    )


def _format_verification(item: NewsItem) -> str:
    verdict = "공식 출처 확인 완료." if item.is_official else "아직 공식 발표는 확인되지 않았어."
    classification = "공식 발표" if item.is_official else "루머로 분류할게. 즉시 알림은 보류하고 추적하자."
    return (
        f"관리자, 확인했어.\n\n"
        f"**검증 결과: {item.title}**\n\n"
        f"공식 여부: {'✅ 공식' if item.is_official else '❌ 루머'}\n"
        f"신뢰도: {item.reliability}/5 | 긴급도: {item.urgency}/5\n\n"
        f"{verdict}\n"
        f"최종 판단: {classification}"
    )
