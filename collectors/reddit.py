"""
Reddit 수집기.

Reddit 공개 JSON API (인증 불필요)로 AI 관련 서브레딧의 최신 포스트를 가져온다.
"""

import asyncio
import aiohttp
from scorer import NewsItem

_SUBREDDITS = ["MachineLearning", "LocalLLaMA"]  # r/singularity는 DC 싱귤래리티 갤이 커버
_REDDIT_JSON = "https://www.reddit.com/r/{sub}/new.json"
_HEADERS = {"User-Agent": "AIField-Bot/1.0 (AI news aggregator)"}

# 광고/자기홍보성 글 필터
_SKIP_FLAIRS = {"self-promotion", "hiring", "job", "advertisement"}


def _build_summary(post: dict) -> str:
    text = (post.get("selftext") or "").strip()
    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    header = f"Score: {score} | Comments: {num_comments}"
    body = text[:300] if text else ""
    return f"{header}\n{body}".strip()


async def _fetch_subreddit(
    session: aiohttp.ClientSession, sub: str, limit: int
) -> list[NewsItem]:
    url = _REDDIT_JSON.format(sub=sub)
    async with session.get(
        url, params={"limit": limit}, timeout=aiohttp.ClientTimeout(total=10)
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    items = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})

        # 삭제된 글, 광고 플레어 스킵
        if p.get("removed_by_category") or p.get("is_self") and not p.get("selftext"):
            continue
        flair = (p.get("link_flair_text") or "").lower()
        if any(skip in flair for skip in _SKIP_FLAIRS):
            continue

        title = p.get("title", "").strip()
        if not title:
            continue

        score = p.get("score", 0)
        items.append(NewsItem(
            title=title,
            source=f"Reddit r/{sub}",
            url=f"https://reddit.com{p.get('permalink', '')}",
            summary=_build_summary(p),
            is_rumor=True,
            is_official=False,
            # 커뮤니티 반응이 뜨거우면 긴급도 반영
            urgency=3 if score >= 500 else 2,
        ))

    return items


async def fetch(limit: int = 15) -> list[NewsItem]:
    """r/MachineLearning, r/LocalLLaMA, r/singularity 최신 포스트를 반환한다."""
    async with aiohttp.ClientSession(headers=_HEADERS) as session:
        results = await asyncio.gather(
            *[_fetch_subreddit(session, sub, limit) for sub in _SUBREDDITS],
            return_exceptions=True,
        )

    items: list[NewsItem] = []
    for sub, result in zip(_SUBREDDITS, results):
        if isinstance(result, Exception):
            print(f"[reddit] r/{sub} 수집 실패: {result}")
            continue
        items.extend(result)

    return items
