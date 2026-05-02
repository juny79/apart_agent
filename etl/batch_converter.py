"""
ODA File Converter CLI를 이용해 디렉토리 내 모든 DWG 파일을 DXF로 일괄 변환합니다.

ODA File Converter 설치:
    https://www.opendesign.com/guestfiles/oda_file_converter

사용법:
    python -m etl.batch_converter --input-dir data/raw_dwg --output-dir data/dxf
"""
import subprocess
import shutil
import argparse
from pathlib import Path

ODA_CONVERTER_PATH = r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
DXF_VERSION = "ACAD2018"  # 출력 DXF 버전


def convert_dwg_to_dxf(input_dir: str, output_dir: str) -> list[Path]:
    """
    input_dir 내 모든 DWG 파일을 output_dir에 DXF로 변환합니다.

    Returns:
        성공적으로 변환된 DXF 파일 경로 목록
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    oda_path = Path(ODA_CONVERTER_PATH)
    if not oda_path.exists() and not shutil.which(str(oda_path)):
        raise FileNotFoundError(
            f"ODA File Converter를 찾을 수 없습니다: {ODA_CONVERTER_PATH}\n"
            "https://www.opendesign.com/guestfiles/oda_file_converter 에서 설치하세요."
        )

    dwg_files = list(input_path.glob("*.dwg")) + list(input_path.glob("*.DWG"))
    if not dwg_files:
        print(f"[경고] {input_path}에 DWG 파일이 없습니다.")
        return []

    print(f"변환 시작: {len(dwg_files)}개 DWG 파일 → {output_path}")

    # ODA CLI: <input_dir> <output_dir> <version> <type> <recurse> <audit>
    cmd = [
        str(oda_path),
        str(input_path),
        str(output_path),
        DXF_VERSION,
        "DXF",
        "0",   # 하위 폴더 재귀 탐색 안 함
        "1",   # 파일 감사(audit) 활성화
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ODA 변환 실패:\n{result.stderr}")

    converted = list(output_path.glob("*.dxf"))
    print(f"변환 완료: {len(converted)}개 DXF 파일 생성 → {output_path}")
    return converted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DWG → DXF 일괄 변환기")
    parser.add_argument("--input-dir", default="data/raw_dwg", help="DWG 파일 디렉토리")
    parser.add_argument("--output-dir", default="data/dxf", help="DXF 출력 디렉토리")
    args = parser.parse_args()
    convert_dwg_to_dxf(args.input_dir, args.output_dir)
