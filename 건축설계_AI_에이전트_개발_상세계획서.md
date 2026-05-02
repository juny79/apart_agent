# 건축 설계 AI 에이전트 개발 상세 계획서

> **프로젝트명**: ApartAgent — 아파트 인테리어 설계 자동화 멀티 에이전트 시스템  
> **작성일**: 2026-05-01  
> **버전**: v1.0

---

## 목차

1. [프로젝트 개요 및 목적](#1-프로젝트-개요-및-목적)
2. [시스템 아키텍처 전체 개요](#2-시스템-아키텍처-전체-개요)
3. [Phase 1 — CAD 데이터 파싱 및 구조화 (ETL)](#3-phase-1--cad-데이터-파싱-및-구조화-etl)
4. [Phase 2 — 벡터 DB 구축 및 임베딩 전략](#4-phase-2--벡터-db-구축-및-임베딩-전략)
5. [Phase 3 — 멀티 에이전트 아키텍처 설계](#5-phase-3--멀티-에이전트-아키텍처-설계)
6. [Phase 4 — CAD 연동 및 결과물 생성](#6-phase-4--cad-연동-및-결과물-생성)
7. [Phase 5 — 피드백 루프 및 지속적 학습](#7-phase-5--피드백-루프-및-지속적-학습)
8. [기술 스택 및 도구 선정](#8-기술-스택-및-도구-선정)
9. [개발 로드맵 및 마일스톤](#9-개발-로드맵-및-마일스톤)
10. [리스크 관리](#10-리스크-관리)
11. [기대 효과 및 ROI](#11-기대-효과-및-roi)
12. [디렉토리 구조 및 코드 스캐폴딩](#12-디렉토리-구조-및-코드-스캐폴딩)

---

## 1. 프로젝트 개요 및 목적

### 1.1 배경

아파트 인테리어 설계 실무에서는 문, 창문, 싱크대, 붙박이장 등 **표준화된 블록(Block) 객체가 반복적으로 재사용**됩니다. 그러나 현재 작업 방식은:

- 디자이너가 직접 라이브러리 폴더에서 블록을 탐색·복사·배치
- 선임 디자이너의 경험 기반 노하우가 암묵지(Tacit Knowledge)로만 존재
- 신입 디자이너의 초안 품질이 낮아 반복 수정 비용 발생

이러한 비효율을 해소하기 위해 **2D CAD 데이터를 Vector DB로 자산화**하고, **LangGraph 기반 멀티 에이전트**가 자연어 요청을 CAD 실행 스크립트로 변환하는 시스템을 개발합니다.

### 1.2 목표

| 목표 구분 | 내용 |
|---|---|
| 단기 목표 | 기존 DWG/DXF 도면을 파싱하여 블록 단위 Vector DB 구축 |
| 중기 목표 | 자연어 요청 → ezdxf Python 코드 자동 생성 파이프라인 완성 |
| 장기 목표 | 피드백 루프를 통한 설계 품질 자동 향상 (MLOps) |

### 1.3 핵심 제약 사항

- LLM은 CAD 파일을 **직접 그리는** 능력이 없음 → **코드 생성(Code Generation)** 방식으로 우회
- DWG(바이너리)는 직접 파싱 불가 → **DXF/JSON 중간 포맷** 변환 후 처리
- 건축 법규 및 최소 치수 기준을 사전 정의한 **룰셋(Ruleset)** 검증 필수

---

## 2. 시스템 아키텍처 전체 개요

```
┌──────────────────────────────────────────────────────────────┐
│                       사용자 인터페이스                         │
│          (웹 대시보드 / AutoCAD 플러그인 / CLI)                 │
└──────────────────────┬───────────────────────────────────────┘
                       │ 자연어 요청
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  LangGraph 멀티 에이전트 오케스트레이터          │
│                                                              │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ Requirement │→ │  Retrieval   │→ │    Drafting      │  │
│   │  Analysis   │  │   Agent      │  │     Agent        │  │
│   │   Agent     │  │  (RAG)       │  │ (Code Generator) │  │
│   └─────────────┘  └──────────────┘  └────────┬─────────┘  │
│                                                │            │
│                         ┌──────────────────────┘            │
│                         ▼                                    │
│                  ┌──────────────┐                            │
│                  │ Verification │ ──── 실패 시 Drafting 재호출 │
│                  │    Agent     │                            │
│                  └──────┬───────┘                            │
└─────────────────────────┼────────────────────────────────────┘
                          │ 최종 승인된 스크립트
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              CAD 실행 레이어                                   │
│     ezdxf Python 스크립트 / AutoLISP 스크립트 실행             │
│              → DXF 파일 출력                                   │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              Feedback Loop (MLOps)                           │
│     최종 수정본 DXF Diff → 벡터 DB 업데이트                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1 — CAD 데이터 파싱 및 구조화 (ETL)

### 3.1 입력 데이터 형식 처리

```
DWG (바이너리)
    └─ ODA File Converter (무료) 또는 LibreDWG
           └─ DXF (텍스트 기반) ──→ ezdxf 파싱 → JSON/YAML
```

**처리 순서:**

1. **DWG → DXF 일괄 변환**: ODA File Converter CLI를 배치 스크립트로 자동화
2. **DXF 파싱**: `ezdxf` 라이브러리로 모든 Entity와 Block 추출
3. **공간 단위 분할**: 레이어(Layer) 이름 컨벤션 기반으로 방·거실·주방 등 공간 영역 구분

### 3.2 블록(Block) 메타데이터 스키마

```json
{
  "block_id": "DOOR_MINI_01",
  "type": "door",
  "subtype": "single_hinged",
  "room_type": ["bedroom", "bathroom"],
  "style": "minimalist",
  "dimensions": {
    "width_mm": 900,
    "height_mm": 2100,
    "swing_radius_mm": 900
  },
  "insertion_point": { "x": 0.0, "y": 0.0 },
  "layer": "A-DOOR",
  "cad_block_name": "DOOR_MINI_01",
  "tags": ["standard", "interior", "2024_renovation"],
  "usage_count": 142,
  "designer_notes": "최소 통과 폭 800mm 준수 필요"
}
```

### 3.3 공간(Space) 메타데이터 스키마

```json
{
  "space_id": "LR_001",
  "space_type": "living_room",
  "area_pyeong": 8.5,
  "area_sqm": 28.1,
  "width_mm": 4200,
  "depth_mm": 6700,
  "ceiling_height_mm": 2400,
  "apartment_size_pyeong": 30,
  "style_theme": ["minimalist", "white_tone"],
  "contains_blocks": [
    { "block_id": "SOFA_L_01", "x": 1200, "y": 800, "rotation": 0 },
    { "block_id": "TV_WALL_02", "x": 0, "y": 3200, "rotation": 0 }
  ],
  "adjacent_spaces": ["kitchen", "hallway"],
  "source_file": "project_2024_A104.dxf",
  "created_by": "designer_kim",
  "created_at": "2024-11-15"
}
```

### 3.4 ETL 파이프라인 구현 예시 (Python)

#### `etl/batch_converter.py` — DWG → DXF 일괄 변환

```python
# etl/batch_converter.py
"""
ODA File Converter CLI를 이용해 디렉토리 내 모든 DWG 파일을 DXF로 일괄 변환합니다.
ODA File Converter 설치: https://www.opendesign.com/guestfiles/oda_file_converter
"""
import subprocess
import shutil
from pathlib import Path


ODA_CONVERTER_PATH = r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
DXF_VERSION = "ACAD2018"  # 출력 DXF 버전


def convert_dwg_to_dxf(input_dir: str, output_dir: str) -> list[Path]:
    """
    input_dir 내 모든 DWG 파일을 output_dir에 DXF로 변환합니다.
    반환값: 성공적으로 변환된 DXF 파일 경로 목록
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not shutil.which(ODA_CONVERTER_PATH) and not Path(ODA_CONVERTER_PATH).exists():
        raise FileNotFoundError(
            f"ODA File Converter를 찾을 수 없습니다: {ODA_CONVERTER_PATH}\n"
            "https://www.opendesign.com/guestfiles/oda_file_converter 에서 설치하세요."
        )

    # ODA CLI: <input_dir> <output_dir> <version> <type> <recurse> <audit>
    cmd = [
        ODA_CONVERTER_PATH,
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
```

#### `etl/metadata_builder.py` — 메타데이터 스키마 빌더

```python
# etl/metadata_builder.py
"""
DXFParser 결과를 받아 블록/공간 메타데이터 JSON 파일로 저장합니다.
"""
import json
from pathlib import Path
from etl.dxf_parser import DXFParser


def build_metadata_from_dxf(dxf_path: str, output_dir: str) -> dict:
    """
    단일 DXF 파일을 파싱하여 블록 및 공간 메타데이터를 JSON으로 저장합니다.
    반환값: {"blocks": [...], "inserts": [...]}
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
    out_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"메타데이터 저장: {out_file} (블록 {len(blocks)}개, 삽입 {len(inserts)}개)")
    return metadata


def build_metadata_batch(dxf_dir: str, output_dir: str) -> list[dict]:
    """디렉토리 내 모든 DXF 파일에 대해 메타데이터를 일괄 생성합니다."""
    results = []
    for dxf_file in sorted(Path(dxf_dir).glob("*.dxf")):
        try:
            meta = build_metadata_from_dxf(str(dxf_file), output_dir)
            results.append(meta)
        except Exception as e:
            print(f"[경고] {dxf_file.name} 처리 실패: {e}")
    return results
```

#### `etl/dxf_parser.py` — DXF 파서

```python
# etl/dxf_parser.py
import ezdxf
import json
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

    def __init__(self, dxf_path: str):
        self.doc = ezdxf.readfile(dxf_path)
        self.msp = self.doc.modelspace()

    def extract_blocks(self) -> Generator[dict, None, None]:
        """블록 정의(BlockDef)에서 메타데이터를 추출합니다."""
        for block in self.doc.blocks:
            if block.name.startswith("*"):  # 내부 블록 제외
                continue
            bbox = ezdxf.bbox.extents([block])
            if bbox.has_data:
                size = bbox.size
                yield {
                    "block_id": block.name,
                    "type": self._infer_type(block.name),
                    "dimensions": {
                        "width_mm": round(size.x, 1),
                        "height_mm": round(size.y, 1),
                    },
                    "entity_count": len(list(block)),
                }

    def extract_inserts(self) -> Generator[dict, None, None]:
        """모델 공간의 INSERT 엔티티(블록 삽입 위치)를 추출합니다."""
        for insert in self.msp.query("INSERT"):
            yield {
                "block_id": insert.dxf.name,
                "x": round(insert.dxf.insert.x, 1),
                "y": round(insert.dxf.insert.y, 1),
                "rotation": round(insert.dxf.rotation, 2),
                "layer": insert.dxf.layer,
                "scale_x": insert.dxf.xscale,
                "scale_y": insert.dxf.yscale,
            }

    def _infer_type(self, block_name: str) -> str:
        """블록 이름 컨벤션으로 타입을 추론합니다."""
        name_upper = block_name.upper()
        type_keywords = {
            "DOOR": "door", "WIN": "window", "SINK": "sink",
            "SOFA": "sofa", "BED": "bed", "CLOSET": "closet",
            "TOILET": "toilet", "BATH": "bathtub", "TABLE": "table",
        }
        for keyword, block_type in type_keywords.items():
            if keyword in name_upper:
                return block_type
        return "unknown"
```

---

## 4. Phase 2 — 벡터 DB 구축 및 임베딩 전략

### 4.1 Chunking 전략

**원칙: 기능적·공간적 단위로 청크를 분할하여 검색 품질 극대화**

| 청크 단위 | 설명 | 예시 |
|---|---|---|
| Block 단위 | 개별 CAD 블록 1개 | `DOOR_MINI_01` 메타데이터 |
| Space 단위 | 특정 공간 배치 레이아웃 | `30평 거실 미니멀 배치 A` |
| Zone 단위 | 연관 공간 조합 | `주방+식당 오픈 레이아웃` |
| Project 단위 | 프로젝트 요약 | `2024 A동 104호 전체 평면` |

### 4.2 임베딩 텍스트 생성 (Text-for-Embedding)

구조화된 JSON을 LLM이 이해하기 쉬운 자연어 문장으로 변환:

```python
# vectordb/embedding_builder.py

def build_block_embedding_text(block_meta: dict) -> str:
    """블록 메타데이터를 임베딩용 자연어 텍스트로 변환합니다."""
    return (
        f"{block_meta['type']} 블록. "
        f"스타일: {block_meta.get('style', '미지정')}. "
        f"크기: 너비 {block_meta['dimensions']['width_mm']}mm, "
        f"높이 {block_meta['dimensions']['height_mm']}mm. "
        f"사용 공간: {', '.join(block_meta.get('room_type', []))}. "
        f"태그: {', '.join(block_meta.get('tags', []))}. "
        f"비고: {block_meta.get('designer_notes', '')}"
    )

def build_space_embedding_text(space_meta: dict) -> str:
    """공간 메타데이터를 임베딩용 자연어 텍스트로 변환합니다."""
    blocks_summary = ", ".join(
        [b["block_id"] for b in space_meta.get("contains_blocks", [])]
    )
    return (
        f"{space_meta['space_type']} 레이아웃. "
        f"평수: {space_meta['area_pyeong']}평 ({space_meta['area_sqm']}㎡). "
        f"아파트 규모: {space_meta['apartment_size_pyeong']}평형. "
        f"디자인 테마: {', '.join(space_meta.get('style_theme', []))}. "
        f"구성 요소: {blocks_summary}. "
        f"천장고: {space_meta.get('ceiling_height_mm', 2400)}mm."
    )
```

### 4.3 Chroma DB 구축

```python
# vectordb/chroma_store.py
import chromadb
from chromadb.utils import embedding_functions

class CADVectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embed_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key="...",
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

    def upsert_block(self, block_meta: dict, embedding_text: str):
        self.blocks_col.upsert(
            ids=[block_meta["block_id"]],
            documents=[embedding_text],
            metadatas=[{
                "type": block_meta["type"],
                "width_mm": block_meta["dimensions"]["width_mm"],
                "height_mm": block_meta["dimensions"]["height_mm"],
                "style": block_meta.get("style", ""),
            }],
        )

    def search_blocks(
        self,
        query: str,
        block_type: str | None = None,
        max_width_mm: float | None = None,
        n_results: int = 5,
    ) -> list[dict]:
        """하이브리드 검색: 시맨틱 유사도 + 메타데이터 필터."""
        where_filter = {}
        if block_type:
            where_filter["type"] = {"$eq": block_type}
        if max_width_mm:
            where_filter["width_mm"] = {"$lte": max_width_mm}

        results = self.blocks_col.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def upsert_space(self, space_meta: dict, embedding_text: str):
        """공간 레이아웃 메타데이터를 벡터 DB에 저장/갱신합니다."""
        self.spaces_col.upsert(
            ids=[space_meta["space_id"]],
            documents=[embedding_text],
            metadatas=[{
                "space_type": space_meta["space_type"],
                "area_pyeong": space_meta["area_pyeong"],
                "apartment_size_pyeong": space_meta["apartment_size_pyeong"],
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
        """공간 레이아웃 하이브리드 검색."""
        where_filter = {}
        if space_type:
            where_filter["space_type"] = {"$eq": space_type}
        if apartment_size_pyeong:
            where_filter["apartment_size_pyeong"] = {"$eq": apartment_size_pyeong}

        results = self.spaces_col.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )
        # 반환 형식 정규화
        items = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            items.append({"document": doc, "metadata": meta, "similarity": round(1 - dist, 4)})
        return items

### 4.4 전체 인덱싱 실행 스크립트 (`vectordb/indexer.py`)

```python
# vectordb/indexer.py
"""
data/metadata/ 디렉토리의 모든 JSON 메타데이터를 읽어
Chroma DB에 일괄 인덱싱하는 실행 스크립트입니다.

사용법:
    python -m vectordb.indexer --metadata-dir data/metadata --db-dir chroma_db
"""
import json
import argparse
from pathlib import Path
from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_block_embedding_text, build_space_embedding_text


def run_indexing(metadata_dir: str, db_dir: str) -> None:
    store = CADVectorStore(persist_dir=db_dir)
    metadata_path = Path(metadata_dir)

    block_count = 0
    space_count = 0

    for json_file in sorted(metadata_path.glob("*_metadata.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        source_file = data.get("source_file", json_file.name)

        # 블록 인덱싱
        for block_meta in data.get("blocks", []):
            if block_meta.get("type") == "unknown":
                continue  # 타입 미분류 블록은 스킵
            embedding_text = build_block_embedding_text(block_meta)
            store.upsert_block(block_meta, embedding_text)
            block_count += 1

        # 공간 레이아웃 인덱싱 (source_file 기준으로 space_id 생성)
        inserts = data.get("inserts", [])
        if inserts:
            space_meta = {
                "space_id": f"SPACE_{Path(source_file).stem}",
                "space_type": "unknown",
                "area_pyeong": 0,
                "area_sqm": 0,
                "apartment_size_pyeong": 0,
                "style_theme": [],
                "contains_blocks": [
                    {"block_id": ins["block_id"], "x": ins["x"], "y": ins["y"]}
                    for ins in inserts[:20]  # 최대 20개 블록만 요약
                ],
                "source_file": source_file,
            }
            embedding_text = build_space_embedding_text(space_meta)
            store.upsert_space(space_meta, embedding_text)
            space_count += 1

    print(f"인덱싱 완료: 블록 {block_count}개, 공간 {space_count}개 → {db_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAD 메타데이터 Vector DB 인덱서")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--db-dir", default="chroma_db")
    args = parser.parse_args()
    run_indexing(args.metadata_dir, args.db_dir)
```

---

## 5. Phase 3 — 멀티 에이전트 아키텍처 설계

### 5.1 LangGraph 상태(State) 정의

```python
# agents/state.py
from typing import TypedDict, Annotated
import operator

class DesignState(TypedDict):
    # 사용자 입력
    user_request: str

    # 요구사항 분석 결과
    parsed_requirements: dict          # 평수, 공간, 스타일, 예산 등

    # 검색 결과
    retrieved_blocks: list[dict]       # 벡터 DB에서 검색된 블록 목록
    retrieved_layouts: list[dict]      # 유사 레이아웃 목록

    # 코드 생성 결과
    generated_code: str                # ezdxf Python 코드
    generated_code_version: int        # 재생성 횟수

    # 검증 결과
    verification_passed: bool
    verification_errors: Annotated[list[str], operator.add]  # 오류 누적

    # 최종 출력
    output_dxf_path: str
    output_summary: str
```

### 5.2 에이전트 1: Requirement Analysis Agent

```python
# agents/requirement_agent.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

REQUIREMENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 건축 설계 요구사항 분석 전문가입니다.
사용자의 자연어 요청을 분석하여 다음 JSON 형식으로 파라미터를 추출하세요.

반드시 JSON만 반환하세요 (마크다운 코드블록 없이):
{{
  "apartment_size_pyeong": <숫자 또는 null>,
  "target_space": "<공간명: living_room|bedroom|kitchen|bathroom|whole>",
  "style_keywords": ["<스타일1>", ...],
  "required_blocks": ["<블록유형1>", ...],
  "budget_tier": "<low|mid|high|null>",
  "special_requirements": "<특수 요구사항 자유 기술>"
}}"""),
    ("human", "{user_request}"),
])

def requirement_analysis_node(state: DesignState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = REQUIREMENT_PROMPT | llm
    response = chain.invoke({"user_request": state["user_request"]})
    parsed = json.loads(response.content)
    return {"parsed_requirements": parsed}
```

### 5.3 에이전트 2: Retrieval Agent (RAG)

```python
# agents/retrieval_agent.py
from vectordb.chroma_store import CADVectorStore

def retrieval_node(state: DesignState) -> dict:
    store = CADVectorStore()
    req = state["parsed_requirements"]

    # 필요 블록 타입별 검색
    retrieved_blocks = []
    for block_type in req.get("required_blocks", []):
        style_query = f"{' '.join(req.get('style_keywords', []))} {block_type}"
        results = store.search_blocks(
            query=style_query,
            block_type=block_type,
            n_results=3,
        )
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            retrieved_blocks.append({
                "document": doc,
                "metadata": meta,
                "similarity": round(1 - dist, 4),
            })

    # 유사 레이아웃 검색
    layout_query = (
        f"{req.get('apartment_size_pyeong', '')}평 "
        f"{req.get('target_space', '')} "
        f"{' '.join(req.get('style_keywords', []))}"
    )
    retrieved_layouts = store.search_spaces(query=layout_query, n_results=3)

    return {
        "retrieved_blocks": retrieved_blocks,
        "retrieved_layouts": retrieved_layouts,
    }
```

### 5.4 에이전트 3: Drafting Agent (Code Generator)

```python
# agents/drafting_agent.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

DRAFTING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 ezdxf 라이브러리 전문 건축 CAD 코딩 에이전트입니다.
주어진 요구사항과 검색된 CAD 블록 정보를 바탕으로,
실행 가능한 Python (ezdxf) 코드를 생성하세요.

[코드 작성 규칙]
1. 반드시 `import ezdxf` 로 시작하세요.
2. 모든 좌표는 밀리미터(mm) 단위를 사용하세요.
3. 레이어 이름은 AIA CAD Layer 컨벤션을 따르세요 (예: A-DOOR, A-WALL).
4. 블록 삽입 시 INSERT 엔티티를 사용하세요.
5. 마지막에 반드시 `doc.saveas("output.dxf")` 를 포함하세요.
6. 코드만 반환하세요 (설명 없이).

[이전 검증 오류가 있다면 반드시 수정하세요]
{verification_errors}
"""),
    ("human", """
[요구사항]
{parsed_requirements}

[검색된 블록 정보]
{retrieved_blocks}

[유사 레이아웃 참고]
{retrieved_layouts}

위 정보를 바탕으로 ezdxf 코드를 생성하세요.
"""),
])

def drafting_node(state: DesignState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    chain = DRAFTING_PROMPT | llm

    errors_text = "\n".join(state.get("verification_errors", [])) or "없음"
    response = chain.invoke({
        "parsed_requirements": str(state["parsed_requirements"]),
        "retrieved_blocks": str(state["retrieved_blocks"]),
        "retrieved_layouts": str(state["retrieved_layouts"]),
        "verification_errors": errors_text,
    })

    # 코드 블록 마크다운 제거
    code = response.content.strip()
    if code.startswith("```python"):
        code = code[9:]
    if code.endswith("```"):
        code = code[:-3]

    version = state.get("generated_code_version", 0) + 1
    return {"generated_code": code.strip(), "generated_code_version": version}
```

### 5.5 에이전트 4: Verification Agent

```python
# agents/verification_agent.py
import ast
import subprocess
import tempfile
import os
from pathlib import Path

# 건축 법규 기반 최소 치수 룰셋
CONSTRAINT_RULES = {
    "min_door_width_mm": 750,        # 피난 안전 최소 문 폭
    "min_corridor_width_mm": 900,    # 최소 복도 폭
    "min_bathroom_area_sqm": 2.5,    # 최소 화장실 면적
    "max_code_retries": 3,           # 최대 재생성 시도 횟수
}

def verification_node(state: DesignState) -> dict:
    code = state["generated_code"]
    errors = []

    # 1. 문법 검사
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"[문법 오류] {e}")
        return {"verification_passed": False, "verification_errors": errors}

    # 2. 안전한 샌드박스 실행 (임시 디렉토리)
    with tempfile.TemporaryDirectory() as tmp_dir:
        code_path = Path(tmp_dir) / "generated_design.py"
        code_path.write_text(code, encoding="utf-8")

        result = subprocess.run(
            ["python", str(code_path)],
            capture_output=True, text=True,
            timeout=30, cwd=tmp_dir,
        )
        if result.returncode != 0:
            errors.append(f"[실행 오류] {result.stderr[:500]}")
            return {"verification_passed": False, "verification_errors": errors}

        # 3. 생성된 DXF 파일 검증
        dxf_files = list(Path(tmp_dir).glob("*.dxf"))
        if not dxf_files:
            errors.append("[검증 오류] DXF 파일이 생성되지 않았습니다.")
            return {"verification_passed": False, "verification_errors": errors}

        constraint_errors = _check_constraints(dxf_files[0])
        errors.extend(constraint_errors)

    if errors:
        return {"verification_passed": False, "verification_errors": errors}

    return {"verification_passed": True, "output_dxf_path": str(dxf_files[0])}


def _check_constraints(dxf_path: Path) -> list[str]:
    """건축 법규 기반 제약 조건을 검사합니다."""
    import ezdxf
    errors = []
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        for insert in msp.query("INSERT"):
            if "DOOR" in insert.dxf.name.upper():
                block = doc.blocks.get(insert.dxf.name)
                if block:
                    bbox = ezdxf.bbox.extents([block])
                    if bbox.has_data and bbox.size.x < CONSTRAINT_RULES["min_door_width_mm"]:
                        errors.append(
                            f"[법규 위반] 문 '{insert.dxf.name}' 폭 {bbox.size.x:.0f}mm가 "
                            f"최소 기준 {CONSTRAINT_RULES['min_door_width_mm']}mm 미만입니다."
                        )
    except Exception as e:
        errors.append(f"[DXF 검증 오류] {e}")
    return errors
```

### 5.6 LangGraph 워크플로우 조립

```python
# agents/graph.py
from langgraph.graph import StateGraph, END
from agents.state import DesignState
from agents.requirement_agent import requirement_analysis_node
from agents.retrieval_agent import retrieval_node
from agents.drafting_agent import drafting_node
from agents.verification_agent import verification_node, CONSTRAINT_RULES

def should_retry_or_end(state: DesignState) -> str:
    """검증 결과에 따라 재시도 또는 종료를 결정합니다."""
    if state["verification_passed"]:
        return "end"
    if state.get("generated_code_version", 0) >= CONSTRAINT_RULES["max_code_retries"]:
        return "end"  # 최대 재시도 초과 시 현재 결과로 종료
    return "retry"

def build_graph() -> StateGraph:
    workflow = StateGraph(DesignState)

    # 노드 등록
    workflow.add_node("requirement_analysis", requirement_analysis_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("drafting", drafting_node)
    workflow.add_node("verification", verification_node)

    # 엣지 정의
    workflow.set_entry_point("requirement_analysis")
    workflow.add_edge("requirement_analysis", "retrieval")
    workflow.add_edge("retrieval", "drafting")
    workflow.add_edge("drafting", "verification")

    # 조건부 엣지: 검증 결과에 따라 재시도 또는 종료
    workflow.add_conditional_edges(
        "verification",
        should_retry_or_end,
        {"retry": "drafting", "end": END},
    )

    return workflow.compile()
```

> **`output_summary` 채우기**: 워크플로우 마지막 단계에서 `graph.py`의 `build_graph()`에 Summary 노드를 추가해 상태를 완성합니다.

```python
# agents/graph.py (summary 노드 추가)
from langchain_openai import ChatOpenAI

def summary_node(state: DesignState) -> dict:
    """최종 생성된 코드를 1~2문장으로 요약합니다."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = (
        "다음 ezdxf CAD 생성 코드가 어떤 도면을 만드는지 "
        "한국어로 1~2문장으로 간결하게 설명하세요:\n\n"
        f"{state['generated_code'][:1000]}"
    )
    response = llm.invoke(prompt)
    return {"output_summary": response.content.strip()}

# build_graph() 내부에 노드/엣지 추가
# workflow.add_node("summary", summary_node)
# workflow.add_edge("verification", "summary") 로 대체하고
# summary → END 로 연결
```

---

## 6. Phase 4 — CAD 연동 및 결과물 생성

### 6.1 실행 인터페이스 옵션

| 방식 | 장점 | 단점 | 권장 대상 |
|---|---|---|---|
| **웹 대시보드** | 별도 CAD 설치 불필요, 팀 공유 용이 | DXF 다운로드 후 CAD에서 열어야 함 | 초기 MVP |
| **AutoCAD 플러그인** | CAD 내에서 직접 실행, 실시간 미리보기 | AutoCAD 라이선스 필요, 개발 복잡 | 장기 목표 |
| **CLI 도구** | 배치 처리 가능 | UI 없음 | 개발자/고급 사용자 |

### 6.2 웹 대시보드 구현 (FastAPI + Streamlit)

```python
# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.graph import build_graph
import tempfile, os

app = FastAPI(title="ApartAgent API")
graph = build_graph()

class DesignRequest(BaseModel):
    user_request: str

@app.post("/generate-design")
async def generate_design(request: DesignRequest):
    """자연어 요청을 받아 DXF 파일을 생성합니다."""
    initial_state = {
        "user_request": request.user_request,
        "parsed_requirements": {},
        "retrieved_blocks": [],
        "retrieved_layouts": [],
        "generated_code": "",
        "generated_code_version": 0,
        "verification_passed": False,
        "verification_errors": [],
        "output_dxf_path": "",
        "output_summary": "",
    }
    try:
        final_state = graph.invoke(initial_state)
        if not final_state.get("output_dxf_path"):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "도면 생성에 실패했습니다.",
                    "errors": final_state.get("verification_errors", []),
                }
            )
        return FileResponse(
            path=final_state["output_dxf_path"],
            filename="generated_design.dxf",
            media_type="application/dxf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

```python
# ui/dashboard.py
import streamlit as st
import requests

st.set_page_config(page_title="ApartAgent", page_icon="🏢", layout="wide")
st.title("ApartAgent — 건축 설계 AI 에이전트")

with st.form("design_form"):
    user_request = st.text_area(
        "설계 요청사항을 입력하세요",
        placeholder="예: 30평형 아파트, 화이트 톤의 아일랜드 식탁이 있는 주방 도면을 그려줘",
        height=120,
    )
    submitted = st.form_submit_button("도면 생성 시작")

if submitted and user_request:
    with st.spinner("에이전트가 도면을 생성 중입니다..."):
        response = requests.post(
            "http://localhost:8000/generate-design",
            json={"user_request": user_request},
        )
    if response.status_code == 200:
        st.success("도면 생성 완료!")
        st.download_button(
            label="DXF 파일 다운로드",
            data=response.content,
            file_name="generated_design.dxf",
            mime="application/dxf",
        )
    else:
        st.error(f"생성 실패: {response.json().get('detail')}")
```

---

## 7. Phase 5 — 피드백 루프 및 지속적 학습

### 7.1 Diff 기반 학습 파이프라인

```
작업자가 에이전트 생성 도면을 수정
        │
        ▼
수정 전 DXF + 수정 후 DXF를 시스템에 업로드
        │
        ▼
DXF Diff 추출 (추가/삭제/이동된 엔티티 목록)
        │
        ▼
수정 내역을 분석하여 "더 나은 레이아웃 패턴" 추출
        │
        ▼
벡터 DB에 개선된 Space 메타데이터로 Upsert
        │
        ▼
다음 유사 요청 시 개선된 패턴이 우선 검색됨
```

### 7.2 DXF Diff 추출기

```python
# feedback/dxf_diff.py
import ezdxf
from dataclasses import dataclass

@dataclass
class EntityChange:
    change_type: str        # "added" | "removed" | "moved"
    block_name: str
    old_position: tuple | None
    new_position: tuple | None

def extract_diff(original_path: str, revised_path: str) -> list[EntityChange]:
    """두 DXF 파일 간의 차이를 추출합니다."""
    original_doc = ezdxf.readfile(original_path)
    revised_doc = ezdxf.readfile(revised_path)

    def get_inserts(doc) -> dict[str, tuple]:
        return {
            f"{ins.dxf.name}_{i}": (ins.dxf.insert.x, ins.dxf.insert.y)
            for i, ins in enumerate(doc.modelspace().query("INSERT"))
        }

    original_inserts = get_inserts(original_doc)
    revised_inserts = get_inserts(revised_doc)

    changes = []
    for key, pos in revised_inserts.items():
        if key not in original_inserts:
            changes.append(EntityChange("added", key.split("_")[0], None, pos))
        elif original_inserts[key] != pos:
            changes.append(EntityChange("moved", key.split("_")[0], original_inserts[key], pos))

    for key, pos in original_inserts.items():
        if key not in revised_inserts:
            changes.append(EntityChange("removed", key.split("_")[0], pos, None))

    return changes
```

### 7.3 피드백 DB 업데이트 파이프라인 (`feedback/updater.py`)

```python
# feedback/updater.py
"""
작업자가 에이전트 생성 도면을 수정한 후, 수정본을 시스템에 반영합니다.
변경 내역을 분석하여 벡터 DB의 공간 메타데이터를 업데이트합니다.

사용법:
    python -m feedback.updater \
        --original data/dxf/generated.dxf \
        --revised  data/dxf/revised_by_designer.dxf \
        --space-id SPACE_project_2024_A104
"""
import argparse
from pathlib import Path
from feedback.dxf_diff import extract_diff, EntityChange
from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_space_embedding_text


def apply_feedback(
    original_path: str,
    revised_path: str,
    space_id: str,
    db_dir: str = "chroma_db",
) -> None:
    """
    수정 전후 DXF를 비교하여 개선된 공간 메타데이터를 벡터 DB에 반영합니다.
    """
    changes: list[EntityChange] = extract_diff(original_path, revised_path)
    if not changes:
        print("변경 사항 없음. DB 업데이트를 건너뜁니다.")
        return

    store = CADVectorStore(persist_dir=db_dir)

    # 기존 공간 메타데이터 조회
    existing = store.spaces_col.get(ids=[space_id], include=["metadatas", "documents"])
    if not existing["ids"]:
        print(f"[경고] space_id '{space_id}'를 DB에서 찾을 수 없습니다. 새 항목으로 등록합니다.")
        existing_meta = {}
    else:
        existing_meta = existing["metadatas"][0]

    # 변경 요약 생성
    added = [c.block_name for c in changes if c.change_type == "added"]
    removed = [c.block_name for c in changes if c.change_type == "removed"]
    moved = [c.block_name for c in changes if c.change_type == "moved"]

    change_summary = []
    if added:
        change_summary.append(f"추가된 블록: {', '.join(added)}")
    if removed:
        change_summary.append(f"제거된 블록: {', '.join(removed)}")
    if moved:
        change_summary.append(f"이동된 블록: {', '.join(moved)}")

    print(f"변경 감지 ({len(changes)}건): {'; '.join(change_summary)}")

    # 수정본 기준으로 메타데이터 재구성
    import ezdxf
    revised_doc = ezdxf.readfile(revised_path)
    revised_inserts = [
        {"block_id": ins.dxf.name, "x": round(ins.dxf.insert.x, 1), "y": round(ins.dxf.insert.y, 1)}
        for ins in revised_doc.modelspace().query("INSERT")
    ]

    updated_meta = {
        "space_id": space_id,
        "space_type": existing_meta.get("space_type", "unknown"),
        "area_pyeong": existing_meta.get("area_pyeong", 0),
        "area_sqm": existing_meta.get("area_sqm", 0),
        "apartment_size_pyeong": existing_meta.get("apartment_size_pyeong", 0),
        "style_theme": existing_meta.get("style_theme", "").split(", "),
        "contains_blocks": revised_inserts[:20],
        "source_file": Path(revised_path).name,
        "feedback_notes": "; ".join(change_summary),
    }

    embedding_text = build_space_embedding_text(updated_meta)
    store.upsert_space(updated_meta, embedding_text)
    print(f"DB 업데이트 완료: space_id='{space_id}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="피드백 기반 벡터 DB 업데이터")
    parser.add_argument("--original", required=True, help="에이전트가 생성한 원본 DXF")
    parser.add_argument("--revised", required=True, help="디자이너가 수정한 DXF")
    parser.add_argument("--space-id", required=True, help="업데이트할 space_id")
    parser.add_argument("--db-dir", default="chroma_db")
    args = parser.parse_args()
    apply_feedback(args.original, args.revised, args.space_id, args.db_dir)
```

---

## 8. 기술 스택 및 도구 선정

| 레이어 | 기술/도구 | 선정 이유 |
|---|---|---|
| **CAD 파싱** | `ezdxf` (Python) | DXF 완전 지원, 오픈소스, ezdxf로 코드 생성도 가능 |
| **DWG→DXF 변환** | ODA File Converter | 무료 CLI, 최신 DWG 포맷 지원 |
| **임베딩 모델** | OpenAI `text-embedding-3-small` | 비용 효율적, 한국어 지원 우수 |
| **벡터 DB** | `chromadb` (로컬) / Qdrant (프로덕션) | 로컬 개발은 Chroma, 스케일 아웃 시 Qdrant |
| **LLM** | GPT-4o (OpenAI) | 코드 생성 품질, Function Calling 지원 |
| **에이전트 프레임워크** | `langgraph` | 상태 기반 순환 워크플로우, 조건부 라우팅 |
| **백엔드 API** | `FastAPI` | 비동기 처리, 자동 OpenAPI 문서 |
| **대시보드** | `Streamlit` | 빠른 프로토타이핑, Python 친화적 |
| **컨테이너화** | `Docker` + `Docker Compose` | 환경 일관성, 배포 간소화 |
| **모니터링** | `LangSmith` | LangGraph 트레이싱, 에이전트 디버깅 |

---

## 9. 개발 로드맵 및 마일스톤

### 9.1 전체 로드맵 (12주)

```
Week 1-2   │ Phase 1: ETL 파이프라인 구축
           │  - DWG→DXF 변환 배치 스크립트
           │  - ezdxf 파서 구현
           │  - 블록/공간 메타데이터 스키마 확정
           │
Week 3-4   │ Phase 2: 벡터 DB 구축
           │  - Chroma DB 초기화
           │  - 임베딩 텍스트 생성기 구현
           │  - 기존 도면 100건 인덱싱
           │
Week 5-7   │ Phase 3: 에이전트 개발
           │  - Requirement Analysis Agent
           │  - Retrieval Agent
           │  - Drafting Agent (ezdxf 코드 생성)
           │  - Verification Agent (법규 룰셋)
           │  - LangGraph 워크플로우 조립
           │
Week 8-9   │ Phase 4: 연동 및 UI
           │  - FastAPI 백엔드 구현
           │  - Streamlit 대시보드
           │  - 단위/통합 테스트
           │
Week 10    │ 내부 베타 테스트
           │  - 디자이너 5명 사용자 테스트
           │  - 피드백 수집 및 버그 수정
           │
Week 11-12 │ Phase 5: 피드백 루프
           │  - DXF Diff 추출기
           │  - 벡터 DB 업데이트 파이프라인
           │  - 운영 환경 배포 (Docker)
```

### 9.2 마일스톤별 성공 기준

| 마일스톤 | 성공 기준 |
|---|---|
| M1: ETL 완료 | 기존 도면 100건에서 블록 500개 이상 추출 성공 |
| M2: 벡터 DB 구축 | 쿼리 응답 시간 < 500ms, 검색 관련도 80% 이상 |
| M3: 에이전트 완성 | 10개 테스트 요청 중 8개 이상 실행 가능한 DXF 생성 |
| M4: UI 완성 | 비개발자 디자이너가 독립적으로 사용 가능 |
| M5: 피드백 루프 | 50건 피드백 후 검색 관련도 5%p 이상 개선 |

---

## 10. 리스크 관리

| 리스크 | 심각도 | 대응 방안 |
|---|---|---|
| LLM이 ezdxf 코드 오류 반복 생성 | 높음 | 검증 에이전트 최대 3회 재시도 + 사람 개입 알림 |
| DWG 버전 호환성 문제 | 중간 | ODA Converter로 DXF 2018 표준으로 통일 |
| 블록 이름 컨벤션 비표준화 | 중간 | ETL 단계에서 이름 정규화 규칙 사전 정의 |
| OpenAI API 비용 초과 | 낮음 | 캐싱(SQLite) 도입, 배치 임베딩 처리 |
| 건축 법규 룰셋 누락 | 높음 | 건축사 검토 후 룰셋 작성, 분기별 업데이트 |

---

## 11. 기대 효과 및 ROI

### 11.1 정량적 효과

| 업무 항목 | 기존 소요 시간 | 에이전트 적용 후 | 절감률 |
|---|---|---|---|
| 표준 공간 초안 작성 | 2~3시간 | 10~15분 | 85% |
| 블록 라이브러리 탐색 | 30분 | 즉시 (프롬프트) | 95% |
| 신입 디자이너 초안 수정 | 3~4회 반복 | 1~2회 반복 | 50% |
| 설계 노하우 전수 | 6개월 (OJT) | DB 검색으로 즉시 | — |

### 11.2 정성적 효과

- **지식 자산화**: 선임 디자이너 퇴직 시에도 설계 노하우가 DB에 보존됨
- **품질 표준화**: 에이전트가 항상 법규 기준을 충족하는 초안 제공
- **창의적 집중**: 반복 작업 제거로 고부가 가치 설계 업무에 역량 집중 가능

---

## 12. 디렉토리 구조 및 코드 스캐폴딩

```
apart_agent/
├── README.md
├── requirements.txt
├── docker-compose.yml
├── .env.example
│
├── etl/                          # Phase 1: CAD 데이터 ETL
│   ├── __init__.py
│   ├── dxf_parser.py             # DXF 파싱 및 블록 추출
│   ├── metadata_builder.py       # 메타데이터 스키마 빌더
│   └── batch_converter.py        # DWG→DXF 배치 변환
│
├── vectordb/                     # Phase 2: 벡터 DB
│   ├── __init__.py
│   ├── chroma_store.py           # Chroma DB CRUD
│   ├── embedding_builder.py      # 임베딩 텍스트 생성
│   └── indexer.py                # 전체 인덱싱 실행 스크립트
│
├── agents/                       # Phase 3: 멀티 에이전트
│   ├── __init__.py
│   ├── state.py                  # LangGraph 상태 정의
│   ├── requirement_agent.py      # 요구사항 분석 에이전트
│   ├── retrieval_agent.py        # RAG 검색 에이전트
│   ├── drafting_agent.py         # 코드 생성 에이전트
│   ├── verification_agent.py     # 검증 에이전트
│   └── graph.py                  # LangGraph 워크플로우
│
├── api/                          # Phase 4: 백엔드
│   ├── __init__.py
│   └── main.py                   # FastAPI 엔드포인트
│
├── ui/                           # Phase 4: 프론트엔드
│   └── dashboard.py              # Streamlit 대시보드
│
├── feedback/                     # Phase 5: 피드백 루프
│   ├── __init__.py
│   ├── dxf_diff.py               # DXF 변경 분석기
│   └── updater.py                # 피드백 기반 DB 업데이터
│
├── rules/                        # 건축 법규 룰셋
│   └── constraints.yaml          # 최소 치수 기준 정의
│
├── data/                         # 원본 데이터 (gitignore)
│   ├── raw_dwg/                  # 원본 DWG 파일
│   ├── dxf/                      # 변환된 DXF 파일
│   └── metadata/                 # 추출된 JSON 메타데이터
│
└── tests/                        # 테스트
    ├── fixtures/
    │   └── sample.dxf            # 테스트용 샘플 도면
    ├── test_etl.py
    ├── test_vectordb.py
    └── test_agents.py
```

---

## 부록 A: `requirements.txt`

```
# CAD 처리
ezdxf==1.3.4

# 벡터 DB
chromadb==0.5.0
qdrant-client==1.9.0         # 프로덕션용 (선택)

# LLM / 에이전트
openai==1.30.0
langchain==0.2.0
langchain-openai==0.1.7
langgraph==0.1.5
langsmith==0.1.63

# API / UI
fastapi==0.111.0
uvicorn==0.29.0
streamlit==1.35.0
pydantic==2.7.1
python-dotenv==1.0.1
requests==2.32.0

# 유틸리티
numpy==1.26.4
```

## 부록 B: `rules/constraints.yaml`

```yaml
# 건축 법규 및 설계 기준 룰셋
# 출처: 주택건설기준 등에 관한 규정, 건축물의 피난·방화구조 등의 기준에 관한 규칙

minimum_dimensions:
  door:
    width_mm: 750          # 일반 실내문 최소 폭
    accessible_width_mm: 850  # 장애인 편의 기준
  corridor:
    width_mm: 900          # 아파트 내부 복도 최소 폭
  bathroom:
    area_sqm: 2.5          # 화장실 최소 면적
  bedroom:
    area_sqm: 7.0          # 침실 최소 면적 (주거용)
  kitchen:
    work_triangle_max_mm: 7000  # 주방 작업 삼각형 최대 합계

ceiling_heights:
  standard_mm: 2400
  high_ceiling_mm: 2700

clearances:
  door_swing_clearance_mm: 100  # 문 열림 시 벽과의 최소 간격
  furniture_wall_gap_mm: 50     # 가구와 벽 사이 최소 간격
```

---

*본 계획서는 파일럿 프로젝트 착수 전 기술 검토 및 팀 정렬을 위한 문서입니다. 실제 구현 과정에서 세부 사항은 조정될 수 있습니다.*

---

## 부록 C: `docker-compose.yml`

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: apart_agent_api
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./data:/app/data
      - ./rules:/app/rules
    env_file:
      - .env
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    restart: unless-stopped

  ui:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: apart_agent_ui
    ports:
      - "8501:8501"
    env_file:
      - .env
    depends_on:
      - api
    command: streamlit run ui/dashboard.py --server.port 8501 --server.address 0.0.0.0
    restart: unless-stopped
```

> **`Dockerfile`** (공통 이미지):
>
> ```dockerfile
> FROM python:3.11-slim
> WORKDIR /app
> COPY requirements.txt .
> RUN pip install --no-cache-dir -r requirements.txt
> COPY . .
> ```

## 부록 D: `.env.example`

```dotenv
# OpenAI
OPENAI_API_KEY=sk-...

# LangSmith (에이전트 트레이싱, 선택)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=apart_agent

# 벡터 DB
CHROMA_DB_DIR=./chroma_db

# ETL 경로
RAW_DWG_DIR=./data/raw_dwg
DXF_DIR=./data/dxf
METADATA_DIR=./data/metadata

# ODA File Converter (Windows 기본 설치 경로)
ODA_CONVERTER_PATH=C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe
```

## 부록 E: 테스트 파일

### `tests/test_etl.py`

```python
# tests/test_etl.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from etl.dxf_parser import DXFParser
from etl.metadata_builder import build_metadata_from_dxf


SAMPLE_DXF = Path(__file__).parent / "fixtures" / "sample.dxf"


class TestDXFParser:
    def test_infer_type_door(self):
        parser = DXFParser.__new__(DXFParser)
        assert parser._infer_type("DOOR_MINI_01") == "door"

    def test_infer_type_window(self):
        parser = DXFParser.__new__(DXFParser)
        assert parser._infer_type("WIN_SLIDE_900") == "window"

    def test_infer_type_unknown(self):
        parser = DXFParser.__new__(DXFParser)
        assert parser._infer_type("MISC_OBJECT") == "unknown"

    @pytest.mark.skipif(not SAMPLE_DXF.exists(), reason="fixtures/sample.dxf 없음")
    def test_extract_blocks_returns_list(self):
        parser = DXFParser(str(SAMPLE_DXF))
        blocks = list(parser.extract_blocks())
        assert isinstance(blocks, list)
        for block in blocks:
            assert "block_id" in block
            assert "type" in block
            assert "dimensions" in block

    @pytest.mark.skipif(not SAMPLE_DXF.exists(), reason="fixtures/sample.dxf 없음")
    def test_extract_inserts_returns_list(self):
        parser = DXFParser(str(SAMPLE_DXF))
        inserts = list(parser.extract_inserts())
        assert isinstance(inserts, list)


class TestMetadataBuilder:
    @pytest.mark.skipif(not SAMPLE_DXF.exists(), reason="fixtures/sample.dxf 없음")
    def test_build_metadata_creates_json(self, tmp_path):
        meta = build_metadata_from_dxf(str(SAMPLE_DXF), str(tmp_path))
        assert "blocks" in meta
        assert "inserts" in meta
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1
```

### `tests/test_vectordb.py`

```python
# tests/test_vectordb.py
import pytest
from vectordb.chroma_store import CADVectorStore
from vectordb.embedding_builder import build_block_embedding_text, build_space_embedding_text


@pytest.fixture
def temp_store(tmp_path):
    """테스트용 임시 Chroma DB 인스턴스."""
    return CADVectorStore(persist_dir=str(tmp_path / "test_chroma"))


SAMPLE_BLOCK = {
    "block_id": "DOOR_TEST_01",
    "type": "door",
    "style": "minimalist",
    "dimensions": {"width_mm": 900, "height_mm": 2100},
    "room_type": ["bedroom"],
    "tags": ["test"],
    "designer_notes": "테스트용",
}

SAMPLE_SPACE = {
    "space_id": "SPACE_TEST_001",
    "space_type": "living_room",
    "area_pyeong": 8.0,
    "area_sqm": 26.4,
    "apartment_size_pyeong": 30,
    "style_theme": ["minimalist"],
    "contains_blocks": [{"block_id": "SOFA_01", "x": 100, "y": 200}],
    "source_file": "test.dxf",
}


class TestEmbeddingBuilder:
    def test_block_text_contains_type(self):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        assert "door" in text

    def test_block_text_contains_dimensions(self):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        assert "900" in text

    def test_space_text_contains_space_type(self):
        text = build_space_embedding_text(SAMPLE_SPACE)
        assert "living_room" in text

    def test_space_text_contains_pyeong(self):
        text = build_space_embedding_text(SAMPLE_SPACE)
        assert "30" in text


class TestCADVectorStore:
    def test_upsert_and_search_block(self, temp_store):
        text = build_block_embedding_text(SAMPLE_BLOCK)
        temp_store.upsert_block(SAMPLE_BLOCK, text)

        results = temp_store.search_blocks(query="미니멀 문", block_type="door", n_results=1)
        assert len(results["ids"][0]) == 1
        assert results["ids"][0][0] == "DOOR_TEST_01"

    def test_upsert_and_search_space(self, temp_store):
        text = build_space_embedding_text(SAMPLE_SPACE)
        temp_store.upsert_space(SAMPLE_SPACE, text)

        results = temp_store.search_spaces(query="30평 거실 미니멀", n_results=1)
        assert len(results) == 1
        assert results[0]["metadata"]["space_type"] == "living_room"
```

### `tests/test_agents.py`

```python
# tests/test_agents.py
import pytest
from unittest.mock import patch, MagicMock
from agents.state import DesignState
from agents.requirement_agent import requirement_analysis_node
from agents.verification_agent import _check_constraints, CONSTRAINT_RULES
from pathlib import Path


class TestRequirementAgent:
    @patch("agents.requirement_agent.ChatOpenAI")
    def test_parses_valid_json(self, mock_llm_class):
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(
            content='{"apartment_size_pyeong": 30, "target_space": "kitchen", '
                    '"style_keywords": ["minimalist"], "required_blocks": ["sink", "island_table"], '
                    '"budget_tier": "mid", "special_requirements": ""}'
        )
        with patch("agents.requirement_agent.REQUIREMENT_PROMPT.__or__", return_value=mock_chain):
            state: DesignState = {
                "user_request": "30평 미니멀 아일랜드 주방",
                "parsed_requirements": {},
                "retrieved_blocks": [], "retrieved_layouts": [],
                "generated_code": "", "generated_code_version": 0,
                "verification_passed": False, "verification_errors": [],
                "output_dxf_path": "", "output_summary": "",
            }
            result = requirement_analysis_node(state)
            assert result["parsed_requirements"]["apartment_size_pyeong"] == 30
            assert result["parsed_requirements"]["target_space"] == "kitchen"


class TestVerificationAgent:
    def test_constraint_rules_have_required_keys(self):
        assert "min_door_width_mm" in CONSTRAINT_RULES
        assert "min_corridor_width_mm" in CONSTRAINT_RULES
        assert "max_code_retries" in CONSTRAINT_RULES

    def test_check_constraints_empty_dxf(self, tmp_path):
        """빈 DXF는 제약 조건 위반 없음."""
        import ezdxf
        doc = ezdxf.new()
        dxf_path = tmp_path / "empty.dxf"
        doc.saveas(str(dxf_path))
        errors = _check_constraints(dxf_path)
        assert errors == []
```
