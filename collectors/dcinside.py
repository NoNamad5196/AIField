"""
DC Inside 싱귤래리티 마이너 갤러리 수집기.
https://gall.dcinside.com/mgallery/board/lists/?id=thesingularity
"""

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
# 허용 말머리 — 정보/활용/루머 계열만 수집
_ALLOWED_SUBJECTS = {"정보", "활용", "유출", "루머", "외신", "속보"}


async def fetch(limit: int = 30) -> list[NewsItem]:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(_GALL_URL, timeout=timeout) as resp:
                if resp.status != 200:
                    print(f"[dcinside] HTTP {resp.status}")
                    return []
                html = await resp.text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[dcinside] 요청 실패: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.ub-content")

    items = []
    for row in rows[:limit]:
        try:
            # 공지/AD 행 건너뜀 (클래스 또는 숫자 컬럼 텍스트로 판단)
            row_classes = row.get("class", [])
            if "notice-cont" in row_classes:
                continue
            num_td = row.select_one("td.gall_num")
            if num_td and num_td.get_text(strip=True) in _SKIP_TYPES:
                continue

            title_td = row.select_one("td.gall_tit")
            if not title_td:
                continue

            # 댓글수 링크(.reply_num) 제외하고 첫 번째 a 태그가 제목
            a_tag = next(
                (a for a in title_td.select("a") if "reply_num" not in a.get("class", [])),
                None,
            )
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            if not title:
                continue

            # 말머리(분류 태그) 파싱 — em 태그에서 추출
            subject = None
            for em in title_td.select("em"):
                text = em.get_text(strip=True)
                if text:
                    subject = text
                    break

            # 허용 말머리 없으면 스킵 (잡담/질문/유머 등 제외)
            if not subject or subject not in _ALLOWED_SUBJECTS:
                continue

            href = a_tag.get("href", "")
            url = _POST_BASE + href if href.startswith("/") else href

            # 추천수 파싱 — 念글(추천 5↑) 은 urgency=4(즉시), 나머지는 urgency=3(브리핑)
            recommend = 0
            rec_td = row.select_one("td.gall_recommend")
            if rec_td:
                try:
                    recommend = int(rec_td.get_text(strip=True))
                except ValueError:
                    pass

            items.append(NewsItem(
                title=title,
                source="DCInside 싱귤래리티 갤",
                url=url,
                is_official=False,
                is_rumor=True,
                reliability=3,  # 전용 AI 갤러리 — 일반 커뮤니티(2)보다 한 단계 위
                urgency=4 if recommend >= 5 else 3,  # 念글=즉시, 일반=브리핑
            ))
        except Exception:
            continue

    return items
