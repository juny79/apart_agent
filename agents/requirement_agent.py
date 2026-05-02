"""
에이전트 1: Requirement Analysis Agent
사용자의 자연어 요청을 분석하여 설계 파라미터 JSON을 추출합니다.
"""
import json
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agents.state import DesignState

REQUIREMENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 건축 설계 요구사항 분석 전문가입니다.
사용자의 자연어 요청을 분석하여 다음 JSON 형식으로 파라미터를 추출하세요.

반드시 JSON만 반환하세요 (마크다운 코드블록 없이):
{{
  "apartment_size_pyeong": <숫자 또는 null>,
  "target_space": "<공간명: living_room|bedroom|kitchen|bathroom|whole>",
  "style_keywords": ["<스타일1>", ...],
  "required_blocks": ["<블록유형1>", ...],
  "budget_tier": "<low|mid|high|null>",
  "special_requirements": "<특수 요구사항 자유 기술>"
}}

블록 유형 예시: door, window, sink, sofa, bed, closet, toilet, bathtub,
               table, island_table, refrigerator, stove, wardrobe, cabinet"""),
    ("human", "{user_request}"),
])


def requirement_analysis_node(state: DesignState) -> dict:
    """사용자 요청을 파싱하여 구조화된 요구사항을 반환합니다."""
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    chain = REQUIREMENT_PROMPT | llm
    response = chain.invoke({"user_request": state["user_request"]})

    content = response.content.strip()
    # 혹시 코드 블록이 있으면 제거
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # LLM 응답 파싱 실패 시 기본값으로 폴백
        parsed = {
            "apartment_size_pyeong": None,
            "target_space": "whole",
            "style_keywords": [],
            "required_blocks": [],
            "budget_tier": None,
            "special_requirements": state["user_request"],
        }

    return {"parsed_requirements": parsed}
