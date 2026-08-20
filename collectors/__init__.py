"""
AIField 수집기 패키지.

각 수집기는 async fetch() -> list[NewsItem] 인터페이스를 따른다.
점수(신뢰도 등)는 수집기 단계에서 0으로 두고, score()가 자동 추론한다.
수집기가 더 정확한 점수를 알면 직접 설정해도 된다 — score()는 0인 항목만 덮어씀.
"""

import asyncio
from scorer import NewsItem, score

from collectors import huggingface, dcinside, rss, anthropic, arcalive  # noqa: F401 (arcalive는 아래 참고)


async def fetch_all() -> list[NewsItem]:
    """모든 수집기를 동시에 실행하고 scored NewsItem 목록을 반환한다."""
    results = await asyncio.gather(
        rss.fetch(),
        huggingface.fetch(),
        dcinside.fetch(),
        anthropic.fetch(),
        # arcalive.fetch(),  # 운영 서버(오라클 클라우드) IP가 Cloudflare에 차단당해 비활성화.
        #                    # 프록시 등 우회 방법 마련되면 이 줄만 다시 켜면 됨.
        return_exceptions=True,
    )

    items: list[NewsItem] = []
    names = ["RSS(공식)", "HuggingFace", "DCInside", "Anthropic"]
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            print(f"[collectors] {name} 수집 실패: {result}")
            continue
        for item in result:
            items.append(score(item))

    return items
