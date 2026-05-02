"""
에이전트 3: Drafting Agent (Code Generator)
검색된 블록 정보를 바탕으로 실행 가능한 ezdxf Python 코드를 생성합니다.
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agents.state import DesignState

DRAFTING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 ezdxf 라이브러리 전문 건축 CAD 코딩 에이전트입니다.
주어진 요구사항과 검색된 CAD 블록 정보를 바탕으로,
실행 가능한 Python (ezdxf) 코드를 생성하세요.

[코드 작성 규칙]
1. 반드시 `import ezdxf` 로 시작하세요.
2. `doc = ezdxf.new(dxfversion="R2018")` 로 새 도면을 생성하세요.
3. `msp = doc.modelspace()` 로 모델 공간을 얻으세요.
4. 모든 좌표는 밀리미터(mm) 단위를 사용하세요.
5. 레이어 이름은 AIA CAD Layer 컨벤션을 따르세요:
   - 벽: A-WALL, 문: A-DOOR, 창문: A-GLAZ, 가구: A-FURN, 주방기기: A-EQPM
6. 레이어 생성 시 `doc.layers.new(name="...", dxfattribs={{"color": N}})` 를 사용하세요.
7. 직선은 `msp.add_line(start, end, dxfattribs={{"layer": "..."}})` 로 그리세요.
8. 호(Arc)는 `msp.add_arc(center, radius, start_angle, end_angle)` 를 사용하세요.
9. 문의 열림 방향은 호(Arc)로 표현하세요.
10. 마지막에 반드시 `doc.saveas("output.dxf")` 를 포함하세요.
11. 코드만 반환하세요 (설명, 주석, 마크다운 코드블록 없이).

[이전 검증 오류 - 반드시 수정하세요]
{verification_errors}
"""),
    ("human", """[요구사항]
{parsed_requirements}

[검색된 블록 참고 정보]
{retrieved_blocks}

[유사 레이아웃 참고]
{retrieved_layouts}

위 정보를 바탕으로 ezdxf Python 코드를 생성하세요.
블록 참고 정보에서 치수를 활용하여 현실적인 배치를 구현하세요.
"""),
])


def drafting_node(state: DesignState) -> dict:
    """ezdxf Python 코드를 생성합니다."""
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    chain = DRAFTING_PROMPT | llm

    errors_text = "\n".join(state.get("verification_errors", [])) or "없음"

    response = chain.invoke({
        "parsed_requirements": str(state["parsed_requirements"]),
        "retrieved_blocks": str(state["retrieved_blocks"]),
        "retrieved_layouts": str(state["retrieved_layouts"]),
        "verification_errors": errors_text,
    })

    code = response.content.strip()

    # 마크다운 코드 블록 제거
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]

    version = state.get("generated_code_version", 0) + 1
    return {
        "generated_code": code.strip(),
        "generated_code_version": version,
    }
