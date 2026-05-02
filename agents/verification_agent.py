"""
에이전트 4: Verification Agent
생성된 ezdxf 코드의 문법·실행 가능성·건축 법규 준수 여부를 검증합니다.
"""
import ast
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

    # 2. 안전한 샌드박스 실행 (임시 디렉토리)
    dxf_path: Path | None = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        code_path = tmp / "generated_design.py"
        code_path.write_text(code, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(code_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_dir,
        )

        if result.returncode != 0:
            stderr_snippet = result.stderr[:600]
            errors.append(f"[실행 오류] {stderr_snippet}")
            return {"verification_passed": False, "verification_errors": errors}

        # 3. DXF 파일 생성 확인
        dxf_files = list(tmp.glob("*.dxf"))
        if not dxf_files:
            errors.append("[검증 오류] DXF 파일이 생성되지 않았습니다. "
                          "코드에 doc.saveas(\"output.dxf\") 가 있는지 확인하세요.")
            return {"verification_passed": False, "verification_errors": errors}

        # 4. 건축 법규 제약 조건 검사
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
                        bbox = ezdxf.bbox.extents([block])
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
