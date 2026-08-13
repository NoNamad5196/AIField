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
- 번호 매기기(1. 2. 3.) / 항목 나열 형식 금지 — 항상 대화체로 자연스럽게

정확성 다음으로 중요한 것은 정보량이다. 짧게 뭉뚱그려서 한두 줄로 끝내지 말고,
아는 구체적 사실(수치·출처명·날짜 등)은 최대한 담아서 관리자가 다시 찾아보지 않아도
바로 이해할 수 있게 전달한다. 각 메시지의 정확한 분량은 매번 함께 전달되는 지시를 따른다.
""".strip()


def breaking_news_user_prompt(item: NewsItem) -> str:
    """Perlica가 공식 속보를 #aifield-live에 올릴 메시지 생성용."""
    url_line = item.url or "없음"
    return "\n".join([
        "다음 공식 AI 속보를 #aifield-live에 올릴 Discord 메시지를 펠리카 말투로 써줘.",
        "",
        f"제목: {item.title}",
        f"출처: {item.source}",
        f"URL: {url_line}",
        f"요약: {item.summary or '요약 없음'}",
        f"특이점 영향도: {item.singularity_impact}/5 | 긴급도: {item.urgency}/5 | 신뢰도: {item.reliability}/5",
        f"알림 레벨: Level {item.alert_level}",
        "",
        "메시지 형식 (엄수):",
        "① **제목 한국어 번역** 굵게 — 출처 (URL)",
        "② 무슨 일인지 + 왜 지금 중요한지를 4~5줄로 구체적으로 설명 (영어면 번역, 원문 복사 금지)",
        "   추상적인 소감 대신 구체적 사실(수치, 대상, 범위, 배경 기술 등)을 최대한 담을 것",
        "   제목에 내용이 없으면 출처·URL 기반으로 아는 맥락 최대한 담아서",
        "③ `영향 X | 긴급 X | 신뢰 X` 수치 한 줄",
        "④ 한줄평 (예: 'AI는 또 한 걸음 앞으로 나아갔어.')",
        "",
        "- 전체 8~10줄 이내. 번호·구분선·섹션 제목 없이 자연스럽게",
        "- 이모지 절대 금지. **굵게** 만 허용",
        "- 펠리카 말투: 차분하고 정확한 반말. 딱딱한 비서체·과장 선동 금지",
    ])


def verification_user_prompt(item: NewsItem) -> str:
    """루머 스레드에 달 Perlica 검증 결과 메시지 생성용."""
    official_str = "예" if item.is_official else "아니오"
    comments_section = (
        f"\n갤러리에 실제로 달린 댓글 전체 (닉네임: 내용):\n{item.raw_comments}"
        if item.raw_comments
        else "\n갤러리 댓글: 없음 (댓글이 없거나 아직 안 달림)"
    )
    return "\n".join([
        "천우가 방금 정보를 들고 왔어. 펠리카가 내용을 제대로 읽고 판단해서 스레드에 댓글로 반응해줘.",
        "구글 검색 툴이 연결되어 있으니, 사실 확인이나 후속 정보가 필요하면 직접 검색해서 확인하고 반영할 것.",
        "",
        f"제목: {item.title}",
        f"출처: {item.source}",
        f"공식 여부: {official_str}",
        f"신뢰도: {item.reliability}/5 | 긴급도: {item.urgency}/5",
        f"요약: {item.summary or '요약 없음'}",
        comments_section,
        "",
        "요구사항:",
        "- 이모티콘(이모지) 절대 사용 금지. 텍스트만 사용할 것",
        "- **굵게** 등 기본 텍스트 강조만 허용",
        "- 6~9줄 이내",
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
        "- 검색해서 확인한 내용이 있으면 구체적 사실(수치/출처명/날짜 등)을 그대로 녹여서 언급 — 뭉뚱그리지 말 것. 특별히 확인된 게 없으면 '아직 확인된 후속 정보는 없어' 식으로 솔직하게 말할 것",
        "- 갤러리 댓글은 전체를 다 읽고 종합해서 판단에 반영할 것. 절대 댓글을 그대로 나열하거나 목록 형태로 베껴 쓰지 말 것 —",
        "  몇 명이 어떤 의견을 냈는지(동의/반박/추가정보/우려 등 흐름), 대표적인 반응 1~2개는 문장 속에 자연스럽게 인용하며 종합해서 서술할 것",
        "  예: '댓글에서도 비용 얼마나 들지 궁금해하는 반응이 많고, 일반 사용자보다는 자율주행 같은 실시간 처리가 필요한 쪽에 먼저 쓰일 거란 의견도 있어.'",
        "  댓글이 없으면 '아직 댓글 반응은 없어' 라고 명확히 말할 것",
        "- 같은 패턴 반복 금지. 매번 내용에 맞게 다르게 반응할 것",
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
            summary_short = (it.summary or "")[:250]
            parts.append(f"- {it.title}")
            if summary_short:
                parts.append(f"  {summary_short}")
            parts.append(f"  (출처: {it.source} | 영향도: {it.singularity_impact}/5)")
        parts.append("")

    if community:
        parts.append(f"【커뮤니티 / 루머 {len(community)}건 — 오늘 갤에서 오간 주요 내용】")
        for it in community[:6]:
            summary_short = (it.summary or "")[:250]
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
        "  형식: **제목** — 무슨 내용인지 + 왜 지금 중요한지 1~2줄",
        "  예: **MS '미토스 능가 AI 공개'** — 김태수 교수 주도 개발, 기존 대비 벤치마크 X% 향상. 국내 AI 연구 방향에 영향 줄 수 있어.",
        "  공식/루머 구분 없이 오늘 가장 눈에 띄는 것들 위주로 선별.",
        "  단순 제목 재탕 말고, 위에 제공된 원문 요약 속 구체적 사실(수치/대상/기능)을 반드시 녹여서 관리자가 클릭 안 해도 내용을 알 수 있게 할 것.",
        "",
        "  [커뮤니티 흐름 — 2~3문장]",
        "  주요 항목에 안 들어간 커뮤 글들을 묶어서 정리하되, 각 글이 무슨 내용이었는지 구체적으로.",
        "  예: '오늘 커뮤에선 애플이 앱스토어에 AI 에이전트 자율 결제 기능을 테스트 중이라는 얘기, 오픈소스 벤치마크 조작 논란도 나왔어.'",
        "  커뮤 내용이 없으면 생략.",
        "",
        "- HuggingFace 개별 모델명(user/model 형식) 절대 언급 금지 — '신규 모델 X건' 식으로만",
        "- 전체 18~22줄 이내",
        "- Discord Markdown **굵게** 사용 (제목에 반드시 적용)",
        "- 펠리카 말투: 차분하고 정확한 반말. 보고서 아니고 대화체로",
        "- 딱딱한 비서체, 과장 선동 절대 금지",
        '- 마지막에서 두 번째 줄: "관리자, 너무 무리하지 말고 핵심만 먼저 보면 돼."',
        '- 맨 마지막 줄: "*AI는 또 한 걸음 앞으로 나아갔어.*"',
    ]

    return "\n".join(parts)
