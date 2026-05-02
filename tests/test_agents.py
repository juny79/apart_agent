"""
tests/test_agents.py — 에이전트 모듈 단위 테스트.
"""
import json
from unittest.mock import MagicMock, patch

import ezdxf
import pytest

from agents.state import DesignState
from agents.verification_agent import _check_constraints, CONSTRAINT_RULES


# ------------------------------------------------------------------ #
# 헬퍼: 기본 DesignState 생성
# ------------------------------------------------------------------ #
def make_state(**kwargs) -> DesignState:
    defaults = DesignState(
        user_request="30평 미니멀 거실 도면",
        parsed_requirements={},
        retrieved_blocks=[],
        retrieved_layouts=[],
        generated_code="",
        generated_code_version=0,
        verification_passed=False,
        verification_errors=[],
        output_dxf_path="",
        output_summary="",
    )
    defaults.update(kwargs)
    return defaults


# ------------------------------------------------------------------ #
# Requirement Analysis Agent
# ------------------------------------------------------------------ #
class TestRequirementAgent:
    @patch("agents.requirement_agent.ChatOpenAI")
    def test_returns_parsed_requirements(self, mock_llm_cls):
        from agents.requirement_agent import requirement_analysis_node

        expected = {
            "apartment_size_pyeong": 30,
            "target_space": "living_room",
            "style_keywords": ["minimalist"],
            "required_blocks": ["sofa", "tv_wall"],
            "budget_tier": "mid",
            "special_requirements": "",
        }
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content=json.dumps(expected))

        with patch("agents.requirement_agent.REQUIREMENT_PROMPT.__or__", return_value=mock_chain):
            result = requirement_analysis_node(make_state())

        assert result["parsed_requirements"]["apartment_size_pyeong"] == 30
        assert result["parsed_requirements"]["target_space"] == "living_room"

    @patch("agents.requirement_agent.ChatOpenAI")
    def test_handles_json_parse_error_with_fallback(self, mock_llm_cls):
        from agents.requirement_agent import requirement_analysis_node

        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content="이것은 JSON이 아닙니다.")

        with patch("agents.requirement_agent.REQUIREMENT_PROMPT.__or__", return_value=mock_chain):
            result = requirement_analysis_node(make_state())

        # 파싱 실패 시 기본값 반환
        assert "target_space" in result["parsed_requirements"]
        assert result["parsed_requirements"]["target_space"] == "whole"


# ------------------------------------------------------------------ #
# Drafting Agent
# ------------------------------------------------------------------ #
class TestDraftingAgent:
    @patch("agents.drafting_agent.ChatOpenAI")
    def test_strips_markdown_fences(self, mock_llm_cls):
        from agents.drafting_agent import drafting_node

        raw_code = "import ezdxf\ndoc = ezdxf.new()\ndoc.saveas('output.dxf')"
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(
            content=f"```python\n{raw_code}\n```"
        )

        with patch("agents.drafting_agent.DRAFTING_PROMPT.__or__", return_value=mock_chain):
            result = drafting_node(make_state(parsed_requirements={"target_space": "kitchen"}))

        assert result["generated_code"] == raw_code
        assert result["generated_code_version"] == 1

    @patch("agents.drafting_agent.ChatOpenAI")
    def test_increments_version(self, mock_llm_cls):
        from agents.drafting_agent import drafting_node

        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content="import ezdxf")

        with patch("agents.drafting_agent.DRAFTING_PROMPT.__or__", return_value=mock_chain):
            result = drafting_node(make_state(generated_code_version=2))

        assert result["generated_code_version"] == 3


# ------------------------------------------------------------------ #
# Verification Agent
# ------------------------------------------------------------------ #
class TestVerificationAgent:
    def test_constraint_rules_keys(self):
        assert "min_door_width_mm" in CONSTRAINT_RULES
        assert "min_corridor_width_mm" in CONSTRAINT_RULES
        assert "max_code_retries" in CONSTRAINT_RULES

    def test_constraint_rules_values_positive(self):
        for key, value in CONSTRAINT_RULES.items():
            assert value > 0, f"{key} should be positive"

    def test_check_constraints_empty_dxf(self, tmp_path):
        """빈 DXF는 제약 조건 위반 없음."""
        doc = ezdxf.new()
        dxf_path = tmp_path / "empty.dxf"
        doc.saveas(str(dxf_path))
        errors = _check_constraints(dxf_path)
        assert errors == []

    def test_check_constraints_valid_door(self, tmp_path):
        """최소 폭 이상의 문은 위반 없음."""
        doc = ezdxf.new()
        door_block = doc.blocks.new(name="DOOR_OK_01")
        door_block.add_line((0, 0), (900, 0))
        msp = doc.modelspace()
        msp.add_blockref("DOOR_OK_01", insert=(0, 0))
        dxf_path = tmp_path / "valid_door.dxf"
        doc.saveas(str(dxf_path))
        errors = _check_constraints(dxf_path)
        assert errors == []

    def test_check_constraints_narrow_door(self, tmp_path):
        """최소 폭 미만의 문은 법규 위반 오류 발생."""
        doc = ezdxf.new()
        door_block = doc.blocks.new(name="DOOR_NARROW_01")
        door_block.add_line((0, 0), (500, 0))  # 500mm < 750mm 최소 기준
        msp = doc.modelspace()
        msp.add_blockref("DOOR_NARROW_01", insert=(0, 0))
        dxf_path = tmp_path / "narrow_door.dxf"
        doc.saveas(str(dxf_path))
        errors = _check_constraints(dxf_path)
        assert len(errors) >= 1
        assert "법규 위반" in errors[0]


# ------------------------------------------------------------------ #
# LangGraph 워크플로우 조립
# ------------------------------------------------------------------ #
class TestGraphBuild:
    def test_build_graph_returns_compiled(self):
        from agents.graph import build_graph
        graph = build_graph()
        assert graph is not None

    def test_create_initial_state(self):
        from agents.graph import create_initial_state
        state = create_initial_state("테스트 요청")
        assert state["user_request"] == "테스트 요청"
        assert state["generated_code_version"] == 0
        assert state["verification_passed"] is False
        assert state["verification_errors"] == []
