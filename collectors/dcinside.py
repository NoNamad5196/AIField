"""
DC Inside 싱귤래리티 마이너 갤러리 수집기.
https://gall.dcinside.com/mgallery/board/lists/?id=thesingularity

수집 기준:
  - 말머리 정보/활용/자료/후기/유출/외신 → 추천 무관 수집
  - 말머리 일반 포함 전체 → 추천 10↑ 念글은 무조건 수집
"""

import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from scorer import NewsItem

_GALL_URL = "https://gall.dcinside.com/mgallery/board/lists/?id=thesingularity"
_POST_BASE = "https://gall.dcinside.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://gall.dcinside.com/",
}
_SKIP_TYPES = {"공지", "AD", "설문"}
_QUALITY_SUBJECTS = {"정보", "활용", "자료", "후기", "유출", "외신", "속보", "루머"}
_HOT_RECOMMEND = 10   # 念글 기준 추천수
_CONTENT_LIMIT = 600
_FETCH_SEMAPHORE = asyncio.Semaphore(3)

_URL_RE = re.compile(r"https?://\S+")


def _clean_content(raw: str) -> str:
    """URL 제거 + 공백 정리 후 의미 있는 텍스트만 반환."""
    text = _URL_RE.sub("", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_CONTENT_LIMIT] if len(text) > 15 else ""


async def _fetch_post_content(session: aiohttp.ClientSession, url: str) -> str:
    """개별 포스트 본문을 가져와 정리된 텍스트로 반환한다."""
    async with _FETCH_SEMAPHORE:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.select_one("div.write_div")
    if not content_div:
        return ""

    return _clean_content(content_div.get_text(separator=" ", strip=True))


async def fetch(limit: int = 30) -> list[NewsItem]:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(_GALL_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    print(f"[dcinside] HTTP {resp.status}")
                    return []
                html = await resp.text(encoding="utf-8", errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("tr.ub-content")

            items = []
            for row in rows[:limit]:
                try:
                    row_classes = row.get("class", [])
                    if "notice-cont" in row_classes:
                        continue
                    num_td = row.select_one("td.gall_num")
                    if num_td and num_td.get_text(strip=True) in _SKIP_TYPES:
                        continue

                    title_td = row.select_one("td.gall_tit")
                    if not title_td:
                        continue

                    a_tag = next(
                        (a for a in title_td.select("a") if "reply_num" not in a.get("class", [])),
                        None,
                    )
                    if not a_tag:
                        continue

                    title = a_tag.get_text(strip=True)
                    if not title:
                        continue

                    # 말머리
                    subject_td = row.select_one("td.gall_subject")
                    subject = subject_td.get_text(strip=True) if subject_td else ""

                    # 추천수
                    recommend = 0
                    rec_td = row.select_one("td.gall_recommend")
                    if rec_td:
                        try:
                            recommend = int(rec_td.get_text(strip=True))
                        except ValueError:
                            pass

                    # 수집 기준: 정보성 말머리 OR 念글(추천 10↑)
                    is_quality_subject = any(s in subject for s in _QUALITY_SUBJECTS)
                    is_hot = recommend >= _HOT_RECOMMEND

                    if not is_quality_subject and not is_hot:
                        continue

                    href = a_tag.get("href", "")
                    url = _POST_BASE + href if href.startswith("/") else href

                    items.append(NewsItem(
                        title=title,
                        source="DCInside 싱귤래리티 갤",
                        url=url,
                        is_official=False,
                        is_rumor=True,
                        reliability=3,
                        urgency=4 if is_hot else 3,
                    ))
                except Exception:
                    continue

            # 본문 병렬 fetch
            if items:
                contents = await asyncio.gather(
                    *[_fetch_post_content(session, it.url) for it in items],
                    return_exceptions=True,
                )
                for item, content in zip(items, contents):
                    if isinstance(content, str) and content:
                        item.summary = content

    except Exception as e:
        print(f"[dcinside] 요청 실패: {e}")
        return []

    return items
