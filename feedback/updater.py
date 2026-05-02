"""
피드백 기반 벡터 DB 업데이터.
작업자가 에이전트 생성 도면을 수정한 후, 수정본을 시스템에 반영합니다.

사용법:
    python -m feedback.updater \\
        --original data/output/generated_design.dxf \\
        --revised  data/dxf/revised_by_designer.dxf \\
        --space-id SPACE_project_A104
"""
import argparse
import os
from pathlib import Path

import ezdxf

from feedback.dxf_diff import extract_diff, EntityChange
from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_space_embedding_text


def apply_feedback(
    original_path: str,
    revised_path: str,
    space_id: str,
    db_dir: str | None = None,
) -> None:
    """
    수정 전후 DXF를 비교하여 개선된 공간 메타데이터를 벡터 DB에 반영합니다.

    Args:
        original_path: 에이전트가 생성한 원본 DXF
        revised_path:  디자이너가 수정 완료한 DXF
        space_id:      업데이트할 벡터 DB space_id
        db_dir:        Chroma DB 경로 (None이면 환경 변수 사용)
    """
    if db_dir is None:
        db_dir = os.getenv("CHROMA_DB_DIR", "./chroma_db")

    changes: list[EntityChange] = extract_diff(original_path, revised_path)
    if not changes:
        print("변경 사항 없음. DB 업데이트를 건너뜁니다.")
        return

    # 변경 요약 생성
    added = [c.block_name for c in changes if c.change_type == "added"]
    removed = [c.block_name for c in changes if c.change_type == "removed"]
    moved = [c.block_name for c in changes if c.change_type == "moved"]

    summary_parts = []
    if added:
        summary_parts.append(f"추가된 블록: {', '.join(added)}")
    if removed:
        summary_parts.append(f"제거된 블록: {', '.join(removed)}")
    if moved:
        summary_parts.append(f"이동된 블록: {', '.join(moved)}")
    change_summary = "; ".join(summary_parts)
    print(f"변경 감지 ({len(changes)}건): {change_summary}")

    # 기존 공간 메타데이터 조회
    store = CADVectorStore(persist_dir=db_dir)
    existing = store.spaces_col.get(ids=[space_id], include=["metadatas", "documents"])
    existing_meta: dict = existing["metadatas"][0] if existing["ids"] else {}

    if not existing["ids"]:
        print(f"[경고] space_id '{space_id}'를 DB에서 찾을 수 없습니다. 새 항목으로 등록합니다.")

    # 수정본 기준으로 메타데이터 재구성
    revised_doc = ezdxf.readfile(revised_path)
    revised_inserts = [
        {
            "block_id": ins.dxf.name,
            "x": round(ins.dxf.insert.x, 1),
            "y": round(ins.dxf.insert.y, 1),
        }
        for ins in revised_doc.modelspace().query("INSERT")
    ]

    style_theme_raw = existing_meta.get("style_theme", "")
    style_theme = (
        [s.strip() for s in style_theme_raw.split(",") if s.strip()]
        if isinstance(style_theme_raw, str)
        else style_theme_raw
    )

    updated_meta = {
        "space_id": space_id,
        "space_type": existing_meta.get("space_type", "unknown"),
        "area_pyeong": existing_meta.get("area_pyeong", 0),
        "area_sqm": existing_meta.get("area_sqm", 0),
        "apartment_size_pyeong": existing_meta.get("apartment_size_pyeong", 0),
        "style_theme": style_theme,
        "contains_blocks": revised_inserts[:20],
        "source_file": Path(revised_path).name,
        "feedback_notes": change_summary,
    }

    embedding_text = build_space_embedding_text(updated_meta)
    store.upsert_space(updated_meta, embedding_text)
    print(f"DB 업데이트 완료: space_id='{space_id}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="피드백 기반 벡터 DB 업데이터")
    parser.add_argument("--original", required=True, help="에이전트가 생성한 원본 DXF")
    parser.add_argument("--revised", required=True, help="디자이너가 수정한 DXF")
    parser.add_argument("--space-id", required=True, help="업데이트할 space_id")
    parser.add_argument("--db-dir", default=None)
    args = parser.parse_args()
    apply_feedback(args.original, args.revised, args.space_id, args.db_dir)
