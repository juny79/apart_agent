"""
LangGraph 멀티 에이전트 워크플로우 조립.

워크플로우 흐름:
    requirement_analysis → retrieval → drafting → verification
                                              ↑              |
                                              └─── retry ────┘
                                                        (검증 실패 시, 최대 3회)
"""
import os
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from agents.state import DesignState
from agents.requirement_agent import requirement_analysis_node
from agents.retrieval_agent import retrieval_node
from agents.drafting_agent import drafting_node
from agents.verification_agent import verification_node, CONSTRAINT_RULES


def summary_node(state: DesignState) -> dict:
    """최종 생성된 코드를 1~2문장으로 요약합니다."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    code_snippet = state.get("generated_code", "")[:1200]
    prompt = (
        "다음 ezdxf CAD 생성 코드가 어떤 도면을 만드는지 "
        "한국어로 1~2문장으로 간결하게 설명하세요. "
        "레이어 구성, 주요 객체, 공간 종류를 언급하세요:\n\n"
        f"{code_snippet}"
    )
    response = llm.invoke(prompt)
    return {"output_summary": response.content.strip()}


def should_retry_or_end(state: DesignState) -> str:
    """검증 결과에 따라 재시도 또는 요약 단계로 분기합니다."""
    if state["verification_passed"]:
        return "summarize"
    if state.get("generated_code_version", 0) >= CONSTRAINT_RULES["max_code_retries"]:
        return "summarize"  # 최대 재시도 초과 → 현재 결과로 종료
    return "retry"


def build_graph() -> StateGraph:
    """LangGraph 멀티 에이전트 워크플로우를 빌드하고 컴파일합니다."""
    workflow = StateGraph(DesignState)

    # 노드 등록
    workflow.add_node("requirement_analysis", requirement_analysis_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("drafting", drafting_node)
    workflow.add_node("verification", verification_node)
    workflow.add_node("summary", summary_node)

    # 기본 엣지
    workflow.set_entry_point("requirement_analysis")
    workflow.add_edge("requirement_analysis", "retrieval")
    workflow.add_edge("retrieval", "drafting")
    workflow.add_edge("drafting", "verification")
    workflow.add_edge("summary", END)

    # 조건부 엣지: 검증 결과에 따라 재시도 또는 요약
    workflow.add_conditional_edges(
        "verification",
        should_retry_or_end,
        {
            "retry": "drafting",
            "summarize": "summary",
        },
    )

    return workflow.compile()


def create_initial_state(user_request: str) -> DesignState:
    """초기 상태(DesignState)를 생성합니다."""
    return DesignState(
        user_request=user_request,
        parsed_requirements={},
        retrieved_blocks=[],
        retrieved_layouts=[],
        generated_code="",
        generated_code_version=0,
        verification_passed=False,
        verification_errors=[],
        output_dxf_path="",
        output_summary="",
    )
