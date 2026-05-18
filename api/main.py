"""
ApartAgent FastAPI 백엔드.

엔드포인트:
    POST /generate-design   자연어 요청 → DXF 파일 생성 및 다운로드
    GET  /health            서버 상태 확인
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

from agents.graph import build_graph, create_initial_state  # noqa: E402

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# 속도 제한 (Rate Limiting)                                          #
# ------------------------------------------------------------------ #
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="ApartAgent API",
    description="자연어 요청을 받아 아파트 인테리어 2D CAD 도면(DXF)을 자동 생성합니다.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: 허용 오리진은 환경변수 ALLOWED_ORIGINS 로 설정 (쉼표 구분)
_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# 인증: API Key (X-API-Key 헤더)                                       #
# ------------------------------------------------------------------ #
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key(key: str | None = Depends(_api_key_header)) -> None:
    """SERVICE_API_KEY 환경변수가 설정된 경우 API Key를 검증합니다."""
    service_key = os.getenv("SERVICE_API_KEY", "")
    if service_key and key != service_key:
        raise HTTPException(status_code=403, detail="유효하지 않은 API Key입니다.")


# ------------------------------------------------------------------ #
# 출력 경로 검증 (Path Traversal 방지)                            #
# ------------------------------------------------------------------ #
_ALLOWED_OUTPUT_DIR = Path("data/output").resolve()


def _validate_output_path(path_str: str) -> Path:
    """FileResponse 경로가 허용된 디렉토리 내에 있는지 검증합니다."""
    try:
        p = Path(path_str).resolve()
    except Exception:
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")
    if not p.is_relative_to(_ALLOWED_OUTPUT_DIR):
        logger.error("허용되지 않은 출력 경로 접근 시도: %s", path_str)
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")
    return p


# 앱 시작 시 그래프를 한 번만 컴파일
_graph = build_graph()


class DesignRequest(BaseModel):
    user_request: str

    @field_validator("user_request")
    @classmethod
    def request_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_request는 비어 있을 수 없습니다.")
        if len(v) > 1000:
            raise ValueError("user_request는 1,000자를 초과할 수 없습니다.")
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
@limiter.limit("5/minute")
async def generate_design(
    request: Request,
    body: DesignRequest,
    _: None = Depends(_verify_api_key),
):
    """
    자연어 요청을 받아 DXF 파일을 생성합니다.

    - 성공 시 DXF 파일을 직접 반환합니다 (Content-Disposition: attachment).
    - 실패 시 422 상태 코드와 오류 목록을 반환합니다.
    """
    initial_state = create_initial_state(body.user_request)

    try:
        final_state = _graph.invoke(initial_state)
    except Exception:
        logger.exception("에이전트 실행 오류")
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")

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

    validated_path = _validate_output_path(dxf_path)

    return FileResponse(
        path=str(validated_path),
        filename="generated_design.dxf",
        media_type="application/octet-stream",
        headers={
            "X-Summary": final_state.get("output_summary", ""),
            "X-Code-Version": str(final_state.get("generated_code_version", 0)),
        },
    )


@app.post("/generate-design/preview", response_model=DesignResponse)
@limiter.limit("10/minute")
async def generate_design_preview(
    request: Request,
    body: DesignRequest,
    _: None = Depends(_verify_api_key),
):
    """
    DXF 파일 없이 생성 결과 메타데이터만 반환합니다 (UI 미리보기용).
    """
    initial_state = create_initial_state(body.user_request)

    try:
        final_state = _graph.invoke(initial_state)
    except Exception:
        logger.exception("에이전트 실행 오류")
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")

    return DesignResponse(
        verification_passed=final_state.get("verification_passed", False),
        output_summary=final_state.get("output_summary", ""),
        generated_code_version=final_state.get("generated_code_version", 0),
        errors=final_state.get("verification_errors", []),
    )
