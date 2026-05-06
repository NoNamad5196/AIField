"""
HuggingFace 수집기.

HuggingFace Hub API (인증 불필요)로 급상승 / 신규 모델을 가져온다.
"""

import asyncio
import aiohttp
from scorer import NewsItem

_HF_API = "https://huggingface.co/api/models"

# 텍스트/코드/멀티모달 관련 파이프라인만 수집
_TARGET_PIPELINES = {
    "text-generation",
    "text2text-generation",
    "question-answering",
    "summarization",
    "translation",
    "image-to-text",
    "text-to-image",
    "visual-question-answering",
    "code-completion",
}


def _build_summary(model: dict) -> str:
    likes = model.get("likes", 0)
    downloads = model.get("downloads", 0)
    pipeline = model.get("pipeline_tag", "unknown")
    tags = ", ".join((model.get("tags") or [])[:5])
    return f"Pipeline: {pipeline} | Likes: {likes} | Downloads: {downloads}\nTags: {tags}"


def _make_item(model: dict, label: str) -> NewsItem:
    model_id = model.get("modelId") or model.get("id", "")
    pipeline = model.get("pipeline_tag", "")
    is_gated = model.get("gated", False)
    likes = model.get("likes", 0)

    return NewsItem(
        title=f"[HuggingFace {label}] {model_id}",
        source="huggingface.co",
        url=f"https://huggingface.co/{model_id}",
        summary=_build_summary(model),
        is_rumor=False,
        is_official=True,
        # 좋아요 수 많으면 영향도/긴급도 높임
        singularity_impact=4 if likes >= 1000 else 3,
        urgency=3 if likes >= 500 else 2,
        practicality=3 if is_gated else 5,  # 게이티드 모델은 접근 제한 있음
    )


async def _fetch_trending(session: aiohttp.ClientSession, limit: int) -> list[NewsItem]:
    params = {"sort": "trendingScore", "direction": -1, "limit": limit}
    async with session.get(_HF_API, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        models = await resp.json()

    return [
        _make_item(m, "급상승")
        for m in models
        if not _TARGET_PIPELINES or m.get("pipeline_tag") in _TARGET_PIPELINES
    ]


async def _fetch_newest(session: aiohttp.ClientSession, limit: int) -> list[NewsItem]:
    params = {"sort": "lastModified", "direction": -1, "limit": limit}
    async with session.get(_HF_API, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        models = await resp.json()

    return [
        _make_item(m, "신규")
        for m in models
        if m.get("pipeline_tag") in _TARGET_PIPELINES
    ]


async def fetch(limit: int = 15) -> list[NewsItem]:
    """HuggingFace 급상승 + 신규 모델을 합쳐서 반환한다."""
    async with aiohttp.ClientSession() as session:
        trending, newest = await asyncio.gather(
            _fetch_trending(session, limit),
            _fetch_newest(session, limit),
        )

    # 중복 URL 제거
    seen: set[str] = set()
    result = []
    for item in trending + newest:
        if item.url not in seen:
            seen.add(item.url)
            result.append(item)

    return result
