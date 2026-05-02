"""
블록 및 공간 메타데이터를 임베딩용 자연어 텍스트로 변환합니다.
구조화된 JSON을 LLM 임베딩 모델이 이해하기 쉬운 문장으로 변환하는 유틸리티입니다.
"""


def build_block_embedding_text(block_meta: dict) -> str:
    """
    블록 메타데이터를 임베딩용 자연어 텍스트로 변환합니다.

    Args:
        block_meta: DXFParser.extract_blocks() 반환값 또는 동일 스키마 dict

    Returns:
        임베딩용 자연어 문자열
    """
    dims = block_meta.get("dimensions", {})
    width = dims.get("width_mm", "미지정")
    height = dims.get("height_mm", "미지정")

    parts = [
        f"{block_meta.get('type', 'unknown')} 블록.",
        f"스타일: {block_meta.get('style', '미지정')}.",
        f"크기: 너비 {width}mm, 높이 {height}mm.",
        f"사용 공간: {', '.join(block_meta.get('room_type', []))}." if block_meta.get("room_type") else "",
        f"태그: {', '.join(block_meta.get('tags', []))}." if block_meta.get("tags") else "",
        f"비고: {block_meta.get('designer_notes', '')}." if block_meta.get("designer_notes") else "",
    ]
    return " ".join(p for p in parts if p)


def build_space_embedding_text(space_meta: dict) -> str:
    """
    공간 메타데이터를 임베딩용 자연어 텍스트로 변환합니다.

    Args:
        space_meta: 공간 레이아웃 메타데이터 dict

    Returns:
        임베딩용 자연어 문자열
    """
    blocks_summary = ", ".join(
        b["block_id"] for b in space_meta.get("contains_blocks", [])
    )

    parts = [
        f"{space_meta.get('space_type', 'unknown')} 레이아웃.",
        f"평수: {space_meta.get('area_pyeong', 0)}평 ({space_meta.get('area_sqm', 0)}㎡).",
        f"아파트 규모: {space_meta.get('apartment_size_pyeong', 0)}평형.",
        f"디자인 테마: {', '.join(space_meta.get('style_theme', []))}." if space_meta.get("style_theme") else "",
        f"구성 요소: {blocks_summary}." if blocks_summary else "",
        f"천장고: {space_meta.get('ceiling_height_mm', 2400)}mm.",
        f"피드백 메모: {space_meta.get('feedback_notes', '')}." if space_meta.get("feedback_notes") else "",
    ]
    return " ".join(p for p in parts if p)
