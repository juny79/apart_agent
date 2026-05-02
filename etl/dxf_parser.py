"""
DXF 파일에서 블록 및 공간 메타데이터를 추출하는 파서.
"""
import ezdxf
from pathlib import Path
from typing import Generator


class DXFParser:
    """DXF 파일에서 블록 및 공간 메타데이터를 추출하는 파서."""

    SPACE_LAYER_MAP = {
        "A-ROOM-BR": "bedroom",
        "A-ROOM-LR": "living_room",
        "A-ROOM-KT": "kitchen",
        "A-ROOM-BT": "bathroom",
    }

    TYPE_KEYWORDS = {
        "DOOR": "door",
        "WIN": "window",
        "SINK": "sink",
        "SOFA": "sofa",
        "BED": "bed",
        "CLOSET": "closet",
        "TOILET": "toilet",
        "BATH": "bathtub",
        "TABLE": "table",
        "CHAIR": "chair",
        "DESK": "desk",
        "ISLAND": "island_table",
        "FRIDGE": "refrigerator",
        "STOVE": "stove",
        "WASHER": "washer",
        "TUB": "bathtub",
        "SHOWER": "shower",
        "WARDROBE": "wardrobe",
        "CABINET": "cabinet",
        "SHELF": "shelf",
    }

    def __init__(self, dxf_path: str):
        self.dxf_path = dxf_path
        self.doc = ezdxf.readfile(dxf_path)
        self.msp = self.doc.modelspace()

    def extract_blocks(self) -> Generator[dict, None, None]:
        """블록 정의(BlockDef)에서 메타데이터를 추출합니다."""
        for block in self.doc.blocks:
            if block.name.startswith("*"):  # 내부 블록 제외 (*Model_Space 등)
                continue
            try:
                bbox = ezdxf.bbox.extents([block])
                dimensions = {}
                if bbox.has_data:
                    size = bbox.size
                    dimensions = {
                        "width_mm": round(size.x, 1),
                        "height_mm": round(size.y, 1),
                    }
                yield {
                    "block_id": block.name,
                    "type": self._infer_type(block.name),
                    "dimensions": dimensions,
                    "entity_count": len(list(block)),
                    "source_file": Path(self.dxf_path).name,
                }
            except Exception:
                # 바운딩 박스 계산 불가 블록은 치수 없이 등록
                yield {
                    "block_id": block.name,
                    "type": self._infer_type(block.name),
                    "dimensions": {},
                    "entity_count": len(list(block)),
                    "source_file": Path(self.dxf_path).name,
                }

    def extract_inserts(self) -> Generator[dict, None, None]:
        """모델 공간의 INSERT 엔티티(블록 삽입 위치)를 추출합니다."""
        for insert in self.msp.query("INSERT"):
            yield {
                "block_id": insert.dxf.name,
                "x": round(insert.dxf.insert.x, 1),
                "y": round(insert.dxf.insert.y, 1),
                "rotation": round(getattr(insert.dxf, "rotation", 0.0), 2),
                "layer": insert.dxf.layer,
                "scale_x": getattr(insert.dxf, "xscale", 1.0),
                "scale_y": getattr(insert.dxf, "yscale", 1.0),
            }

    def _infer_type(self, block_name: str) -> str:
        """블록 이름 컨벤션으로 타입을 추론합니다."""
        name_upper = block_name.upper()
        for keyword, block_type in self.TYPE_KEYWORDS.items():
            if keyword in name_upper:
                return block_type
        return "unknown"
