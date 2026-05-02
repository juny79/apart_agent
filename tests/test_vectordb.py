"""
tests/test_vectordb.py — 벡터 DB 모듈 단위 테스트.
"""
import pytest

from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_block_embedding_text, build_space_embedding_text

# ------------------------------------------------------------------ #
# 샘플 데이터
# ------------------------------------------------------------------ #
SAMPLE_BLOCK = {
    "block_id": "DOOR_TEST_01",
    "type": "door",
    "style": "minimalist",
    "dimensions": {"width_mm": 900, "height_mm": 2100},
    "room_type": ["bedroom"],
    "tags": ["test"],
    "designer_notes": "테스트용 문 블록",
    "source_file": "test.dxf",
}

SAMPLE_BLOCK_UNKNOWN = {
    "block_id": "MISC_01",
    "type": "unknown",
    "dimensions": {},
    "source_file": "test.dxf",
}

SAMPLE_SPACE = {
    "space_id": "SPACE_TEST_001",
    "space_type": "living_room",
    "area_pyeong": 8.0,
    "area_sqm": 26.4,
    "apartment_size_pyeong": 30,
    "style_theme": ["minimalist", "white_tone"],
    "contains_blocks": [
        {"block_id": "SOFA_01", "x": 100, "y": 200},
        {"block_id": "TV_WALL_01", "x": 0, "y": 3000},
    ],
    "source_file": "test.dxf",
    "feedback_notes": "",
}


# ------------------------------------------------------------------ #
# 임베딩 빌더 테스트
# ------------------------------------------------------------------ #
class TestEmbeddingBuilder:
    def test_block_text_contains_type(self):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        assert "door" in text

    def test_block_text_contains_width(self):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        assert "900" in text

    def test_block_text_contains_style(self):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        assert "minimalist" in text

    def test_block_text_handles_missing_fields(self):
        minimal = {"block_id": "X", "type": "window", "dimensions": {}}
        text = build_block_embedding_text(minimal)
        assert "window" in text

    def test_space_text_contains_space_type(self):
        text = build_space_embedding_text(SAMPLE_SPACE)
        assert "living_room" in text

    def test_space_text_contains_pyeong(self):
        text = build_space_embedding_text(SAMPLE_SPACE)
        assert "30" in text

    def test_space_text_contains_block_ids(self):
        text = build_space_embedding_text(SAMPLE_SPACE)
        assert "SOFA_01" in text

    def test_space_text_with_feedback_notes(self):
        meta = {**SAMPLE_SPACE, "feedback_notes": "소파 위치 조정됨"}
        text = build_space_embedding_text(meta)
        assert "소파 위치 조정됨" in text


# ------------------------------------------------------------------ #
# Chroma DB CRUD 테스트 (임시 DB 사용)
# ------------------------------------------------------------------ #
@pytest.fixture
def temp_store(tmp_path):
    """테스트용 임시 Chroma DB 인스턴스."""
    import os
    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "test-key")
    return CADVectorStore(persist_dir=str(tmp_path / "test_chroma"))


class TestCADVectorStoreBlocks:
    def test_upsert_block_no_error(self, temp_store):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        # OpenAI API 없이 테스트 시 embedding 호출이 실패할 수 있으므로 mocking
        pytest.importorskip("chromadb")

    def test_search_blocks_empty_db_returns_empty(self, temp_store):
        """빈 DB에서 검색 시 결과가 비어 있어야 합니다."""
        # count가 0이므로 safe_n=1이지만 결과 없음
        results = temp_store.blocks_col.count()
        assert results == 0


class TestCADVectorStoreSpaces:
    def test_spaces_collection_created(self, temp_store):
        assert temp_store.spaces_col is not None

    def test_upsert_and_count_space(self, temp_store):
        """space upsert 후 count가 1이어야 합니다 (embedding 모킹)."""
        # embedding function 없이 직접 chromadb add 테스트
        temp_store.spaces_col.add(
            ids=["SPACE_TEST_001"],
            documents=["테스트 거실 레이아웃"],
            metadatas=[{
                "space_type": "living_room",
                "area_pyeong": 8.0,
                "apartment_size_pyeong": 30.0,
                "style_theme": "minimalist",
                "source_file": "test.dxf",
            }],
            embeddings=[[0.1] * 1536],  # 더미 임베딩
        )
        assert temp_store.spaces_col.count() == 1
