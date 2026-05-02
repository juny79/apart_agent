"""
Chroma 벡터 DB를 이용한 CAD 블록 및 공간 레이아웃 CRUD.
"""
import os
import chromadb
from chromadb.utils import embedding_functions


class CADVectorStore:
    """CAD 블록 및 공간 레이아웃을 저장·검색하는 벡터 DB 클라이언트."""

    def __init__(self, persist_dir: str | None = None):
        if persist_dir is None:
            persist_dir = os.getenv("CHROMA_DB_DIR", "./chroma_db")

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embed_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name="text-embedding-3-small",
        )
        self.blocks_col = self.client.get_or_create_collection(
            name="cad_blocks",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.spaces_col = self.client.get_or_create_collection(
            name="cad_spaces",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------ #
    # 블록 CRUD
    # ------------------------------------------------------------------ #

    def upsert_block(self, block_meta: dict, embedding_text: str) -> None:
        """블록 메타데이터를 벡터 DB에 저장/갱신합니다."""
        dims = block_meta.get("dimensions", {})
        self.blocks_col.upsert(
            ids=[block_meta["block_id"]],
            documents=[embedding_text],
            metadatas=[{
                "type": block_meta.get("type", "unknown"),
                "width_mm": float(dims.get("width_mm", 0)),
                "height_mm": float(dims.get("height_mm", 0)),
                "style": block_meta.get("style", ""),
                "source_file": block_meta.get("source_file", ""),
            }],
        )

    def search_blocks(
        self,
        query: str,
        block_type: str | None = None,
        max_width_mm: float | None = None,
        n_results: int = 5,
    ) -> dict:
        """
        하이브리드 검색: 시맨틱 유사도 + 메타데이터 필터.

        Returns:
            chromadb query 결과 dict (ids, documents, metadatas, distances)
        """
        where_filter: dict = {}
        conditions = []
        if block_type:
            conditions.append({"type": {"$eq": block_type}})
        if max_width_mm is not None:
            conditions.append({"width_mm": {"$lte": max_width_mm}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        # n_results가 컬렉션 크기보다 클 수 있으므로 안전하게 클램프
        total = self.blocks_col.count()
        safe_n = min(n_results, total) if total > 0 else 1

        return self.blocks_col.query(
            query_texts=[query],
            n_results=safe_n,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

    # ------------------------------------------------------------------ #
    # 공간 CRUD
    # ------------------------------------------------------------------ #

    def upsert_space(self, space_meta: dict, embedding_text: str) -> None:
        """공간 레이아웃 메타데이터를 벡터 DB에 저장/갱신합니다."""
        self.spaces_col.upsert(
            ids=[space_meta["space_id"]],
            documents=[embedding_text],
            metadatas=[{
                "space_type": space_meta.get("space_type", "unknown"),
                "area_pyeong": float(space_meta.get("area_pyeong", 0)),
                "apartment_size_pyeong": float(space_meta.get("apartment_size_pyeong", 0)),
                "style_theme": ", ".join(space_meta.get("style_theme", [])),
                "source_file": space_meta.get("source_file", ""),
            }],
        )

    def search_spaces(
        self,
        query: str,
        space_type: str | None = None,
        apartment_size_pyeong: int | None = None,
        n_results: int = 3,
    ) -> list[dict]:
        """
        공간 레이아웃 하이브리드 검색.

        Returns:
            [{"document": str, "metadata": dict, "similarity": float}, ...]
        """
        where_filter: dict = {}
        conditions = []
        if space_type:
            conditions.append({"space_type": {"$eq": space_type}})
        if apartment_size_pyeong is not None:
            conditions.append({"apartment_size_pyeong": {"$eq": float(apartment_size_pyeong)}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        total = self.spaces_col.count()
        safe_n = min(n_results, total) if total > 0 else 1

        results = self.spaces_col.query(
            query_texts=[query],
            n_results=safe_n,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        items = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            items.append({
                "document": doc,
                "metadata": meta,
                "similarity": round(1 - dist, 4),
            })
        return items
