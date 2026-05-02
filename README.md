# ApartAgent

아파트 인테리어 설계 자동화 멀티 에이전트 시스템

자연어 요청을 받아 `ezdxf` Python 코드로 2D CAD 도면(DXF)을 자동 생성합니다.

## 빠른 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 입력

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 기존 DXF 파일 인덱싱 (data/dxf/ 에 DXF 파일 배치 후)
python -m vectordb.indexer --metadata-dir data/metadata --db-dir chroma_db

# 4. API 서버 실행
uvicorn api.main:app --reload

# 5. 대시보드 실행 (별도 터미널)
streamlit run ui/dashboard.py
```

## Docker로 실행

```bash
cp .env.example .env   # OPENAI_API_KEY 입력 후
docker-compose up --build
```

- API: http://localhost:8000/docs
- 대시보드: http://localhost:8501

## 프로젝트 구조

```
apart_agent/
├── etl/            # DWG/DXF 파싱 및 메타데이터 추출
├── vectordb/       # Chroma 벡터 DB CRUD 및 인덱서
├── agents/         # LangGraph 멀티 에이전트 (4개 에이전트)
├── api/            # FastAPI 백엔드
├── ui/             # Streamlit 대시보드
├── feedback/       # DXF Diff 기반 피드백 루프
├── rules/          # 건축 법규 룰셋 YAML
├── data/           # 원본 DWG/DXF 및 메타데이터
└── tests/          # pytest 단위/통합 테스트
```

## ETL 파이프라인

```bash
# DWG → DXF 변환 (ODA File Converter 설치 필요)
python -m etl.batch_converter --input-dir data/raw_dwg --output-dir data/dxf

# DXF → JSON 메타데이터 추출
python -m etl.metadata_builder --dxf-dir data/dxf --output-dir data/metadata

# 메타데이터 → 벡터 DB 인덱싱
python -m vectordb.indexer --metadata-dir data/metadata --db-dir chroma_db
```

## 피드백 루프

```bash
python -m feedback.updater \
    --original data/dxf/generated.dxf \
    --revised  data/dxf/revised_by_designer.dxf \
    --space-id SPACE_project_A104
```

## 테스트

```bash
pytest tests/ -v
```
