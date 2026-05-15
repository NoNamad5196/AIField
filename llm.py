"""
Gemini 2.0 Flash 비동기 래퍼.

GEMINI_API_KEY가 없으면 즉시 fallback을 반환하므로 키 없이도 봇이 동작한다.
Semaphore(1) + sleep(4.1s)로 무료 티어 15 RPM 제한을 준수한다.
"""

import asyncio
import config

_MODEL = "gemini-2.0-flash"
_semaphore = asyncio.Semaphore(1)
_REQ_INTERVAL = 4.1  # 60 / 15 RPM = 4초, 여유분 포함

_client = None
if config.GEMINI_API_KEY:
    try:
        from google import genai
        from google.genai import types as _types
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    except ImportError:
        print("[llm] google-genai 미설치 — pip install google-genai 후 재시작")


async def generate(system_prompt: str, user_prompt: str, fallback: str = "") -> str:
    """Gemini로 텍스트를 생성한다. 키 없음/오류 시 fallback을 반환한다.

    429 rate limit 시 최대 2회 재시도 (대기 12초 → 20초).
    그 외 오류는 즉시 fallback 반환.
    """
    if _client is None:
        return fallback

    from google.genai import types

    async with _semaphore:
        for attempt in range(3):
            try:
                response = await _client.aio.models.generate_content(
                    model=_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.8,
                        max_output_tokens=800,
                    ),
                    contents=user_prompt,
                )
                await asyncio.sleep(_REQ_INTERVAL)
                text = response.text
                return text.strip() if text else fallback

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "quota" in err_str.lower()

                if is_rate_limit and attempt < 2:
                    wait = 12.0 + attempt * 8.0  # 1차: 12초, 2차: 20초
                    print(f"[llm] 429 rate limit — {wait:.0f}초 후 재시도 ({attempt + 1}/2)")
                    await asyncio.sleep(wait)
                    continue

                print(f"[llm] 오류 (attempt {attempt + 1}): {e}")
                await asyncio.sleep(_REQ_INTERVAL)  # 오류 후에도 간격 유지
                return fallback

    return fallback
