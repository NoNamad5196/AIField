import asyncio
import discord
import config
from scorer import NewsItem
from llm import generate
from prompts.qianyu_system import (
    QIANYU_SYSTEM_PROMPT,
    rumor_user_prompt,
    community_reaction_user_prompt,
)


class QianyuBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self._ready_event = asyncio.Event()

    async def on_ready(self):
        print(f"[Qianyu] 온라인: {self.user}")
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

    async def post_rumor(self, item: NewsItem) -> int:
        """루머/떡밥을 #aifield-live에 올리고 스레드 생성 후 thread_id 반환."""
        content = await generate(
            QIANYU_SYSTEM_PROMPT,
            rumor_user_prompt(item),
            fallback=_format_rumor(item),
        )
        channel = await self._get_channel(config.AIFIELD_LIVE_CHANNEL_ID)
        first = content[:2000]
        message = await channel.send(first)
        if len(content) > 2000:
            await asyncio.sleep(0.5)
            await self._safe_send(channel, content[2000:])
        await asyncio.sleep(0.5)
        thread = await message.create_thread(
            name=f"검증 | {item.title[:50]}",
            auto_archive_duration=1440,
        )
        return thread.id

    async def post_community_reaction(self, thread_id: int, item: NewsItem):
        """속보 스레드에 커뮤니티 반응 달기."""
        content = await generate(
            QIANYU_SYSTEM_PROMPT,
            community_reaction_user_prompt(item),
            fallback=_format_community_reaction(item),
        )
        thread = await self._get_channel(thread_id)
        await self._safe_send(thread, content)


def _format_rumor(item: NewsItem) -> str:
    rumor_tag = "⚠️ 루머" if item.is_rumor else "📌 정보"
    official_tag = "❌ 미확인" if not item.is_official else "✅ 공식"
    return (
        f"관리자, 이거 봐! 재밌는 거 하나 찾았어. 헤헤.\n\n"
        f"**{item.title}**\n"
        f"{item.summary}\n\n"
        f"📍 출처: {item.source}\n"
        f"{rumor_tag} | {official_tag}\n"
        f"⚡ 긴급도: {item.urgency}/5 | "
        f"🛡️ 신뢰도: {item.reliability}/5 | "
        f"🔧 실용성: {item.practicality}/5\n"
        f"📊 알림 레벨: Level {item.alert_level}\n\n"
        f"일단 내가 떡밥으로 잡아둘게. 펠리카한테 넘기면 제대로 정리해줄 거야.\n"
        f"*아직 한 걸음까진 아니어도, 발은 들썩인 것 같아.*"
    )


def _format_community_reaction(item: NewsItem) -> str:
    reaction = item.community_summary or "커뮤니티 반응 수집 중..."
    return (
        f"관리자, 커뮤니티 반응 들고 왔어!\n\n"
        f"**{item.title}** — 커뮤 분위기\n"
        f"{reaction}\n\n"
        f"그냥 지나치긴 아까운 한 걸음이야."
    )
