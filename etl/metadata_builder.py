"""
DXFParser 결과를 받아 블록/공간 메타데이터 JSON 파일로 저장합니다.

사용법:
    python -m etl.metadata_builder --dxf-dir data/dxf --output-dir data/metadata
"""
import json
import argparse
from pathlib import Path

from etl.dxf_parser import DXFParser


def build_metadata_from_dxf(dxf_path: str, output_dir: str) -> dict:
    """
    단일 DXF 파일을 파싱하여 블록 및 공간 메타데이터를 JSON으로 저장합니다.

    Returns:
        {"source_file": str, "blocks": [...], "inserts": [...]}
    """
    parser = DXFParser(dxf_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = Path(dxf_path).stem
    blocks = list(parser.extract_blocks())
    inserts = list(parser.extract_inserts())

    metadata = {
        "source_file": Path(dxf_path).name,
        "blocks": blocks,
        "inserts": inserts,
    }

    out_file = output_path / f"{stem}_metadata.json"
    out_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"메타데이터 저장: {out_file} (블록 {len(blocks)}개, 삽입 {len(inserts)}개)")
    return metadata


def build_metadata_batch(dxf_dir: str, output_dir: str) -> list[dict]:
    """디렉토리 내 모든 DXF 파일에 대해 메타데이터를 일괄 생성합니다."""
    results = []
    dxf_files = sorted(Path(dxf_dir).glob("*.dxf")) + sorted(Path(dxf_dir).glob("*.DXF"))
    if not dxf_files:
        print(f"[경고] {dxf_dir}에 DXF 파일이 없습니다.")
        return results

    for dxf_file in dxf_files:
        try:
            meta = build_metadata_from_dxf(str(dxf_file), output_dir)
            results.append(meta)
        except Exception as e:
            print(f"[경고] {dxf_file.name} 처리 실패: {e}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DXF → JSON 메타데이터 빌더")
    parser.add_argument("--dxf-dir", default="data/dxf", help="DXF 파일 디렉토리")
    parser.add_argument("--output-dir", default="data/metadata", help="JSON 출력 디렉토리")
    args = parser.parse_args()
    build_metadata_batch(args.dxf_dir, args.output_dir)
