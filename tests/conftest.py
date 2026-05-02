"""
tests/conftest.py — pytest 공통 픽스처 및 샘플 DXF 생성 유틸리티.
"""
import pytest
import ezdxf
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def create_sample_dxf():
    """테스트용 샘플 DXF 파일을 fixtures/ 디렉토리에 생성합니다."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    sample_path = FIXTURES_DIR / "sample.dxf"

    if not sample_path.exists():
        doc = ezdxf.new(dxfversion="R2018")

        # 블록 정의
        door_block = doc.blocks.new(name="DOOR_MINI_01")
        door_block.add_line((0, 0), (900, 0))      # 문 폭
        door_block.add_line((0, 0), (0, 2100))     # 문 높이
        door_block.add_arc((0, 0), 900, 0, 90)     # 열림 호

        sofa_block = doc.blocks.new(name="SOFA_L_01")
        sofa_block.add_lwpolyline(
            [(0, 0), (2400, 0), (2400, 900), (0, 900), (0, 0)],
            close=True,
        )

        win_block = doc.blocks.new(name="WIN_SLIDE_1200")
        win_block.add_line((0, 0), (1200, 0))

        # 레이어 생성
        doc.layers.new(name="A-DOOR", dxfattribs={"color": 3})
        doc.layers.new(name="A-FURN", dxfattribs={"color": 5})
        doc.layers.new(name="A-GLAZ", dxfattribs={"color": 4})
        doc.layers.new(name="A-WALL", dxfattribs={"color": 7})

        # 모델 공간에 블록 삽입
        msp = doc.modelspace()
        msp.add_blockref("DOOR_MINI_01", insert=(500, 0), dxfattribs={"layer": "A-DOOR"})
        msp.add_blockref("SOFA_L_01", insert=(1000, 1000), dxfattribs={"layer": "A-FURN"})
        msp.add_blockref("WIN_SLIDE_1200", insert=(2000, 0), dxfattribs={"layer": "A-GLAZ"})

        doc.saveas(str(sample_path))

    return sample_path
