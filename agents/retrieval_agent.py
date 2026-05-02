"""
에이전트 2: Retrieval Agent (RAG)
분석된 요구사항을 바탕으로 벡터 DB에서 관련 블록과 레이아웃을 검색합니다.
"""
import os
from vectordb.chroma_store import CADVectorStore
from agents.state import DesignState


def retrieval_node(state: DesignState) -> dict:
    """벡터 DB에서 요구사항에 맞는 블록과 레이아웃을 검색합니다."""
    db_dir = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    store = CADVectorStore(persist_dir=db_dir)
    req = state["parsed_requirements"]

    style_prefix = " ".join(req.get("style_keywords", []))

    # 필요 블록 타입별 시맨틱 검색
    retrieved_blocks: list[dict] = []
    for block_type in req.get("required_blocks", []):
        query = f"{style_prefix} {block_type}".strip()
        try:
            results = store.search_blocks(
                query=query,
                block_type=block_type,
                n_results=3,
            )
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                retrieved_blocks.append({
                    "block_type": block_type,
                    "document": doc,
                    "metadata": meta,
                    "similarity": round(1 - dist, 4),
                })
        except Exception:
            # 해당 타입 블록이 DB에 없는 경우 스킵
            pass

    # 유사 레이아웃 검색
    size = req.get("apartment_size_pyeong", "")
    space = req.get("target_space", "")
    layout_query = f"{size}평 {space} {style_prefix}".strip()

    try:
        retrieved_layouts = store.search_spaces(
            query=layout_query,
            space_type=space if space not in ("whole", "", None) else None,
            n_results=3,
        )
    except Exception:
        retrieved_layouts = []

    return {
        "retrieved_blocks": retrieved_blocks,
        "retrieved_layouts": retrieved_layouts,
    }
