"""
GitHub 트렌딩 AI 프로젝트 수집기.

GitHub REST Search API (비인증 60req/h)로 최근 급성장 AI 레포지토리를 가져온다.
GITHUB_TOKEN 환경변수가 있으면 5000req/h로 늘어난다.

GitHub Search API는 topic: 간 OR을 지원하지 않으므로 topic별로 검색 후 합산한다.
"""

import os
import asyncio
import aiohttp
from scorer import NewsItem

_SEARCH_API = "https://api.github.com/search/repositories"
_AI_TOPICS = ["llm", "generative-ai", "large-language-model", "machine-learning"]


def _build_summary(repo: dict) -> str:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    lang = repo.get("language") or "Unknown"
    desc = (repo.get("description") or "").strip()
    return f"Stars: {stars:,} | Forks: {forks:,} | Language: {lang}\n{desc}"


def _make_item(repo: dict) -> NewsItem:
    stars = repo.get("stargazers_count", 0)
    return NewsItem(
        title=f"[GitHub] {repo.get('full_name', '')}",
        source="GitHub Trending",
        url=repo.get("html_url", ""),
        summary=_build_summary(repo),
        is_rumor=False,
        is_official=False,
        singularity_impact=4 if stars >= 5000 else 3,
        urgency=2,
        practicality=5,
    )


async def _search_topic(
    session: aiohttp.ClientSession, headers: dict, topic: str, per_page: int
) -> list[dict]:
    params = {
        "q": f"topic:{topic} created:>2024-01-01",
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    }
    async with session.get(
        _SEARCH_API, params=params, headers=headers,
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        if resp.status == 403:
            print(f"[github] rate limit 도달. GITHUB_TOKEN 설정을 권장함.")
            return []
        resp.raise_for_status()
        data = await resp.json()
    return data.get("items", [])


async def fetch(limit: int = 15) -> list[NewsItem]:
    """AI 관련 GitHub 레포지토리 중 최근 생성 + 스타 수 상위를 반환한다."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    per_topic = max(5, limit // len(_AI_TOPICS))

    async with aiohttp.ClientSession() as session:
        # GitHub Search API 비인증 레이트 리밋: 10req/min → 순차 실행
        results = []
        for topic in _AI_TOPICS:
            repos = await _search_topic(session, headers, topic, per_topic)
            results.extend(repos)
            await asyncio.sleep(0.5)  # 레이트 리밋 여유

    # 중복 URL 제거 후 스타 순 정렬
    seen: set[str] = set()
    unique = []
    for repo in sorted(results, key=lambda r: r.get("stargazers_count", 0), reverse=True):
        url = repo.get("html_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(repo)

    return [_make_item(r) for r in unique[:limit]]
