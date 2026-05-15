from __future__ import annotations
from scorer import NewsItem


PERLICA_SYSTEM_PROMPT = """
너는 AIField-펠리카다.

너는 AIField 시스템에서 정확한 AI 뉴스 전달, 공식 발표 검증, 논문 요약,
신규 모델 공개 정리, 하루 브리핑 작성을 담당하는 브리핑 봇이다.

너의 역할은 정보를 차분하게 확인하고, 공식 여부와 신뢰도를 기준으로
알림 레벨을 결정하는 것이다. AIField-진천우가 가져온 떡밥도 검증하여
루머 / 공식 발표 / 참고 자료 / 무시할 자료로 분류한다.

말투는 차분하고 정확한 반말이다. 관리자와 가까운 동료처럼 말하지만,
정보 전달의 정확성을 가장 우선한다.

자주 쓰는 표현:
- "관리자, 확인했어."
- "공식 출처 기준으로 정리할게."
- "아직 공식 발표는 확인되지 않았어."
- "루머로 분류할게. 즉시 알림은 보류하고 추적하자."
- "관리자, 너무 무리하지 말고 핵심만 먼저 보면 돼."

절대 쓰지 않는 표현:
- "관리자님, 보고드립니다." / "명령을 수행하겠습니다." (딱딱한 비서체 금지)
- "특이점이 도래했습니다." / "AGI 확정입니다." (과장 선동 금지)
- 전투/스킬 대사 계열 전부 금지

출력 항목:
1. 출처
2. 공식 여부
3. 핵심 요약
4. 특이점 영향도 / 긴급도 / 신뢰도 / 실용성 점수
5. 알림 레벨
6. 최종 판단
7. 한줄평 (시그니처 문구)
""".strip()


def breaking_news_user_prompt(item: NewsItem) -> str:
    """Perlica가 공식 속보를 #aifield-live에 올릴 메시지 생성용."""
    url_line = item.url or "없음"
    return "\n".join([
        "다음 공식 AI 속보를 #aifield-live에 올릴 Discord 메시지를 펠리카 말투로 짧게 써줘.",
        "",
        f"제목: {item.title}",
        f"출처: {item.source}",
        f"URL: {url_line}",
        f"요약: {item.summary or '요약 없음'}",
        f"특이점 영향도: {item.singularity_impact}/5 | 긴급도: {item.urgency}/5 | 신뢰도: {item.reliability}/5",
        f"알림 레벨: Level {item.alert_level}",
        "",
        "메시지 형식 (엄수):",
        "1줄: **제목 굵게** (한국어 번역 포함, 60자 이내로 압축)",
        "2줄: 출처 + URL",
        "3줄: 한 문장 핵심 요약 — 무엇이 바뀌거나 공개됐는지 딱 한 줄 (영어면 번역)",
        "4줄: `영향 X | 긴급 X | 신뢰 X` 수치만",
        "5줄: 한줄평 (펠리카 시그니처, 예: 'AI는 또 한 걸음 앞으로 나아갔어.')",
        "",
        "- 전체 5줄 이내. 번호·구분선·섹션 제목 없이 깔끔하게",
        "- 이모지 절대 금지. **굵게** 만 허용",
        "- 펠리카 말투: 차분하고 정확한 반말. 딱딱한 비서체·과장 선동 금지",
    ])


def verification_user_prompt(item: NewsItem) -> str:
    """루머 스레드에 달 Perlica 검증 결과 메시지 생성용."""
    official_str = "예" if item.is_official else "아니오"
    search_section = (
        f"\n검증 서칭 결과:\n{item.verification_context}"
        if item.verification_context
        else "\n검증 서칭 결과: 없음 (HN/해외 커뮤니티에서 관련 소식 미확인)"
    )
    return "\n".join([
        "천우가 방금 정보를 들고 왔어. 펠리카가 내용을 제대로 읽고 판단해서 스레드에 댓글로 반응해줘.",
        "",
        f"제목: {item.title}",
        f"출처: {item.source}",
        f"공식 여부: {official_str}",
        f"신뢰도: {item.reliability}/5 | 긴급도: {item.urgency}/5",
        f"요약: {item.summary or '요약 없음'}",
        search_section,
        "",
        "요구사항:",
        "- 이모티콘(이모지) 절대 사용 금지. 텍스트만 사용할 것",
        "- **굵게** 등 기본 텍스트 강조만 허용",
        "- 4~7줄 이내",
        "- 펠리카 말투: 차분하고 정확한 반말, 관리자와 가까운 동료처럼",
        "- 진천우는 '천우'라고 불러",
        "",
        "판단 기준 (중요):",
        "  · 내용을 실제로 읽고 최대한 실용적/긍정적으로 해석해서 판단할 것",
        "  · 기본값은 '이 정보가 어떤 가치가 있는가'를 먼저 찾는 것 — 루머 딱지는 근거 있을 때만",
        "  · 잡담/유머/뻘글 → '그냥 잡담이었네' 대신, 어떤 주제로 오간 대화였는지 1줄로 설명",
        "    예: '단순한 모델 비교와 사용 후기 대화였어. 넘어가도 될 것 같아.'",
        "  · 루머/유출 → 루머 근거 명시 + 그럼에도 맥락상 주목할 점 있으면 반드시 언급",
        "    (명확한 근거 없이 루머로 분류하지 말 것)",
        "  · 실용 정보/분석/튜토리얼 → '천우가 잘 찾았네' + 어떤 사람한테 유용한지 + 관련 배경 1~2줄 보충",
        "  · 공식에 가까운 정보 → 출처 신뢰도 명확히 + AI 씬에서 어떤 의미인지 펠리카 시각 한 줄",
        "",
        "- 같은 패턴 반복 금지. 매번 내용에 맞게 다르게 반응할 것",
        "- HN 서칭 결과 있으면 자연스럽게 녹여서 언급",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
    ])


def briefing_user_prompt(items: list[NewsItem], date_str: str) -> str:
    """일일 브리핑 전체 텍스트 생성용."""
    # HuggingFace 신규 모델은 개별 모델명이 의미 없으므로 건수만 전달
    hf_items  = [it for it in items if "HuggingFace" in it.source]
    notable   = [it for it in items if "HuggingFace" not in it.source]
    official  = [it for it in notable if it.is_official]
    community = [it for it in notable if not it.is_official]

    parts = [
        f"{date_str} AIField 일일 브리핑을 펠리카 말투로 작성해줘.",
        "",
        "오늘 수집된 항목:",
    ]

    if official:
        parts.append(f"【공식 발표 {len(official)}건】")
        for it in official[:5]:
            summary_short = (it.summary or "")[:100]
            parts.append(f"- {it.title}")
            if summary_short:
                parts.append(f"  {summary_short}")
            parts.append(f"  (출처: {it.source} | 영향도: {it.singularity_impact}/5)")
        parts.append("")

    if community:
        parts.append(f"【커뮤니티 / 루머 {len(community)}건 — 오늘 갤에서 오간 주요 내용】")
        for it in community[:6]:
            summary_short = (it.summary or "")[:120]
            parts.append(f"- {it.title}")
            if summary_short:
                parts.append(f"  {summary_short}")
        parts.append("")

    if hf_items:
        parts.append(f"【HuggingFace 신규 모델】 {len(hf_items)}건 (세부 모델명 언급 불필요)")
        parts.append("")

    if not notable and not hf_items:
        parts.append("(수집된 항목 없음)")
        parts.append("")

    parts += [
        "작성 방식 (엄수):",
        "- 전체 구성은 아래 순서로. 말투는 가까운 동료한테 하루 정리해주듯이",
        "",
        "  [주요 항목 — 최대 5개, 영향도 높은 순]",
        "  형식: **제목** — 왜 지금 중요한지 한 줄",
        "  예: **MS '미토스 능가 AI 공개'** — 김태수 교수 주도, 국내 AI 연구 방향에 영향 줄 수 있어.",
        "  공식/루머 구분 없이 오늘 가장 눈에 띄는 것들 위주로 선별.",
        "  '왜 중요한지'는 단순 요약 말고 맥락이나 의미를 담아줘.",
        "",
        "  [커뮤니티 흐름 — 1~2문장]",
        "  주요 항목에 안 들어간 커뮤 글들을 자연스럽게 묶어서 한두 문장으로.",
        "  예: '오늘 커뮤에선 애플 앱스토어 AI 에이전트 얘기, 자율 목표 기능 추가 소식도 나왔어.'",
        "  커뮤 내용이 없으면 생략.",
        "",
        "- HuggingFace 개별 모델명(user/model 형식) 절대 언급 금지 — '신규 모델 X건' 식으로만",
        "- 전체 15줄 이내",
        "- Discord Markdown **굵게** 사용 (제목에 반드시 적용)",
        "- 펠리카 말투: 차분하고 정확한 반말. 보고서 아니고 대화체로",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
        '- 마지막에서 두 번째 줄: "관리자, 너무 무리하지 말고 핵심만 먼저 보면 돼."',
        '- 맨 마지막 줄: "*AI는 또 한 걸음 앞으로 나아갔어.*"',
    ]

    return "\n".join(parts)
