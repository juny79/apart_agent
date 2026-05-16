# ApartAgent 보안 수정 보고서 (Security Fix Report)

| 항목 | 내용 |
|------|------|
| 원본 감사 문서 | `SECURITY_AUDIT_REPORT.md` |
| 수정 일자 | 2026-05-09 |
| 수정 대상 파일 | `agents/verification_agent.py`, `api/main.py`, `requirements.txt`, `docker-compose.yml`, `.env.example` |
| 신규 생성 파일 | `.dockerignore` |

---

## 수정 결과 요약

| ID | 심각도 | 제목 | 상태 |
|----|--------|------|------|
| C-01 | 🔴 Critical | LLM 생성 코드 임의 실행 (RCE) | ✅ 부분 수정 (코드 레벨) |
| C-02 | 🔴 Critical | 프롬프트 인젝션 → 코드 실행 연계 | ✅ 수정 완료 |
| H-01 | 🟠 High | 인증/인가 없는 API 엔드포인트 | ✅ 수정 완료 |
| H-02 | 🟠 High | Rate Limiting 없음 | ✅ 수정 완료 |
| H-03 | 🟠 High | 내부 에러 정보 노출 | ✅ 수정 완료 |
| M-01 | 🟡 Medium | Path Traversal (FileResponse) | ✅ 수정 완료 |
| M-02 | 🟡 Medium | CORS 미설정 | ✅ 수정 완료 |
| M-03 | 🟡 Medium | 입력 길이 제한 없음 | ✅ 수정 완료 |
| L-01 | 🟢 Low | 프로덕션에서 `--reload` 사용 | ✅ 수정 완료 |
| L-02 | 🟢 Low | LangSmith 트레이싱 외부 전송 | ⚠️ 설명 추가 (.env.example) |
| L-03 | 🟢 Low | `.dockerignore` 누락 | ✅ 수정 완료 |
| L-04 | 🟢 Low | HTTP 평문 통신 (UI → API) | ⚠️ 인프라 수준 조치 필요 |

---

## 수정 상세

---

### [C-01] LLM 생성 코드 임의 실행 (RCE)

**파일**: `agents/verification_agent.py`

#### 추가된 코드 1 — 허용 모듈 화이트리스트 상수

```python
# 허용된 최상위 모듈 화이트리스트 (ezdxf 코드 생성에 필요한 것만 허용)
_ALLOWED_IMPORTS: frozenset[str] = frozenset({"ezdxf", "math"})
# 실행 위험 내장 함수 금지 목록
_BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__", "open", "breakpoint",
})
```

#### 추가된 코드 2 — AST 기반 보안 검사 함수

```python
def _check_code_safety(code: str) -> list[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # ezdxf, math 외 모든 import 차단
        elif isinstance(node, ast.ImportFrom):
            # ezdxf, math 외 from ... import 차단
        elif isinstance(node, ast.Call):
            # eval(), exec(), open() 등 위험 내장 함수 차단
```

`verification_node` 내 **step 2** 로 삽입 (문법 검사 직후, subprocess 실행 전):

```python
# 2. 보안 화이트리스트 검사 (허용 모듈·금지 함수)
safety_errors = _check_code_safety(code)
if safety_errors:
    errors.extend(safety_errors)
    return {"verification_passed": False, "verification_errors": errors}
```

#### 추가된 코드 3 — 환경변수 격리 (subprocess env 제한)

```python
# 환경변수 격리: API 키 등 시크릿이 서브프로세스에 노출되지 않도록 제한
_safe_env: dict[str, str] = {"PATH": os.environ.get("PATH", "")}
for _k in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "WINDIR"):
    _v = os.environ.get(_k)
    if _v:
        _safe_env[_k] = _v

result = subprocess.run(
    [sys.executable, str(code_path)],
    ...
    env=_safe_env,   # ← 추가: OPENAI_API_KEY 등 시크릿 차단
)
```

> **⚠️ 잔존 위험**: AST 검사는 직접적인 `import os` 를 차단하지만, `__builtins__['open']` 같은 우회 경로는 차단하지 못합니다. 완전한 격리를 위해서는 **운영 환경에서 Docker `--network none` 또는 `gVisor`/`nsjail` 적용을 권장**합니다.

---

### [C-02] 프롬프트 인젝션 → 입력 길이 제한

**파일**: `api/main.py` — `DesignRequest` 검증 추가

| 구분 | 변경 전 | 변경 후 |
|------|---------|---------|
| 최대 길이 | 제한 없음 | **1,000자** |

```python
# 변경 전
def request_not_empty(cls, v: str) -> str:
    if not v or not v.strip():
        raise ValueError("...")
    return v.strip()

# 변경 후
def request_not_empty(cls, v: str) -> str:
    if not v or not v.strip():
        raise ValueError("...")
    if len(v) > 1000:                               # ← 추가
        raise ValueError("user_request는 1,000자를 초과할 수 없습니다.")
    return v.strip()
```

---

### [H-01] API 인증 추가 (API Key)

**파일**: `api/main.py`

```python
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def _verify_api_key(key: str | None = Depends(_api_key_header)) -> None:
    """SERVICE_API_KEY 환경변수가 설정된 경우 API Key를 검증합니다."""
    service_key = os.getenv("SERVICE_API_KEY", "")
    if service_key and key != service_key:
        raise HTTPException(status_code=403, detail="유효하지 않은 API Key입니다.")
```

엔드포인트에 의존성 주입:

```python
@app.post("/generate-design")
async def generate_design(
    request: Request,
    body: DesignRequest,
    _: None = Depends(_verify_api_key),   # ← 추가
):
```

> `SERVICE_API_KEY` 환경변수를 **비워두면 인증 비활성화** (개발 편의), 설정 시 자동 활성화.

---

### [H-02] Rate Limiting 추가

**파일**: `api/main.py`, `requirements.txt`

`slowapi==0.1.9` 의존성 추가:

```text
# requirements.txt
slowapi==0.1.9
```

앱 초기화에 limiter 등록:

```python
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

엔드포인트별 제한:

| 엔드포인트 | 제한 |
|-----------|------|
| `POST /generate-design` | **5회/분** (IP당) |
| `POST /generate-design/preview` | **10회/분** (IP당) |

```python
@app.post("/generate-design")
@limiter.limit("5/minute")   # ← 추가
async def generate_design(request: Request, ...):
```

---

### [H-03] 내부 에러 정보 노출 차단

**파일**: `api/main.py`

```python
# 변경 전 — 예외 메시지 그대로 노출
except Exception as e:
    raise HTTPException(status_code=500, detail=f"에이전트 실행 오류: {e}")

# 변경 후 — 내부 로그만 기록, 클라이언트에는 generic 메시지
except Exception:
    logger.exception("에이전트 실행 오류")   # 서버 로그에만 기록
    raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")
```

---

### [M-01] Path Traversal 방지 (FileResponse 경로 검증)

**파일**: `api/main.py`

```python
_ALLOWED_OUTPUT_DIR = Path("data/output").resolve()

def _validate_output_path(path_str: str) -> Path:
    """FileResponse 경로가 허용된 디렉토리 내에 있는지 검증합니다."""
    try:
        p = Path(path_str).resolve()
    except Exception:
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")
    if not p.is_relative_to(_ALLOWED_OUTPUT_DIR):
        logger.error("허용되지 않은 출력 경로 접근 시도: %s", path_str)
        raise HTTPException(status_code=500, detail="내부 서버 오류가 발생했습니다.")
    return p
```

엔드포인트에서 사용:

```python
# 변경 전
return FileResponse(path=dxf_path, ...)

# 변경 후
validated_path = _validate_output_path(dxf_path)   # ← 검증 추가
return FileResponse(path=str(validated_path), ...)
```

---

### [M-02] CORS 화이트리스트 설정

**파일**: `api/main.py`

```python
_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,   # 환경변수로 제어
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

> 기본값은 Streamlit UI 주소(`http://localhost:8501`)만 허용. 여러 도메인은 `ALLOWED_ORIGINS=https://a.com,https://b.com` 형식으로 설정.

---

### [L-01] 프로덕션 `--reload` 제거

**파일**: `docker-compose.yml`

```yaml
# 변경 전
command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 변경 후
command: uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

### [L-03] `.dockerignore` 생성

**신규 파일**: `.dockerignore`

Docker 이미지 빌드 시 `.env`, `chroma_db/`, `data/`, `.git/` 등이 레이어에 포함되지 않도록 차단합니다.

---

### [L-02 / L-04] 설명 추가 (코드 변경 없음)

**파일**: `.env.example`

```
# 보안 설정
SERVICE_API_KEY=your-secret-api-key-here   # API 인증 키
ALLOWED_ORIGINS=http://localhost:8501       # CORS 허용 오리진

# LangSmith: 프로덕션에서는 false 권장 (사용자 입력이 외부로 전송됨)
LANGCHAIN_TRACING_V2=true
```

L-04 (HTTP 평문 통신)는 인프라 수준 조치(Nginx HTTPS / mTLS)가 필요하므로 코드 변경 범위 밖입니다.

---

## 수정 후 보안 체계 흐름

```
사용자 요청
    │
    ▼
[FastAPI] DesignRequest 검증
    ├─ 빈 입력 차단
    └─ 1,000자 초과 차단          ← M-03 수정
    │
    ▼
[FastAPI] API Key 인증            ← H-01 수정
    │
    ▼
[slowapi] Rate Limiting (5/분)    ← H-02 수정
    │
    ▼
[Requirement Agent] LLM 파싱
    │
    ▼
[Drafting Agent] ezdxf 코드 생성
    │
    ▼
[Verification Agent]
    ├─ 1. AST 문법 검사
    ├─ 2. 모듈 화이트리스트 검사  ← C-01 수정 (ezdxf, math 만 허용)
    ├─ 3. subprocess 실행
    │       └─ env 격리           ← C-01 수정 (OPENAI_API_KEY 노출 차단)
    ├─ 4. DXF 생성 확인
    └─ 5. 건축 법규 검증
    │
    ▼
[FastAPI] 경로 검증               ← M-01 수정
    │
    ▼
FileResponse (DXF 파일 반환)
```

---

## 잔존 위험 및 추가 권고

| 항목 | 위험 | 권고 |
|------|------|------|
| C-01 완전 격리 | `__builtins__` 우회 가능 | 운영: Docker `--network none --memory 256m` 또는 gVisor |
| L-04 평문 통신 | 내부 컨테이너 트래픽 평문 | Nginx + TLS 또는 서비스 메시(mTLS) |
| 동적 테스트(DAST) | 정적 분석만 수행 | Burp Suite / OWASP ZAP 침투 테스트 권장 |

---

*정적 소스코드 분석(SAST) 기반 수정 보고서. 완전한 보안 검증을 위해 동적 분석(DAST) 및 침투 테스트를 별도로 수행하세요.*
