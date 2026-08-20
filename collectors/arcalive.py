"""
아카라이브 'AI 채팅 채널' 수집기.
https://arca.live/b/characterai

이 채널은 캐릭터 AI(NovelAI, Character.AI 등) 롤플레이/채팅 커뮤니티라
대부분 글이 잡담·롤플레이 스크린샷이라 AI 뉴스 봇 목적에 맞지 않는다.
'뉴스' 말머리(쿼리 파라미터상 실제 값은 "뉴스2")로 태그된 글만 수집해서 노이즈를 걸러낸다.

아카라이브는 Cloudflare 뒤에 있고 aiohttp의 TLS 핸드셰이크 지문을 봇으로 감지해
차단한다 (같은 헤더로도 urllib은 통과, aiohttp는 403). 그래서 HTTP 요청은
urllib을 스레드풀에서 돌려서 처리한다.
"""

import asyncio
import functools
import html as _html
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from scorer import NewsItem

_CHANNEL = "characterai"
_LIST_URL = f"https://arca.live/b/{_CHANNEL}"
_NEWS_CATEGORY = "뉴스2"  # 채널 UI 표시상 "뉴스"지만 실제 쿼리 파라미터 값은 "뉴스2"
_POST_BASE = "https://arca.live"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://arca.live/",
}
_HOT_RATE = 20  # 추천수 기준 긴급도 상향
_CONTENT_LIMIT = 1200
_FETCH_SEMAPHORE = asyncio.Semaphore(3)

_URL_RE = re.compile(r"https?://\S+")


def _blocking_get(url: str, timeout: int = 10) -> str:
    """동기 urllib GET. 실패하면 빈 문자열 반환."""
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return ""
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


async def _fetch_url(url: str, timeout: int = 10) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(_blocking_get, url, timeout))


def _clean_content(raw: str) -> str:
    """HTML 엔티티 언스케이프 + URL 제거 + 공백 정리."""
    text = _html.unescape(raw)
    text = _URL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_CONTENT_LIMIT] if len(text) > 20 else ""


async def _fetch_post_content(url: str) -> str:
    """개별 게시물 본문을 가져와 정리된 텍스트로 반환한다."""
    async with _FETCH_SEMAPHORE:
        html = await _fetch_url(url, timeout=8)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    body_div = soup.select_one("div.article-body .article-content") or soup.select_one("div.article-body")
    if not body_div:
        return ""

    raw_text = body_div.get_text(separator=" ", strip=True)
    return _clean_content(raw_text)


async def fetch_comments(post_url: str, limit: int = 20) -> str:
    """
    게시물 URL에서 실제 댓글을 가져와 '닉네임: 내용' 형식 텍스트로 반환한다.
    DCInside와 달리 별도 비공개 API/보안 토큰이 필요 없고, 게시물 페이지 HTML에
    댓글이 그대로 렌더링되어 있어 페이지 하나만 fetch하면 된다.
    실패하거나 댓글이 없으면 빈 문자열 반환.
    """
    html = await _fetch_url(post_url, timeout=10)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    comment_area = soup.select_one("div.article-comment")
    if not comment_area:
        return ""

    lines = []
    for comment_item in comment_area.select("div.comment-item"):
        name_tag = comment_item.select_one(".user-info")
        name = name_tag.get_text(strip=True) if name_tag else "익명"

        text_tag = comment_item.select_one(".message .text")
        if not text_tag:
            continue
        text = _html.unescape(text_tag.get_text(separator=" ", strip=True))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        lines.append(f"- {name}: {text}")
        if len(lines) >= limit:
            break

    return "\n".join(lines)


async def fetch(limit: int = 30) -> list[NewsItem]:
    try:
        query = urllib.parse.urlencode({"category": _NEWS_CATEGORY})
        html = await _fetch_url(f"{_LIST_URL}?{query}")
        if not html:
            print("[arcalive] 목록 페이지 요청 실패")
            return []

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("a.vrow.column")

        items = []
        for row in rows[:limit]:
            try:
                if "notice" in row.get("class", []):
                    continue

                title_span = row.select_one("span.title")
                if not title_span:
                    continue
                title = title_span.get_text(strip=True)
                if not title:
                    continue

                href = row.get("href", "")
                if not href:
                    continue
                url = href if href.startswith("http") else _POST_BASE + href
                url = url.split("?")[0]

                rate = 0
                rate_span = row.select_one("span.col-rate")
                if rate_span:
                    try:
                        rate = int(rate_span.get_text(strip=True))
                    except ValueError:
                        pass

                items.append(NewsItem(
                    title=title,
                    source="Arca Live AI 채팅 채널",
                    url=url,
                    is_official=False,
                    is_rumor=True,
                    reliability=3,
                    urgency=4 if rate >= _HOT_RATE else 3,
                ))
            except Exception:
                continue

        # 본문 병렬 fetch
        if items:
            contents = await asyncio.gather(
                *[_fetch_post_content(it.url) for it in items],
                return_exceptions=True,
            )
            for item, content in zip(items, contents):
                if isinstance(content, str) and content:
                    item.summary = content

    except Exception as e:
        print(f"[arcalive] 요청 실패: {e}")
        return []

    # 본문 수집 실패 또는 내용 빈약한 항목 제외 (최소 50자 이상)
    return [it for it in items if it.summary and len(it.summary) >= 50]
