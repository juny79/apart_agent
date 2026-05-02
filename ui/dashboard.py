"""
ApartAgent Streamlit 대시보드.

실행:
    streamlit run ui/dashboard.py
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (모듈 임포트용)
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")


def _show_error(resp: requests.Response) -> None:
    """API 오류 응답을 화면에 표시합니다."""
    try:
        detail = resp.json().get("detail", {})
        if isinstance(detail, dict):
            st.error(f"생성 실패: {detail.get('message', '알 수 없는 오류')}")
            for err in detail.get("errors", []):
                st.warning(err)
        else:
            st.error(f"생성 실패: {detail}")
    except Exception:
        st.error(f"생성 실패 (HTTP {resp.status_code})")

st.set_page_config(
    page_title="ApartAgent",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# 사이드바: 시스템 정보
# ------------------------------------------------------------------ #
with st.sidebar:
    st.title("ApartAgent")
    st.caption("아파트 인테리어 설계 AI 에이전트")
    st.divider()
    st.subheader("사용 예시")
    examples = [
        "30평형 미니멀 화이트 톤 거실 도면을 그려줘",
        "25평 아파트 아일랜드 주방 배치를 만들어줘",
        "안방 붙박이장과 침대 배치 도면이 필요해",
        "욕실에 욕조와 세면대, 변기를 배치해줘",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    st.caption("API 서버: " + API_URL)

# ------------------------------------------------------------------ #
# 메인 화면
# ------------------------------------------------------------------ #
st.title("건축 설계 AI 에이전트")
st.markdown(
    "자연어로 설계 요청을 입력하면 **ezdxf** 기반 2D CAD 도면(DXF)을 자동으로 생성합니다."
)

prefill = st.session_state.pop("prefill", "")

with st.form("design_form"):
    user_request = st.text_area(
        "설계 요청사항",
        value=prefill,
        placeholder="예: 30평형 아파트, 화이트 톤의 아일랜드 식탁이 있는 주방 도면을 그려줘",
        height=130,
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        submitted = st.form_submit_button("도면 생성", use_container_width=True, type="primary")
    with col2:
        preview_only = st.checkbox("미리보기만 (DXF 다운로드 없이)", value=False)

if submitted:
    if not user_request.strip():
        st.warning("설계 요청사항을 입력해주세요.")
    else:
        with st.spinner("에이전트가 도면을 생성 중입니다... (최대 약 60초 소요)"):
            try:
                if preview_only:
                    resp = requests.post(
                        f"{API_URL}/generate-design/preview",
                        json={"user_request": user_request},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data["verification_passed"]:
                            st.success("도면 생성 성공!")
                        else:
                            st.warning("검증 오류가 있지만 코드가 생성되었습니다.")

                        st.subheader("생성 요약")
                        st.info(data["output_summary"] or "(요약 없음)")
                        st.caption(f"코드 생성 버전: {data['generated_code_version']}")

                        if data["errors"]:
                            with st.expander("검증 오류 목록"):
                                for err in data["errors"]:
                                    st.error(err)
                    else:
                        _show_error(resp)

                else:
                    resp = requests.post(
                        f"{API_URL}/generate-design",
                        json={"user_request": user_request},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        summary = resp.headers.get("X-Summary", "")
                        version = resp.headers.get("X-Code-Version", "1")

                        st.success("도면 생성 완료!")
                        if summary:
                            st.info(f"**생성 요약**: {summary}")
                        st.caption(f"코드 생성 버전: {version}")

                        st.download_button(
                            label="DXF 파일 다운로드",
                            data=resp.content,
                            file_name="generated_design.dxf",
                            mime="application/octet-stream",
                            use_container_width=True,
                        )
                    else:
                        _show_error(resp)

            except requests.exceptions.ConnectionError:
                st.error(
                    f"API 서버({API_URL})에 연결할 수 없습니다. "
                    "서버가 실행 중인지 확인하세요: `uvicorn api.main:app --reload`"
                )
            except requests.exceptions.Timeout:
                st.error("요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
