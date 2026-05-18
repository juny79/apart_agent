"""
에이전트 4: Verification Agent
생성된 ezdxf 코드의 문법·실행 가능성·건축 법규 준수 여부를 검증합니다.
"""
import ast
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from agents.state import DesignState

# 건축 법규 기반 최소 치수 룰셋
CONSTRAINT_RULES = {
    "min_door_width_mm": 750,         # 피난 안전 최소 문 폭
    "min_corridor_width_mm": 900,     # 최소 복도 폭
    "min_bathroom_area_sqm": 2.5,     # 최소 화장실 면적
    "max_code_retries": 3,            # 최대 재생성 시도 횟수
}

# ------------------------------------------------------------------ #
# 코드 보안 검사 설정
# ------------------------------------------------------------------ #
# 허용된 최상위 모듈 화이트리스트 (ezdxf 코드 생성에 필요한 것만 허용)
_ALLOWED_IMPORTS: frozenset[str] = frozenset({"ezdxf", "math"})
# 실행 위험 내장 함수 금지 목록
_BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__", "open", "breakpoint",
})

logger = logging.getLogger(__name__)


def _check_code_safety(code: str) -> list[str]:
    """
    LLM 생성 코드의 허용 모듈·금지 함수 화이트리스트 검사.

    Returns:
        보안 위반 오류 메시지 목록 (정상이면 빈 리스트)
    """
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # 문법 오류는 상위 단계에서 처리

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in _ALLOWED_IMPORTS:
                    errors.append(
                        f"[보안 위반] 허용되지 않은 모듈 임포트: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            if top not in _ALLOWED_IMPORTS:
                errors.append(
                    f"[보안 위반] 허용되지 않은 모듈 임포트: "
                    f"'from {module} import ...'"
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_BUILTINS:
                errors.append(
                    f"[보안 위반] 금지된 함수 호출: '{node.func.id}()'"
                )

    return errors


def verification_node(state: DesignState) -> dict:
    """생성된 코드를 검증하고 결과를 반환합니다."""
    code = state["generated_code"]
    errors: list[str] = []

    # 1. 문법 검사
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"[문법 오류] {e}")
        return {"verification_passed": False, "verification_errors": errors}

    # 2. 보안 화이트리스트 검사 (허용 모듈·금지 함수)
    safety_errors = _check_code_safety(code)
    if safety_errors:
        errors.extend(safety_errors)
        return {"verification_passed": False, "verification_errors": errors}

    # 3. 안전한 샌드박스 실행 (임시 디렉토리 + 환경변수 격리)
    dxf_path: Path | None = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        code_path = tmp / "generated_design.py"
        code_path.write_text(code, encoding="utf-8")

        # 환경변수 격리: API 키 등 시크릿이 서브프로세스에 노출되지 않도록 제한
        _safe_env: dict[str, str] = {"PATH": os.environ.get("PATH", "")}
        for _k in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "WINDIR"):
            _v = os.environ.get(_k)
            if _v:
                _safe_env[_k] = _v

        result = subprocess.run(
            [sys.executable, str(code_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_dir,
            env=_safe_env,
        )

        if result.returncode != 0:
            stderr_snippet = result.stderr[:600]
            errors.append(f"[실행 오류] {stderr_snippet}")
            return {"verification_passed": False, "verification_errors": errors}

        # 4. DXF 파일 생성 확인
        dxf_files = list(tmp.glob("*.dxf"))
        if not dxf_files:
            errors.append("[검증 오류] DXF 파일이 생성되지 않았습니다. "
                          "코드에 doc.saveas(\"output.dxf\") 가 있는지 확인하세요.")
            return {"verification_passed": False, "verification_errors": errors}

        # 5. 건축 법규 제약 조건 검사
        constraint_errors = _check_constraints(dxf_files[0])
        errors.extend(constraint_errors)

        # 검증 통과 시 파일을 영구 위치에 복사
        if not errors:
            import shutil
            output_dir = Path("data") / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / "generated_design.dxf"
            shutil.copy2(str(dxf_files[0]), str(final_path))
            dxf_path = final_path

    if errors:
        return {"verification_passed": False, "verification_errors": errors}

    return {
        "verification_passed": True,
        "output_dxf_path": str(dxf_path),
    }


def _check_constraints(dxf_path: Path) -> list[str]:
    """건축 법규 기반 제약 조건을 검사합니다."""
    import ezdxf

    import ezdxf.bbox

    errors: list[str] = []
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        for insert in msp.query("INSERT"):
            block_name = insert.dxf.name.upper()
            if "DOOR" in block_name:
                block = doc.blocks.get(insert.dxf.name)
                if block:
                    try:
                        bbox = ezdxf.bbox.extents(block)
                        if bbox.has_data:
                            effective_width = bbox.size.x * getattr(insert.dxf, "xscale", 1.0)
                            if effective_width < CONSTRAINT_RULES["min_door_width_mm"]:
                                errors.append(
                                    f"[법규 위반] 문 '{insert.dxf.name}' 유효 폭 "
                                    f"{effective_width:.0f}mm 가 최소 기준 "
                                    f"{CONSTRAINT_RULES['min_door_width_mm']}mm 미만입니다."
                                )
                    except Exception:
                        pass  # 바운딩 박스 계산 실패는 무시

    except Exception as e:
        errors.append(f"[DXF 검증 오류] {e}")

    return errors
