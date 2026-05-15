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
    official_str = "예" if item.is_official else "아니오"
    return "\n".join([
        "다음 공식 AI 속보를 #aifield-live에 올릴 Discord 메시지를 펠리카 말투로 써줘.",
        "",
        f"제목: {item.title}",
        f"출처: {item.source}",
        f"URL: {item.url or '없음'}",
        f"요약: {item.summary or '요약 없음'}",
        f"공식 여부: {official_str}",
        f"특이점 영향도: {item.singularity_impact}/5 | 긴급도: {item.urgency}/5",
        f"신뢰도: {item.reliability}/5 | 실용성: {item.practicality}/5",
        f"알림 레벨: Level {item.alert_level}",
        "",
        "요구사항:",
        "- 이모티콘(이모지) 절대 사용 금지. 텍스트만 사용할 것",
        "- **굵게** 등 기본 텍스트 강조만 허용",
        "- 6~10줄 이내",
        "- 핵심 내용을 반드시 한국어로 3~5줄 요약 (영어라면 번역 후 풀어서 설명, 원문 영어 그대로 복사 금지)",
        "- 펠리카 말투: 차분하고 정확한 반말, 관리자와 가까운 동료처럼",
        "- 수치는 마지막 한 줄에만 간략히 (예: `영향 3 | 긴급 4 | 신뢰 5`)",
        "- 마지막 줄에 한줄평 포함 (예: 'AI는 또 한 걸음 앞으로 나아갔어.')",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
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
        "진천우가 방금 루머를 올렸어. 펠리카가 HN 서칭까지 마친 후 검증 결과를 스레드에 달 댓글로 써줘.",
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
        "- 4~6줄 이내",
        "- 펠리카 말투: 차분하고 정확한 반말, 관리자와 가까운 동료처럼",
        "- 내용을 실제로 읽고 판단해서 아래 중 하나로 자연스럽게 반응할 것:",
        "  · 잡담/뻘소리/유머 → '이건 그냥 잡담이야, 넘어가도 될 것 같아.' 식으로 가볍게",
        "  · 흥미로운 분석/정보글 → 핵심 내용 요약 + 왜 주목할 만한지",
        "  · 실제 루머/유출 → 신뢰도 평가 + 추적 여부 의견",
        "  · 공식 발표 확인 → 출처 강조 + 신뢰도 높음 명시",
        "- 매번 같은 판에 박힌 문장 금지. 내용에 맞게 다르게 반응할 것",
        "- HN 서칭 결과 있으면 간략히 언급",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
    ])


def briefing_user_prompt(items: list[NewsItem], date_str: str) -> str:
    """일일 브리핑 전체 텍스트 생성용."""
    official = [it for it in items if it.is_official]
    rumors = [it for it in items if not it.is_official]

    parts = [
        f"{date_str} AIField 일일 브리핑을 펠리카 말투로 작성해줘.",
        "",
        f"오늘 수집된 항목 총 {len(items)}개.",
        "",
    ]

    if official:
        parts.append(f"【공식 발표 {len(official)}건】")
        for i, it in enumerate(official[:5], 1):
            summary_short = (it.summary or "")[:80]
            parts.append(f"{i}. {it.title}")
            if summary_short:
                parts.append(f"   요약: {summary_short}")
            parts.append(f"   출처: {it.source} | 영향도: {it.singularity_impact}/5 | Level {it.alert_level}")
        parts.append("")

    if rumors:
        parts.append(f"【루머/커뮤니티 {len(rumors)}건】")
        for i, it in enumerate(rumors[:5], 1):
            summary_short = (it.summary or "")[:80]
            parts.append(f"{i}. {it.title}")
            if summary_short:
                parts.append(f"   요약: {summary_short}")
            parts.append(f"   출처: {it.source} | 신뢰도: {it.reliability}/5")
        parts.append("")

    parts += [
        "요구사항:",
        "- Discord Markdown 사용 (**섹션 제목**, > 인용 등)",
        "- 전체 20줄 이내",
        "- 펠리카 말투: 차분하고 정확한 반말, 관리자와 가까운 동료처럼",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
        "",
        "브리핑 구성 방식 (단순 나열 금지):",
        "1. 수집된 항목 중 가장 중요한 3건만 선별",
        "   - 각 항목마다: 제목 + '왜 지금 중요한가' 분석 2줄 (단순 요약 아님)",
        "   - 영향도/신뢰도 높은 순으로 선별",
        "2. 나머지 항목은 '그 외' 섹션에 한 줄씩 간략히",
        "3. 마지막에 오늘 AI 흐름 트렌드 1줄 요약",
        '4. 맨 끝: "관리자, 너무 무리하지 말고 핵심만 먼저 보면 돼."',
        '5. 시그니처: "*AI는 또 한 걸음 앞으로 나아갔어.*"',
    ]

    return "\n".join(parts)
