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

    async def _safe_reply(self, original_msg, content: str):
        """원본 메시지에 답글. 2000자 초과 시 첫 청크만 reply, 나머지는 채널 전송."""
        if len(content) <= 2000:
            await original_msg.reply(content)
            return
        await original_msg.reply(content[:2000])
        await asyncio.sleep(0.5)
        await self._safe_send(original_msg.channel, content[2000:])

    async def post_rumor(self, item: NewsItem) -> int:
        """루머/떡밥을 #aifield-live에 올리고 message_id 반환."""
        content = await generate(
            QIANYU_SYSTEM_PROMPT,
            rumor_user_prompt(item),
            fallback=_format_rumor(item),
        )
        # DCInside 글: 링크를 Gemini에 맡기지 않고 코드에서 직접 붙임
        is_dcinside = "특이점" in item.source or "dcinside" in item.source.lower()
        if is_dcinside and item.url and item.url not in content:
            content = content.rstrip() + f"\n🔗 {item.url}"

        channel = await self._get_channel(config.AIFIELD_LIVE_CHANNEL_ID)
        first = content[:2000]
        message = await channel.send(first)
        if len(content) > 2000:
            await asyncio.sleep(0.5)
            await self._safe_send(channel, content[2000:])
        return message.id

    async def post_community_reaction(self, message_id: int, item: NewsItem):
        """펠리카 속보에 답글로 커뮤니티 반응 달기."""
        content = await generate(
            QIANYU_SYSTEM_PROMPT,
            community_reaction_user_prompt(item),
            fallback=_format_community_reaction(item),
        )
        channel = await self._get_channel(config.AIFIELD_LIVE_CHANNEL_ID)
        original = await channel.fetch_message(message_id)
        await self._safe_reply(original, content)


def _format_rumor(item: NewsItem) -> str:
    summary_short = (item.summary or "")[:200].strip()
    official_str = "공식" if item.is_official else "미확인"
    return (
        f"관리자, 이거 봐! 재밌는 거 하나 찾았어. 헤헤.\n\n"
        f"**{item.title}**\n\n"
        f"{summary_short}\n\n"
        f"출처: {item.source} | {official_str} | "
        f"신뢰 {item.reliability} | 긴급 {item.urgency} | 실용 {item.practicality}\n"
        f"아직 한 걸음까진 아니어도, 발은 들썩인 것 같아."
    )


def _format_community_reaction(item: NewsItem) -> str:
    if item.community_summary:
        reaction = item.community_summary
    else:
        reaction = f"'{item.title[:40]}' 관련 커뮤니티 반응은 아직 못 찾았어."
    return (
        f"관리자, 커뮤니티 반응 들고 왔어!\n\n"
        f"**{item.title}**\n"
        f"{reaction}\n\n"
        f"그냥 지나치긴 아까운 한 걸음이야."
    )
