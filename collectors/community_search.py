"""
공식 속보에 대한 Hacker News + Reddit 커뮤니티 반응 수집기.

fetch_reactions(item) → str
  속보 제목을 키워드로 HN과 Reddit을 동시 검색해
  community_summary 필드에 넣을 텍스트를 반환한다.
  결과가 없거나 오류 시 빈 문자열을 반환한다.
"""

import asyncio
import re

import aiohttp

from scorer import NewsItem

_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_REDDIT_SEARCH_URL = (
    "https://www.reddit.com"
    "/r/MachineLearning+LocalLLaMA+singularity/search.json"
)
_REDDIT_HEADERS = {
    "User-Agent": "AIField-Bot/1.0 (AI news aggregator; contact: bot@aifield.local)"
}
_TIMEOUT = aiohttp.ClientTimeout(total=8)


# ---------------------------------------------------------------------------
# 키워드 추출
# ---------------------------------------------------------------------------

def _extract_keyword(title: str) -> str:
    """
    제목에서 검색 키워드를 추출한다.
    - 영어 단어가 2개 이상이면 앞 3단어를 사용 (모델명·회사명 위주)
    - 영어 단어가 1개 이하면 제목 전체를 사용
    - 최대 60자 제한
    """
    english_words = re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", title)
    if len(english_words) >= 2:
        keyword = " ".join(english_words[:3])
    else:
        keyword = title
    return keyword[:60].strip()


# ---------------------------------------------------------------------------
# HN 검색
# ---------------------------------------------------------------------------

async def _fetch_hn(session: aiohttp.ClientSession, keyword: str) -> list[dict]:
    """HN Algolia search API로 관련 스토리 최대 5개를 반환한다."""
    try:
        params = {"query": keyword, "tags": "story", "hitsPerPage": 5}
        async with session.get(
            _HN_SEARCH_URL, params=params, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return [
            {
                "title": h.get("title", ""),
                "points": h.get("points") or 0,
                "num_comments": h.get("num_comments") or 0,
            }
            for h in data.get("hits", [])
            if h.get("title")
        ]
    except Exception as e:
        print(f"[community_search] HN 오류: {e}")
        return []


# ---------------------------------------------------------------------------
# Reddit 검색
# ---------------------------------------------------------------------------

async def _fetch_reddit(session: aiohttp.ClientSession, keyword: str) -> list[dict]:
    """Reddit public JSON API로 관련 포스트 최대 5개를 반환한다. 인증 불필요."""
    try:
        params = {
            "q": keyword,
            "sort": "relevance",
            "limit": 5,
            "restrict_sr": 1,
            "t": "week",
        }
        async with session.get(
            _REDDIT_SEARCH_URL,
            params=params,
            headers=_REDDIT_HEADERS,
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        children = data.get("data", {}).get("children", [])
        return [
            {
                "title": c["data"].get("title", ""),
                "score": c["data"].get("score") or 0,
                "num_comments": c["data"].get("num_comments") or 0,
                "subreddit": c["data"].get("subreddit", ""),
            }
            for c in children
            if c.get("data", {}).get("title")
        ]
    except Exception as e:
        print(f"[community_search] Reddit 오류: {e}")
        return []


# ---------------------------------------------------------------------------
# 결과 포맷
# ---------------------------------------------------------------------------

def _format_reactions(hn_hits: list[dict], reddit_hits: list[dict]) -> str:
    """HN + Reddit 결과를 Gemini 프롬프트용 텍스트로 포맷한다."""
    lines = []

    if hn_hits:
        lines.append("【Hacker News 반응】")
        for h in hn_hits[:3]:
            lines.append(
                f"- {h['title']} "
                f"(포인트: {h['points']}, 댓글: {h['num_comments']})"
            )

    if reddit_hits:
        lines.append("【Reddit 반응】")
        for r in reddit_hits[:3]:
            lines.append(
                f"- [{r['subreddit']}] {r['title']} "
                f"(투표: {r['score']}, 댓글: {r['num_comments']})"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

async def fetch_reactions(item: NewsItem) -> str:
    """
    공식 속보의 제목을 기준으로 HN + Reddit 커뮤니티 반응을 수집한다.
    결과가 없거나 오류 발생 시 빈 문자열("")을 반환한다.
    """
    keyword = _extract_keyword(item.title)
    if not keyword:
        return ""

    async with aiohttp.ClientSession() as session:
        hn_hits, reddit_hits = await asyncio.gather(
            _fetch_hn(session, keyword),
            _fetch_reddit(session, keyword),
        )

    if not hn_hits and not reddit_hits:
        print(f"[community_search] 반응 없음 — keyword={keyword!r}")
        return ""

    result = _format_reactions(hn_hits, reddit_hits)
    print(
        f"[community_search] 수집 완료 — "
        f"HN {len(hn_hits)}건, Reddit {len(reddit_hits)}건 (keyword={keyword!r})"
    )
    return result
