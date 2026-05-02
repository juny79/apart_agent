"""
tests/test_etl.py — ETL 모듈 단위 테스트.
"""
import json
from pathlib import Path

import pytest

from etl.dxf_parser import DXFParser
from etl.metadata_builder import build_metadata_from_dxf, build_metadata_batch

SAMPLE_DXF = Path(__file__).parent / "fixtures" / "sample.dxf"


class TestDXFParserInferType:
    """_infer_type 메서드 단위 테스트."""

    def setup_method(self):
        self.parser = DXFParser.__new__(DXFParser)

    def test_door(self):
        assert self.parser._infer_type("DOOR_MINI_01") == "door"

    def test_window(self):
        assert self.parser._infer_type("WIN_SLIDE_900") == "window"

    def test_sofa(self):
        assert self.parser._infer_type("SOFA_L_2400") == "sofa"

    def test_bed(self):
        assert self.parser._infer_type("BED_QUEEN_01") == "bed"

    def test_island_table(self):
        assert self.parser._infer_type("ISLAND_TABLE_1800") == "island_table"

    def test_unknown(self):
        assert self.parser._infer_type("MISC_OBJECT_99") == "unknown"

    def test_case_insensitive(self):
        assert self.parser._infer_type("door_standard") == "door"


class TestDXFParserExtract:
    """실제 DXF 파싱 테스트 (sample.dxf 필요)."""

    @pytest.fixture(autouse=True)
    def require_sample(self, create_sample_dxf):
        self.sample_path = create_sample_dxf

    def test_extract_blocks_returns_list(self):
        parser = DXFParser(str(self.sample_path))
        blocks = list(parser.extract_blocks())
        assert isinstance(blocks, list)
        assert len(blocks) >= 3  # DOOR_MINI_01, SOFA_L_01, WIN_SLIDE_1200

    def test_extract_blocks_schema(self):
        parser = DXFParser(str(self.sample_path))
        for block in parser.extract_blocks():
            assert "block_id" in block
            assert "type" in block
            assert "dimensions" in block
            assert "source_file" in block

    def test_extract_inserts_returns_list(self):
        parser = DXFParser(str(self.sample_path))
        inserts = list(parser.extract_inserts())
        assert isinstance(inserts, list)
        assert len(inserts) >= 3

    def test_extract_inserts_schema(self):
        parser = DXFParser(str(self.sample_path))
        for insert in parser.extract_inserts():
            assert "block_id" in insert
            assert "x" in insert
            assert "y" in insert
            assert "layer" in insert

    def test_door_block_detected(self):
        parser = DXFParser(str(self.sample_path))
        blocks = list(parser.extract_blocks())
        door_blocks = [b for b in blocks if b["type"] == "door"]
        assert len(door_blocks) >= 1


class TestMetadataBuilder:
    """메타데이터 빌더 테스트."""

    @pytest.fixture(autouse=True)
    def require_sample(self, create_sample_dxf):
        self.sample_path = create_sample_dxf

    def test_build_metadata_creates_json(self, tmp_path):
        meta = build_metadata_from_dxf(str(self.sample_path), str(tmp_path))
        assert "blocks" in meta
        assert "inserts" in meta
        assert "source_file" in meta

        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1

    def test_json_is_valid(self, tmp_path):
        build_metadata_from_dxf(str(self.sample_path), str(tmp_path))
        json_file = list(tmp_path.glob("*.json"))[0]
        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert isinstance(data["blocks"], list)
        assert isinstance(data["inserts"], list)

    def test_batch_processes_all_dxf(self, tmp_path):
        # sample.dxf를 tmp_path에 복사하여 배치 테스트
        import shutil
        dxf_dir = tmp_path / "dxf"
        dxf_dir.mkdir()
        shutil.copy2(str(self.sample_path), str(dxf_dir / "sample.dxf"))
        shutil.copy2(str(self.sample_path), str(dxf_dir / "sample2.dxf"))

        out_dir = tmp_path / "metadata"
        results = build_metadata_batch(str(dxf_dir), str(out_dir))
        assert len(results) == 2
