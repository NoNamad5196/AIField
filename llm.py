"""
Gemini 2.5 Flash 비동기 래퍼.

진천우(qianyu)와 펠리카(perlica)가 각자 독립된 클라이언트/세마포어를 사용한다.
키가 없으면 즉시 fallback을 반환하므로 키 없이도 봇이 동작한다.
Semaphore(1) + sleep(7s)로 무료 티어 10 RPM 제한을 봇별로 준수한다.
"""

import asyncio
import config

_MODEL = "gemini-2.5-flash"
_REQ_INTERVAL = 7.0  # 60 / 10 RPM = 6초, 여유분 포함 (2.5-flash free tier: 10 RPM)

# 봇별 클라이언트 & 세마포어
_clients:    dict[str, object] = {}
_semaphores: dict[str, asyncio.Semaphore] = {}

# fallback 사용 시 왜 AI 생성 대신 템플릿이 나왔는지 관리자가 바로 알 수 있게 덧붙이는 안내문.
# 봇 말투(진천우: 밝은 반말 / 펠리카: 차분한 반말)를 유지한 채로 붙인다.
_FALLBACK_NOTE = {
    "qianyu":  "_(참고: {reason} 때문에 이번엔 AI 대신 간단 버전으로 대체했어!)_",
    "perlica": "_(참고: {reason} 때문에 이번엔 AI 생성 대신 간이 메시지로 대체했어.)_",
}
_REASON_DAILY_QUOTA = "일일 AI 쿼터 초과"
_REASON_RATE_LIMIT  = "AI 요청량 제한(RPM) 초과"
_REASON_EMPTY       = "AI 응답 생성 실패"
_REASON_ERROR       = "일시적 오류"


def _with_fallback_note(fallback: str, bot: str, reason: str) -> str:
    if not fallback:
        return fallback
    note = _FALLBACK_NOTE.get(bot, _FALLBACK_NOTE["perlica"]).format(reason=reason)
    return fallback.rstrip() + "\n\n" + note


def _init_client(name: str, api_key: str | None) -> None:
    if not api_key:
        return
    try:
        from google import genai
        _clients[name]    = genai.Client(api_key=api_key)
        _semaphores[name] = asyncio.Semaphore(1)
    except ImportError:
        print("[llm] google-genai 미설치 — pip install google-genai 후 재시작")


_init_client("qianyu",  config.GEMINI_API_KEY_QIANYU)
_init_client("perlica", config.GEMINI_API_KEY_PERLICA)


async def generate(
    system_prompt: str,
    user_prompt: str,
    fallback: str = "",
    *,
    bot: str = "perlica",
    tools: list | None = None,
    temperature: float = 0.8,
) -> str:
    """Gemini로 텍스트를 생성한다. 키 없음/오류 시 fallback을 반환한다.

    bot: "qianyu" 또는 "perlica" — 각자 독립된 키/세마포어/쿼터 사용.
    tools: 예) [types.Tool(google_search=types.GoogleSearch())] — 검색 등 내장 툴 사용 시.
    429 rate limit 시 최대 2회 재시도 (대기 12초 → 20초).
    그 외 오류는 즉시 fallback 반환.
    """
    client    = _clients.get(bot)
    semaphore = _semaphores.get(bot)
    if client is None:
        # 진천우/펠리카 둘 다 키가 설정돼 있는 게 정상 운영 상태라, 클라이언트가 없는 경우도
        # 실질적으론 쿼터 문제(예: 초기화 실패)로 보는 게 더 현실적인 안내다.
        return _with_fallback_note(fallback, bot, _REASON_DAILY_QUOTA)

    from google.genai import types

    async with semaphore:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        max_output_tokens=2000,
                        thinking_config=types.ThinkingConfig(thinking_budget=512),
                        tools=tools,
                    ),
                    contents=user_prompt,
                )
                await asyncio.sleep(_REQ_INTERVAL)
                text = response.text
                if text:
                    return text.strip()
                return _with_fallback_note(fallback, bot, _REASON_EMPTY)

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "quota" in err_str.lower()
                # 일일 쿼터(PerDay) 초과는 몇 분 기다려도 안 풀리므로 재시도 없이 바로 fallback
                is_daily_quota = "PerDay" in err_str

                if is_rate_limit and not is_daily_quota and attempt < 2:
                    wait = 65.0 + attempt * 60.0  # 1차: 65초, 2차: 125초 (RPM 윈도우 완전 초기화)
                    print(f"[llm:{bot}] 429 rate limit — {wait:.0f}초 후 재시도 ({attempt + 1}/2)")
                    await asyncio.sleep(wait)
                    continue

                if is_daily_quota:
                    print(f"[llm:{bot}] 일일 쿼터 초과 — 재시도 없이 fallback 사용")
                    reason = _REASON_DAILY_QUOTA
                elif is_rate_limit:
                    print(f"[llm:{bot}] 429 rate limit 재시도 소진 — fallback 사용")
                    reason = _REASON_RATE_LIMIT
                else:
                    print(f"[llm:{bot}] 오류 (attempt {attempt + 1}): {e}")
                    reason = _REASON_ERROR
                await asyncio.sleep(_REQ_INTERVAL)
                return _with_fallback_note(fallback, bot, reason)

    return _with_fallback_note(fallback, bot, _REASON_ERROR)
