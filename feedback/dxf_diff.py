"""
두 DXF 파일 간의 엔티티 변경 사항을 추출합니다.
"""
import ezdxf
from dataclasses import dataclass


@dataclass
class EntityChange:
    change_type: str            # "added" | "removed" | "moved"
    block_name: str
    old_position: tuple | None  # (x, y)
    new_position: tuple | None  # (x, y)

    def __str__(self) -> str:
        if self.change_type == "added":
            return f"추가: {self.block_name} @ {self.new_position}"
        if self.change_type == "removed":
            return f"제거: {self.block_name} @ {self.old_position}"
        return (
            f"이동: {self.block_name} "
            f"{self.old_position} → {self.new_position}"
        )


def extract_diff(original_path: str, revised_path: str) -> list[EntityChange]:
    """
    두 DXF 파일 간의 INSERT 엔티티 차이를 추출합니다.

    Args:
        original_path: 에이전트가 생성한 원본 DXF 경로
        revised_path:  디자이너가 수정한 DXF 경로

    Returns:
        변경 사항 목록 (추가/제거/이동)
    """
    original_doc = ezdxf.readfile(original_path)
    revised_doc = ezdxf.readfile(revised_path)

    def get_inserts(doc: ezdxf.document.Drawing) -> dict[str, tuple[float, float]]:
        """INSERT 엔티티를 인덱스 키로 매핑합니다."""
        return {
            f"{ins.dxf.name}_{i}": (
                round(ins.dxf.insert.x, 1),
                round(ins.dxf.insert.y, 1),
            )
            for i, ins in enumerate(doc.modelspace().query("INSERT"))
        }

    original_inserts = get_inserts(original_doc)
    revised_inserts = get_inserts(revised_doc)

    changes: list[EntityChange] = []

    for key, pos in revised_inserts.items():
        block_name = key.rsplit("_", 1)[0]
        if key not in original_inserts:
            changes.append(EntityChange("added", block_name, None, pos))
        elif original_inserts[key] != pos:
            changes.append(EntityChange("moved", block_name, original_inserts[key], pos))

    for key, pos in original_inserts.items():
        block_name = key.rsplit("_", 1)[0]
        if key not in revised_inserts:
            changes.append(EntityChange("removed", block_name, pos, None))

    return changes
