"""
공식 속보 커뮤니티 반응 수집 + 루머 검증 검색.

Gemini 2.5-flash의 내장 Google Search 툴을 사용한다.
별도 API 키 불필요 — llm.py의 봇별 클라이언트/세마포어/재시도 로직을 그대로 재사용한다
(동시 지연 작업이 겹쳐도 RPM을 넘기지 않도록).
"""

from llm import generate
from scorer import NewsItem

_SEARCH_SYSTEM_PROMPT = (
    "너는 검색 결과를 정리해서 전달하는 리서치 도우미다. "
    "실제로 검색해서 찾은 사실만 근거로 답하고, 근거 없는 내용은 추측해서 채우지 않는다. "
    "찾은 내용이 있으면 날짜, 숫자, 매체/작성자명 등 구체적인 사실을 최대한 포함해서 답한다."
)


async def fetch_reactions(item: NewsItem) -> str:
    """
    공식 속보에 대한 커뮤니티 반응을 Google Search로 수집한다.
    진천우 스레드 답글용 텍스트를 반환한다.
    결과 없거나 오류 시 빈 문자열 반환.
    """
    context = f"\n\n참고할 원문 요약:\n{item.summary}" if item.summary else ""
    return await _search(
        bot="qianyu",
        query=f"{item.title} AI community reaction developer response",
        task=(
            "이 AI 뉴스에 대한 개발자/AI 커뮤니티(Reddit, Hacker News, X/Twitter 등)의 "
            "실제 반응을 검색해서 한국어로 4~6줄로 정리해줘. "
            "누가 어떤 의견을 냈는지, 우려나 기대 포인트가 뭔지 구체적으로 담을 것. "
            "반응을 전혀 못 찾으면 빈 문자열만 반환해."
        ) + context,
    )


async def search_for_verification(item: NewsItem) -> str:
    """
    루머/커뮤니티 글에 대한 펠리카 검증용 — Google Search로 관련 정보를 찾는다.
    검증 컨텍스트 텍스트를 반환한다. 결과 없으면 빈 문자열 반환.
    """
    # 커뮤니티 글 제목은 맥락 없는 슬랭인 경우가 많으므로, 본문 내용을 검색 근거로 함께 전달한다.
    context = (
        f"\n\n원문 내용(제목만으로는 검색이 부정확할 수 있으니 이 내용을 기준으로 검색할 것):\n{item.summary}"
        if item.summary else ""
    )
    return await _search(
        bot="perlica",
        query=f"{item.title} {item.source}",
        task=(
            "이 내용에 대해 지금까지 나온 반응, 후속 정보, 또는 사실 확인이 가능한 "
            "공식 출처나 관련 뉴스를 검색해서 한국어로 4~6줄로 정리해줘. "
            "가능하면 출처명, 날짜, 구체적 수치 등을 포함할 것. "
            "관련 정보를 전혀 못 찾으면 빈 문자열만 반환해."
        ) + context,
    )


async def _search(bot: str, query: str, task: str) -> str:
    """Gemini Google Search 툴로 검색하고 결과를 반환한다."""
    from google.genai import types

    text = await generate(
        _SEARCH_SYSTEM_PROMPT,
        f"다음 주제로 검색해줘: {query}\n\n{task}",
        fallback="",
        bot=bot,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )
    if text and len(text) > 10:
        print(f"[community_search] 검색 완료 — {query[:40]!r}")
        return text
    return ""
