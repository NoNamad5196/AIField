"""
AIField 스케줄러.

두 가지 루프를 asyncio로 동시 실행한다:
  - 수집 루프: 주기적으로 collectors.fetch_all() → 즉시 알림 처리
  - 브리핑 루프: 지정 시각(09:00 / 21:00 KST)에 Perlica 브리핑 발송

알림 라우팅:
  - is_official=True  → Perlica 속보 → 스레드에 Qianyu 커뮤니티 반응
  - is_official=False → Qianyu 루머  → 스레드에 Perlica 검증
  - Level 3           → DB 저장 + 브리핑 버퍼 적재
  - Level 1~2         → DB 저장만 (알림 없음)
"""

import asyncio
from datetime import datetime, timezone, timedelta

from collectors import fetch_all
from scorer import NewsItem
from bot_qianyu import QianyuBot
from bot_perlica import PerlicaBot
from db.news_store import NewsStore
from llm import generate
from prompts.perlica_system import PERLICA_SYSTEM_PROMPT, briefing_user_prompt

KST = timezone(timedelta(hours=9))
SCAN_INTERVAL_SEC = 30 * 60      # 30분마다 수집
BRIEFING_HOURS_KST = (9, 21)     # 09:00, 21:00 KST
BRIEFING_MAX_ITEMS = 10
IMMEDIATE_ALERT_MIN_LEVEL = 4    # Level 4 이상 즉시 알림


class AIFieldScheduler:
    def __init__(self, qianyu: QianyuBot, perlica: PerlicaBot):
        self.qianyu = qianyu
        self.perlica = perlica
        self._store = NewsStore()         # SQLite 영구 저장 — 재시작 후에도 중복 방지
        self._briefing_buffer: list[NewsItem] = []

    async def run(self):
        """두 봇이 ready 상태인 상황에서 호출한다. 종료될 때까지 반환하지 않는다."""
        print(f"[scheduler] 시작 — 수집 주기: {SCAN_INTERVAL_SEC // 60}분, "
              f"브리핑: {BRIEFING_HOURS_KST[0]:02d}:00 / {BRIEFING_HOURS_KST[1]:02d}:00 KST")
        try:
            await asyncio.gather(
                self._scan_loop(),
                self._briefing_loop(),
            )
        finally:
            self._store.close()

    # ------------------------------------------------------------------
    # 수집 루프
    # ------------------------------------------------------------------

    async def _scan_loop(self):
        while True:
            await self._scan_once()
            await asyncio.sleep(SCAN_INTERVAL_SEC)

    async def _scan_once(self):
        now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
        print(f"[scheduler] 수집 시작 — {now_str}")
        try:
            items = await fetch_all()
        except Exception as e:
            print(f"[scheduler] fetch_all 오류: {e}")
            return

        new_items = self._save_new(items)
        stats = self._store.stats()
        print(f"[scheduler] {len(items)}개 수집 → 신규 {len(new_items)}개 "
              f"(DB 누계: {stats['total']}건, 미브리핑: {stats['unbriefed']}건)")

        immediate = [it for it in new_items if it.alert_level >= IMMEDIATE_ALERT_MIN_LEVEL]
        buffered  = [it for it in new_items if it.alert_level == 3]

        self._briefing_buffer.extend(buffered)

        for item in immediate:
            await self._post_immediate(item)
            await asyncio.sleep(1.5)

    def _save_new(self, items: list[NewsItem]) -> list[NewsItem]:
        """DB에 저장 성공한 항목(신규)만 반환한다."""
        return [it for it in items if self._store.save(it)]

    # ------------------------------------------------------------------
    # 즉시 알림 (Level 4 / 5)
    # ------------------------------------------------------------------

    async def _post_immediate(self, item: NewsItem):
        label = f"L{item.alert_level} {'공식' if item.is_official else '루머'}"
        print(f"[scheduler] 즉시 알림 [{label}] {item.title[:50]}")
        try:
            if item.is_official:
                thread_id = await self.perlica.post_breaking_news(item)
                await asyncio.sleep(1)
                await self.qianyu.post_community_reaction(thread_id, item)
            else:
                thread_id = await self.qianyu.post_rumor(item)
                await asyncio.sleep(1)
                await self.perlica.post_verification(thread_id, item)
        except Exception as e:
            print(f"[scheduler] 즉시 알림 실패: {e}")

    # ------------------------------------------------------------------
    # 브리핑 루프
    # ------------------------------------------------------------------

    async def _briefing_loop(self):
        while True:
            now = datetime.now(KST)
            next_at = _next_briefing_time(now)
            wait_sec = (next_at - now).total_seconds()
            print(f"[scheduler] 다음 브리핑: {next_at.strftime('%m/%d %H:%M KST')} "
                  f"({wait_sec / 3600:.1f}h 후)")
            await asyncio.sleep(wait_sec)
            await self._post_briefing()

    async def _post_briefing(self):
        # 버퍼가 비어 있으면 DB 미브리핑 항목으로 보완
        if not self._briefing_buffer:
            rows = self._store.get_unbriefed(min_level=3)
            if rows:
                self._briefing_buffer = [_row_to_news_item(r) for r in rows]

        if not self._briefing_buffer:
            print("[scheduler] 브리핑 항목 없음 — 생략")
            return

        now = datetime.now(KST)
        date_str = now.strftime("%Y-%m-%d")
        fallback = _format_briefing(self._briefing_buffer, now)
        content = await generate(
            PERLICA_SYSTEM_PROMPT,
            briefing_user_prompt(self._briefing_buffer, date_str),
            fallback=fallback,
        )
        try:
            await self.perlica.post_briefing(content)
            self._store.mark_briefed(self._briefing_buffer)
            print(f"[scheduler] 브리핑 발송 완료 ({len(self._briefing_buffer)}개 항목)")
            self._briefing_buffer.clear()
        except Exception as e:
            print(f"[scheduler] 브리핑 발송 실패: {e}")

    # ------------------------------------------------------------------
    # 슬래시 명령어용 공개 메서드
    # ------------------------------------------------------------------

    async def force_briefing(self, items: list[NewsItem] | None = None):
        """items 지정 시 버퍼를 교체하고 즉시 브리핑을 발송한다."""
        if items is not None:
            self._briefing_buffer = list(items)
        await self._post_briefing()

    async def scan_once(self):
        """슬래시 명령어에서 즉시 수집 한 사이클 실행용."""
        await self._scan_once()

    def get_status(self) -> dict:
        """슬래시 /status 명령어용 상태 정보를 반환한다."""
        stats = self._store.stats()
        now = datetime.now(KST)
        next_at = _next_briefing_time(now)
        wait_h = (next_at - now).total_seconds() / 3600
        return {
            "db": stats,
            "next_briefing": next_at.strftime("%m/%d %H:%M KST"),
            "next_briefing_in": f"{wait_h:.1f}h",
            "buffer_count": len(self._briefing_buffer),
        }


# ------------------------------------------------------------------
# 헬퍼 함수
# ------------------------------------------------------------------

def _next_briefing_time(now: datetime) -> datetime:
    for hour in BRIEFING_HOURS_KST:
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(
        hour=BRIEFING_HOURS_KST[0], minute=0, second=0, microsecond=0
    )


def _row_to_news_item(row: dict) -> NewsItem:
    """DB 행을 NewsItem으로 변환한다."""
    return NewsItem(
        title=row["title"],
        source=row.get("source", ""),
        url=row.get("url", ""),
        summary=row.get("summary", ""),
        is_official=bool(row.get("is_official", 0)),
        is_rumor=bool(row.get("is_rumor", 1)),
        alert_level=row.get("alert_level", 0),
        should_alert=bool(row.get("should_alert", 0)),
        singularity_impact=row.get("singularity_impact", 0),
        urgency=row.get("urgency", 0),
        reliability=row.get("reliability", 0),
        practicality=row.get("practicality", 0),
    )


def _format_briefing(items: list[NewsItem], now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d")
    official = [it for it in items if it.is_official]
    rumors   = [it for it in items if not it.is_official]

    lines = [
        f"**[AIField 일일 브리핑] {date_str}**",
        "",
        "관리자, 오늘 하루 정리할게.",
        "",
    ]

    if official:
        lines.append("**✅ 공식 발표**")
        for i, it in enumerate(official[:5], 1):
            lines.append(f"{i}. {it.title[:65]} (Level {it.alert_level})")
        lines.append("")

    if rumors:
        lines.append("**🔺 루머 / 커뮤니티**")
        for i, it in enumerate(rumors[:5], 1):
            lines.append(f"{i}. {it.title[:65]}")
        lines.append("")

    total = len(items)
    if total > BRIEFING_MAX_ITEMS:
        lines.append(f"... 외 {total - BRIEFING_MAX_ITEMS}건 더 있어.")
        lines.append("")

    lines.append(f"총 {total}건. 관리자, 너무 무리하지 말고 핵심만 먼저 보면 돼.")
    lines.append("")
    lines.append("*AI는 또 한 걸음 앞으로 나아갔어.*")
    return "\n".join(lines)
