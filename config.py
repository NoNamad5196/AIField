import os
from dotenv import load_dotenv

load_dotenv()

QIANYU_BOT_TOKEN = os.getenv("QIANYU_BOT_TOKEN")
PERLICA_BOT_TOKEN = os.getenv("PERLICA_BOT_TOKEN")
AIFIELD_LIVE_CHANNEL_ID = int(os.getenv("AIFIELD_LIVE_CHANNEL_ID", "0"))
AIFIELD_BRIEFING_CHANNEL_ID = int(os.getenv("AIFIELD_BRIEFING_CHANNEL_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # 선택사항 — 없으면 하드코딩 폴백
AIFIELD_GUILD_ID: int | None = int(os.getenv("AIFIELD_GUILD_ID") or 0) or None  # 선택사항 — 설정 시 슬래시 명령어 즉시 적용

def _require_str(name: str, val) -> None:
    if not val:
        raise EnvironmentError(f"필수 환경변수 누락: {name} — .env 파일을 확인해줘.")

def _require_int(name: str, val: int) -> None:
    if val == 0:
        raise EnvironmentError(f"필수 환경변수 누락: {name} — .env 파일을 확인해줘.")

_require_str("QIANYU_BOT_TOKEN", QIANYU_BOT_TOKEN)
_require_str("PERLICA_BOT_TOKEN", PERLICA_BOT_TOKEN)
_require_int("AIFIELD_LIVE_CHANNEL_ID", AIFIELD_LIVE_CHANNEL_ID)
_require_int("AIFIELD_BRIEFING_CHANNEL_ID", AIFIELD_BRIEFING_CHANNEL_ID)
