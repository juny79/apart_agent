"""
data/metadata/ 디렉토리의 모든 JSON 메타데이터를 읽어
Chroma DB에 일괄 인덱싱하는 실행 스크립트입니다.

사용법:
    python -m vectordb.indexer
    python -m vectordb.indexer --metadata-dir data/metadata --db-dir chroma_db
"""
import json
import argparse
from pathlib import Path

from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_block_embedding_text, build_space_embedding_text


def run_indexing(metadata_dir: str = "data/metadata", db_dir: str = "chroma_db") -> None:
    """
    메타데이터 JSON 파일을 읽어 Chroma DB에 인덱싱합니다.

    Args:
        metadata_dir: *_metadata.json 파일이 위치한 디렉토리
        db_dir: Chroma DB 저장 경로
    """
    store = CADVectorStore(persist_dir=db_dir)
    metadata_path = Path(metadata_dir)

    if not metadata_path.exists():
        print(f"[오류] 메타데이터 디렉토리가 없습니다: {metadata_path}")
        return

    json_files = sorted(metadata_path.glob("*_metadata.json"))
    if not json_files:
        print(f"[경고] {metadata_path}에 *_metadata.json 파일이 없습니다.")
        return

    block_count = 0
    space_count = 0
    skip_count = 0

    for json_file in json_files:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        source_file = data.get("source_file", json_file.name)

        # 블록 인덱싱
        for block_meta in data.get("blocks", []):
            if block_meta.get("type") == "unknown":
                skip_count += 1
                continue
            if not block_meta.get("dimensions"):
                skip_count += 1
                continue
            embedding_text = build_block_embedding_text(block_meta)
            store.upsert_block(block_meta, embedding_text)
            block_count += 1

        # 공간 레이아웃 인덱싱 (파일 기준으로 space_id 생성)
        inserts = data.get("inserts", [])
        if inserts:
            stem = Path(source_file).stem
            space_meta = {
                "space_id": f"SPACE_{stem}",
                "space_type": "unknown",
                "area_pyeong": 0,
                "area_sqm": 0,
                "apartment_size_pyeong": 0,
                "style_theme": [],
                "contains_blocks": [
                    {"block_id": ins["block_id"], "x": ins["x"], "y": ins["y"]}
                    for ins in inserts[:20]
                ],
                "source_file": source_file,
            }
            embedding_text = build_space_embedding_text(space_meta)
            store.upsert_space(space_meta, embedding_text)
            space_count += 1

    print(
        f"인덱싱 완료: 블록 {block_count}개, 공간 {space_count}개 등록 "
        f"(타입 미분류 {skip_count}개 스킵) → {db_dir}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAD 메타데이터 Vector DB 인덱서")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--db-dir", default="chroma_db")
    args = parser.parse_args()
    run_indexing(args.metadata_dir, args.db_dir)
