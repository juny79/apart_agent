# 건축 설계 AI 에이전트 — 아키텍처 및 데이터 흐름 보고서

**프로젝트명:** Apart Agent  
**작성일:** 2026-05-03  
**버전:** 1.0

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [전체 아키텍처 구성도](#2-전체-아키텍처-구성도)
3. [Phase 1 — ETL 파이프라인](#3-phase-1--etl-파이프라인-오프라인)
4. [Phase 2 — 멀티 에이전트 추론](#4-phase-2--langgraph-멀티-에이전트-추론-온라인)
5. [Phase 3 — 피드백 루프](#5-phase-3--피드백-루프)
6. [핵심 기술 스택](#6-핵심-기술-스택)
7. [모듈별 파일 구조](#7-모듈별-파일-구조)

---

## 1. 시스템 개요

본 시스템은 과거 프로젝트에서 축적된 CAD(2D) 데이터를 벡터 DB에 인덱싱하고,  
사용자의 자연어 요청을 기반으로 아파트 인테리어 도면(DXF)을 자동 생성하는 **멀티 에이전트 AI 파이프라인**이다.

### 핵심 설계 원칙

| 원칙 | 내용 |
|------|------|
| **LLM은 코드를 생성한다** | GPT-4o가 직접 CAD를 그리지 않고 `ezdxf` Python 코드를 생성 → 샌드박스에서 실행 |
| **RAG 기반 검색** | 과거 CAD 블록·레이아웃을 벡터화하여 유사 도면 참조 |
| **3단계 자동 검증** | 문법 → 실행 → 건축 법규 순서로 생성 코드를 검증 |
| **피드백 루프** | 설계사 수정본을 DB에 재반영하여 지속적 품질 향상 |

---

## 2. 전체 아키텍처 구성도

```
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 1 · ETL 파이프라인 (오프라인 · 1회성)                          │
│                                                                      │
│  .dwg/.dxf ──► ODA Converter ──► DXFParser ──► MetadataBuilder      │
│                                                      │               │
│                                              JSON 저장               │
│                                                      │               │
│                                          EmbeddingBuilder            │
│                                                      │               │
│                                      text-embedding-3-small          │
│                                                      │               │
│                                             Chroma DB                │
│                                    [cad_blocks / cad_spaces]         │
└──────────────────────────────────────────────────────────────────────┘
                                        │
                               cosine 유사도 검색
                                        │
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 2 · LangGraph 멀티 에이전트 워크플로우 (온라인)                  │
│                                                                      │
│  사용자 요청 (Streamlit / FastAPI)                                    │
│        │                                                             │
│        ▼                                                             │
│  [1] Requirement Analysis Agent  (GPT-4o)                           │
│      자연어 → {평수, 공간, 스타일, 필요 블록, 예산}                      │
│        │                                                             │
│        ▼                                                             │
│  [2] Retrieval Agent                                                 │
│      Chroma DB 검색 → 유사 블록 + 레이아웃 RAG                        │
│        │                                                             │
│        ▼                                                             │
│  [3] Drafting Agent  (GPT-4o)  ◄──────────────┐                     │
│      ezdxf Python 코드 생성                     │ retry (최대 3회)    │
│        │                                       │                     │
│        ▼                                       │                     │
│  [4] Verification Agent                        │                     │
│      ① 문법 검사 (ast.parse)                    │                     │
│      ② 샌드박스 실행 (subprocess, timeout 30s) │                     │
│      ③ 법규 검사 (문폭≥750mm / 복도≥900mm) ────┘ 실패 시 재시도        │
│        │                                                             │
│        ▼ (통과 또는 재시도 한도 초과)                                   │
│  [5] Summary Node  (GPT-4o-mini)                                     │
│      도면 설명 1~2문장 생성                                            │
│        │                                                             │
│        ▼                                                             │
│  DXF 파일 출력  (data/output/generated_design.dxf)                  │
└──────────────────────────────────────────────────────────────────────┘
                                        │
                                  설계사 수정
                                        │
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 3 · 피드백 루프                                                 │
│                                                                      │
│  수정 DXF ──► dxf_diff (변경 감지) ──► updater (메타 재구성)            │
│                                            │                         │
│                                    Chroma DB upsert                  │
│                              (다음 검색부터 품질 향상)                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1 — ETL 파이프라인 (오프라인)

과거 CAD 프로젝트 데이터를 **최초 1회** 처리하여 벡터 DB에 인덱싱하는 단계이다.

### 3.1 처리 흐름

```
과거 CAD 파일 (.dwg / .dxf)
        │
        ▼  [etl/batch_converter.py]
   ODA File Converter CLI 호출
   DWG → DXF R2018 변환
        │
        ▼  [etl/dxf_parser.py]
   블록 정의 파싱          INSERT 엔티티 파싱
   ├─ 블록명 → 타입 추론   ├─ 삽입 좌표 (x, y)
   │  (20개 키워드 매핑)   ├─ 회전각 / 축척
   └─ 치수 추출 (mm)       └─ 레이어 → 공간 타입
        │
        ▼  [etl/metadata_builder.py]
   {source_file, blocks[], inserts[]} → JSON 저장
        │
        ▼  [vectordb/embedding_builder.py]
   JSON 메타데이터 → 자연어 텍스트 변환
   예) "door block, width 900mm, minimalist style"
        │
        ▼  [OpenAI text-embedding-3-small]
   1536차원 벡터 생성
        │
        ▼  [vectordb/indexer.py + chroma_store.py]
   Chroma DB 저장
   ├─ cad_blocks  컬렉션  (블록 단위)
   └─ cad_spaces  컬렉션  (레이아웃 단위)
```

### 3.2 블록 타입 자동 분류

`dxf_parser.py`는 블록명 키워드를 기반으로 20가지 타입을 자동 분류한다.

| 키워드 | 분류 타입 |
|--------|----------|
| DOOR | door |
| WIN | window |
| SOFA | sofa |
| BED | bed |
| SINK / ISLAND | sink / island_table |
| TOILET / BATH / SHOWER | toilet / bathtub / shower |
| FRIDGE / STOVE / WASHER | refrigerator / stove / washer |
| CLOSET / WARDROBE / CABINET | closet / wardrobe / cabinet |

### 3.3 CLI 실행 명령어

```bash
# 1단계: DWG → DXF 변환
python -m etl.batch_converter --input-dir data/raw_dwg --output-dir data/dxf

# 2단계: DXF → JSON 메타데이터 추출
python -m etl.metadata_builder --dxf-dir data/dxf --output-dir data/metadata

# 3단계: 벡터 DB 인덱싱
python -m vectordb.indexer --metadata-dir data/metadata --db-dir chroma_db
```

---

## 4. Phase 2 — LangGraph 멀티 에이전트 추론 (온라인)

사용자 요청마다 실행되는 **5개 노드의 LangGraph StateGraph** 워크플로우이다.

### 4.1 상태 정의 (DesignState)

모든 에이전트는 공유 상태 `DesignState`를 통해 데이터를 주고받는다.

| 필드 | 타입 | 역할 |
|------|------|------|
| `user_request` | str | 원본 사용자 요청 |
| `parsed_requirements` | dict | 구조화된 설계 파라미터 |
| `retrieved_blocks` | list[dict] | RAG 검색된 블록 목록 |
| `retrieved_layouts` | list[dict] | RAG 검색된 레이아웃 목록 |
| `generated_code` | str | 생성된 ezdxf 코드 |
| `generated_code_version` | int | 재시도 횟수 카운터 |
| `verification_passed` | bool | 검증 통과 여부 |
| `verification_errors` | list[str] | 누적 오류 메시지 (Annotated 합산) |
| `output_dxf_path` | str | 생성 완료된 DXF 경로 |
| `output_summary` | str | 도면 설명 요약 |

### 4.2 에이전트별 역할

#### Agent 1 — Requirement Analysis Agent
- **모델:** GPT-4o (temperature=0)
- **입력:** 자연어 요청 (예: "30평 아파트 미니멀 거실")
- **출력:** 구조화 JSON
  ```json
  {
    "apartment_size_pyeong": 30,
    "target_space": "living_room",
    "style_keywords": ["minimalist", "white_tone"],
    "required_blocks": ["sofa", "tv_wall", "coffee_table"],
    "budget_tier": "mid",
    "special_requirements": ""
  }
  ```

#### Agent 2 — Retrieval Agent
- **입력:** `parsed_requirements`의 `required_blocks` 목록
- **동작:**
  - `required_blocks` 항목별로 `search_blocks()` 호출 (n=3)
  - 공간 타입으로 `search_spaces()` 호출 (n=3)
  - cosine 유사도 기반 TOP-K 반환
- **출력:** `retrieved_blocks`, `retrieved_layouts`

#### Agent 3 — Drafting Agent
- **모델:** GPT-4o (temperature=0.2)
- **입력:** 파라미터 + 검색된 블록/레이아웃 참조
- **출력:** 실행 가능한 ezdxf Python 코드
- **코드 생성 규칙 (11개):**
  1. `doc = ezdxf.new("R2018")` 으로 시작
  2. AIA 레이어 네이밍 규칙 준수 (A-WALL, A-DOOR, A-FURN 등)
  3. `doc.saveas("output.dxf")` 로 종료
  4. 마크다운 코드 펜스 없이 코드만 출력
  5. mm 단위 절대 좌표 사용
  6. 블록 삽입 시 레이어 명시
  7. 등 (총 11개 규칙)

#### Agent 4 — Verification Agent
- **3단계 검증 파이프라인:**

  | 단계 | 방법 | 통과 기준 |
  |------|------|----------|
  | ① 문법 검사 | `ast.parse()` | SyntaxError 없음 |
  | ② 실행 검사 | `subprocess` 샌드박스 (timeout 30s) | returncode == 0, .dxf 생성 확인 |
  | ③ 법규 검사 | `_check_constraints()` | 문폭≥750mm, 복도≥900mm |

- **재시도 로직:** 실패 시 오류 메시지를 `verification_errors`에 추가하고 Drafting Agent로 재전송 (최대 3회)

#### Agent 5 — Summary Node
- **모델:** GPT-4o-mini (temperature=0)
- **입력:** 생성된 ezdxf 코드 (최대 1200자)
- **출력:** 도면 설명 1~2문장 (레이어 구성, 주요 객체, 공간 종류 포함)

### 4.3 조건부 분기 로직

```
verification 노드 완료
        │
        ▼
should_retry_or_end() 판단
        │
        ├─ verification_passed == True  ──────────► summary 노드
        │
        ├─ generated_code_version >= 3  ──────────► summary 노드 (강제 종료)
        │
        └─ 그 외                         ──────────► drafting 노드 (재시도)
```

### 4.4 API 엔드포인트

| 엔드포인트 | 메서드 | 응답 |
|-----------|--------|------|
| `/health` | GET | `{"status": "ok"}` |
| `/generate-design` | POST | DXF FileResponse + `X-Summary` 헤더 |
| `/generate-design/preview` | POST | JSON (verification_passed, summary, 오류 목록) |

---

## 5. Phase 3 — 피드백 루프

설계사가 생성된 도면을 수정하면, 그 수정 내용이 벡터 DB에 자동 반영된다.

### 5.1 처리 흐름

```
설계사가 DXF 파일 수정 (편집 툴에서 가구 이동·추가·삭제)
        │
        ▼  [feedback/dxf_diff.py]
   extract_diff(original_path, revised_path)
   ├─ INSERT 엔티티 키: {block_name}_{index}
   ├─ 추가된 블록  (added)
   ├─ 제거된 블록  (removed)
   └─ 이동된 블록  (moved, 좌표 변경)
        │
        ▼  [feedback/updater.py]
   apply_feedback()
   ├─ 변경 요약 문자열 생성
   ├─ 수정본 기준 INSERT 목록 재구성
   └─ updated_meta 딕셔너리 생성
        │
        ▼  [vectordb/chroma_store.py]
   upsert_space(updated_meta, embedding_text)
   → Chroma DB [cad_spaces] 갱신
```

### 5.2 CLI 실행 명령어

```bash
python -m feedback.updater \
  --original data/output/generated_design.dxf \
  --revised  data/dxf/revised_by_designer.dxf \
  --space-id SPACE_project_A104
```

### 5.3 피드백 루프의 효과

- 설계사 선호 패턴이 DB에 누적됨
- 동일한 평형·스타일 요청 시 이전 수정 내역이 검색에 반영됨
- 별도의 재학습 없이 지속적 품질 향상 (RAG 기반)

---

## 6. 핵심 기술 스택

| 범주 | 기술 | 버전 | 용도 |
|------|------|------|------|
| CAD 처리 | ezdxf | 1.3.4 | DXF 파싱 및 생성 |
| CAD 변환 | ODA File Converter | 외부 CLI | DWG → DXF 변환 |
| 벡터 DB | chromadb | 0.5.0 | 블록/레이아웃 유사도 검색 |
| 임베딩 | text-embedding-3-small | OpenAI | 1536차원 벡터 생성 |
| LLM | GPT-4o | OpenAI | 요구사항 분석, 코드 생성 |
| LLM | GPT-4o-mini | OpenAI | 도면 요약 |
| 오케스트레이션 | langgraph | 0.1.5 | 멀티 에이전트 StateGraph |
| LLM 프레임워크 | langchain / langchain-openai | 0.2.0 / 0.1.7 | 프롬프트 템플릿, LLM 래퍼 |
| 트레이싱 | LangSmith | 0.1.63 | 에이전트 실행 추적 (선택) |
| API 서버 | FastAPI + uvicorn | 0.111.0 / 0.29.0 | REST API 제공 |
| 대시보드 | Streamlit | 1.35.0 | 웹 UI |
| 컨테이너 | Docker + Docker Compose | — | api:8000, ui:8501 배포 |

---

## 7. 모듈별 파일 구조

```
apart_agent/
│
├── etl/                          # Phase 1: ETL 파이프라인
│   ├── dxf_parser.py             # DXF → 블록/삽입 메타데이터 추출
│   ├── batch_converter.py        # DWG → DXF 일괄 변환
│   └── metadata_builder.py       # DXF → JSON 저장 + 배치 처리
│
├── vectordb/                     # 벡터 DB 레이어
│   ├── chroma_store.py           # Chroma CRUD + 하이브리드 검색
│   ├── embedding_builder.py      # 메타데이터 → 자연어 텍스트 변환
│   └── indexer.py                # 전체 인덱싱 CLI 실행기
│
├── agents/                       # Phase 2: LangGraph 에이전트
│   ├── state.py                  # DesignState TypedDict 정의
│   ├── requirement_agent.py      # Agent 1: 요구사항 분석
│   ├── retrieval_agent.py        # Agent 2: RAG 검색
│   ├── drafting_agent.py         # Agent 3: ezdxf 코드 생성
│   ├── verification_agent.py     # Agent 4: 3단계 검증
│   └── graph.py                  # LangGraph 워크플로우 조립
│
├── api/
│   └── main.py                   # FastAPI REST 엔드포인트
│
├── ui/
│   └── dashboard.py              # Streamlit 대시보드
│
├── feedback/                     # Phase 3: 피드백 루프
│   ├── dxf_diff.py               # DXF 변경 사항 감지
│   └── updater.py                # 수정본 → 벡터 DB 반영
│
├── rules/
│   └── constraints.yaml          # 건축 법규 기준 룰셋
│
├── tests/
│   ├── conftest.py               # 공통 픽스처 (샘플 DXF 생성)
│   ├── test_etl.py               # ETL 단위 테스트
│   ├── test_vectordb.py          # 벡터 DB 단위 테스트
│   └── test_agents.py            # 에이전트 단위 테스트
│
├── docs/
│   └── architecture_workflow.md  # 본 보고서
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

*본 보고서는 `apart_agent` 프로젝트의 소스 코드를 기반으로 자동 분석·작성되었습니다.*
