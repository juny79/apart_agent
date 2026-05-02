"""
LangGraph 에이전트 워크플로우의 공유 상태(State) 정의.
"""
from typing import TypedDict, Annotated
import operator


class DesignState(TypedDict):
    # 사용자 입력
    user_request: str

    # 요구사항 분석 결과
    parsed_requirements: dict          # 평수, 공간, 스타일, 예산 등

    # 검색 결과
    retrieved_blocks: list[dict]       # 벡터 DB에서 검색된 블록 목록
    retrieved_layouts: list[dict]      # 유사 레이아웃 목록

    # 코드 생성 결과
    generated_code: str                # ezdxf Python 코드
    generated_code_version: int        # 재생성 횟수

    # 검증 결과
    verification_passed: bool
    verification_errors: Annotated[list[str], operator.add]  # 오류 누적

    # 최종 출력
    output_dxf_path: str
    output_summary: str
