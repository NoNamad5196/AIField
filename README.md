# AIField 🛰️

AI 관련 공식 발표, 논문, 오픈소스 모델, 커뮤니티 떡밥을 자동 수집·분류해서 Discord로 알려주는 AI 뉴스 속보봇 시스템.

---

## 봇 구성

### AIField-진천우 (Rumor Radar)
커뮤니티 떡밥, 루머, 신규 모델, Hugging Face 급상승 모델을 빠르게 물어오는 레이더 봇.
> "관리자, 이거 봐! 재밌는 거 하나 찾았어. 헤헤."

### AIField-펠리카 (Briefing Agent)
공식 발표 검증, 논문 요약, 루머 분류, 하루 브리핑 작성을 담당하는 브리핑 봇.
> "관리자, 확인했어. 공식 출처 기준으로 정리할게."

---

## 동작 방식

```
루머/떡밥 발견 시
  진천우 → #aifield-live 포스팅
    └─ 펠리카가 답글로 검증 결과

공식 속보 발견 시
  펠리카 → #aifield-live 포스팅
    └─ 진천우가 답글로 커뮤니티 반응

정기 브리핑
  펠리카 → #aifield-briefing (09:00 / 21:00 KST)
```

---

## 수집 소스

| 소스 | 종류 | 신뢰도 |
|------|------|--------|
| OpenAI Blog | 공식 RSS | 5 |
| Google DeepMind Blog | 공식 RSS | 5 |
| HuggingFace Blog | 공식 RSS | 4 |
| NVIDIA AI Blog | 공식 RSS | 4 |
| Meta Engineering Blog | 공식 RSS | 4 |
| Hacker News | 커뮤니티 | 3 |
| HuggingFace Models | 급상승 모델 | 3 |
| DCInside 싱귤래리티 갤 | 커뮤니티 | 3 |

수집 주기: **30분**

---

## 알림 레벨

| 레벨 | 조건 | 처리 |
|------|------|------|
| Level 5 | 공식 대형 발표, 신뢰도 5, 긴급도 5 | 즉시 알림 |
| Level 4 | 중요 논문, 큰 오픈소스 모델 | 즉시 알림 |
| Level 3 | 브리핑에 넣을 만한 소식 | 하루 브리핑 포함 |
| Level 2 | 커뮤니티 떡밥, 약한 루머 | DB 저장만 |
| Level 1 | 중복, 출처 없는 과장글 | 무시 |

---

## 기술 스택

- **Python 3.11+** / discord.py
- **Gemini 3.1 Flash Lite Preview** — 봇 메시지 생성 (LLM)
- **SQLite** — 수집 데이터 저장 및 중복 필터링
- **aiohttp + feedparser + BeautifulSoup4** — RSS/웹 수집
- **Oracle Cloud Free Tier** (AMD VM.Standard.E2.1) — 24시간 운영

---

## 파일 구조

```
AIField/
├── main.py                 # 진입점 (--live / --test)
├── config.py               # 환경변수 로드
├── scorer.py               # 점수 채점 로직
├── scheduler.py            # 수집·브리핑 스케줄러
├── llm.py                  # Gemini API 래퍼
├── bot_qianyu.py           # 진천우 봇
├── bot_perlica.py          # 펠리카 봇
├── prompts/
│   ├── qianyu_system.py    # 진천우 시스템 프롬프트
│   └── perlica_system.py   # 펠리카 시스템 프롬프트
├── collectors/
│   ├── rss.py              # 공식 RSS 수집기
│   ├── hacker_news.py      # Hacker News 수집기
│   ├── huggingface.py      # HuggingFace 모델 수집기
│   ├── dcinside.py         # DCInside 갤러리 스크래퍼 (특이점이 온다, AI 활용)
│   └── arcalive.py         # 아카라이브 AI 채팅 채널 스크래퍼
└── db/
    └── news_store.py       # SQLite 저장·중복 필터
```

---

## 설치 및 실행

### 1. 패키지 설치
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일에 값 채우기
```

```env
QIANYU_BOT_TOKEN=
PERLICA_BOT_TOKEN=
AIFIELD_LIVE_CHANNEL_ID=
AIFIELD_BRIEFING_CHANNEL_ID=
GEMINI_API_KEY=          # 없으면 하드코딩 포맷으로 fallback
AIFIELD_GUILD_ID=        # 슬래시 명령어 즉시 적용용 (선택)
```

### 3. 실행
```bash
# 더미 데이터로 Discord 흐름 테스트
python main.py

# 실제 수집 + 스케줄러 실행
python main.py --live
```

---

## 슬래시 명령어

| 명령어 | 설명 |
|--------|------|
| `/status` | 봇 상태 및 DB 통계 확인 |
| `/scan-now` | 즉시 수집 실행 |
| `/briefing-now` | 즉시 브리핑 발송 |
