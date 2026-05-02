"""
ApartAgent FastAPI 백엔드.

엔드포인트:
    POST /generate-design   자연어 요청 → DXF 파일 생성 및 다운로드
    GET  /health            서버 상태 확인
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

load_dotenv()

from agents.graph import build_graph, create_initial_state  # noqa: E402

app = FastAPI(
    title="ApartAgent API",
    description="자연어 요청을 받아 아파트 인테리어 2D CAD 도면(DXF)을 자동 생성합니다.",
    version="1.0.0",
)

# 앱 시작 시 그래프를 한 번만 컴파일
_graph = build_graph()


class DesignRequest(BaseModel):
    user_request: str

    @field_validator("user_request")
    @classmethod
    def request_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_request는 비어 있을 수 없습니다.")
        return v.strip()


class DesignResponse(BaseModel):
    verification_passed: bool
    output_summary: str
    generated_code_version: int
    errors: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-design")
async def generate_design(request: DesignRequest):
    """
    자연어 요청을 받아 DXF 파일을 생성합니다.

    - 성공 시 DXF 파일을 직접 반환합니다 (Content-Disposition: attachment).
    - 실패 시 422 상태 코드와 오류 목록을 반환합니다.
    """
    initial_state = create_initial_state(request.user_request)

    try:
        final_state = _graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에이전트 실행 오류: {e}")

    dxf_path = final_state.get("output_dxf_path", "")

    if not dxf_path or not Path(dxf_path).exists():
        raise HTTPException(
            status_code=422,
            detail={
                "message": "도면 생성에 실패했습니다.",
                "errors": final_state.get("verification_errors", []),
                "summary": final_state.get("output_summary", ""),
            },
        )

    return FileResponse(
        path=dxf_path,
        filename="generated_design.dxf",
        media_type="application/octet-stream",
        headers={
            "X-Summary": final_state.get("output_summary", ""),
            "X-Code-Version": str(final_state.get("generated_code_version", 0)),
        },
    )


@app.post("/generate-design/preview", response_model=DesignResponse)
async def generate_design_preview(request: DesignRequest):
    """
    DXF 파일 없이 생성 결과 메타데이터만 반환합니다 (UI 미리보기용).
    """
    initial_state = create_initial_state(request.user_request)

    try:
        final_state = _graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"에이전트 실행 오류: {e}")

    return DesignResponse(
        verification_passed=final_state.get("verification_passed", False),
        output_summary=final_state.get("output_summary", ""),
        generated_code_version=final_state.get("generated_code_version", 0),
        errors=final_state.get("verification_errors", []),
    )
