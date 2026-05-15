"""
Gemini 2.0 Flash 비동기 래퍼.

진천우(qianyu)와 펠리카(perlica)가 각자 독립된 클라이언트/세마포어를 사용한다.
키가 없으면 즉시 fallback을 반환하므로 키 없이도 봇이 동작한다.
Semaphore(1) + sleep(4.1s)로 무료 티어 15 RPM 제한을 봇별로 준수한다.
"""

import asyncio
import config

_MODEL = "gemini-2.0-flash"
_REQ_INTERVAL = 4.1  # 60 / 15 RPM = 4초, 여유분 포함

# 봇별 클라이언트 & 세마포어
_clients:    dict[str, object] = {}
_semaphores: dict[str, asyncio.Semaphore] = {}


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
) -> str:
    """Gemini로 텍스트를 생성한다. 키 없음/오류 시 fallback을 반환한다.

    bot: "qianyu" 또는 "perlica" — 각자 독립된 키/세마포어/쿼터 사용.
    429 rate limit 시 최대 2회 재시도 (대기 12초 → 20초).
    그 외 오류는 즉시 fallback 반환.
    """
    client    = _clients.get(bot)
    semaphore = _semaphores.get(bot)
    if client is None:
        return fallback

    from google.genai import types

    async with semaphore:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
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
                    print(f"[llm:{bot}] 429 rate limit — {wait:.0f}초 후 재시도 ({attempt + 1}/2)")
                    await asyncio.sleep(wait)
                    continue

                print(f"[llm:{bot}] 오류 (attempt {attempt + 1}): {e}")
                await asyncio.sleep(_REQ_INTERVAL)
                return fallback

    return fallback
