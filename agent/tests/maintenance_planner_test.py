import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.src.maintenance_planner import (
    DEFAULT_MODEL,
    build_planning_prompt,
    parse_maintenance_decisions,
    plan_maintenance,
    _resolve_model,
)
from agent.src.maintenance_graph import run_planning_graph


class BindableFakeChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def table_health_payload() -> dict:
    return {
        "catalog": "lakehouse",
        "namespace": "demo",
        "table": "events",
        "snapshot_count": 1,
        "data_file_count": 3,
        "delete_file_count": 0,
        "total_data_file_size_bytes": 2958,
        "avg_data_file_size_bytes": 986.0,
        "min_data_file_size_bytes": 986,
        "max_data_file_size_bytes": 986,
        "target_file_size_bytes": 536870912,
        "small_file_count": 3,
        "small_file_ratio": 1.0,
        "manifest_count": 1,
        "orphan_file_count": None,
        "recommendation": {
            "operation": "REWRITE_DATA_FILES",
            "reason": "The table contains a high ratio of data files below the target size.",
            "priority": "HIGH",
            "confidence": 0.95,
        },
    }


def decision_response() -> str:
    return json.dumps(
        {
            "decisions": [
                {
                    "catalog": "lakehouse",
                    "namespace": "demo",
                    "table": "events",
                    "operation": "REWRITE_DATA_FILES",
                    "priority": "HIGH",
                    "confidence": 0.94,
                    "should_execute": True,
                    "rationale": "All data files are far below the configured target size.",
                    "action": "Run Iceberg rewrite_data_files with binpack strategy.",
                    "validation": "Collect table health again and verify small_file_ratio decreased.",
                }
            ]
        }
    )


def test_build_planning_prompt_includes_metrics_and_schema() -> None:
    prompt = build_planning_prompt([table_health_payload()])

    assert "small_file_ratio" in prompt
    assert "REWRITE_DATA_FILES" in prompt
    assert "REWRITE_MANIFESTS" in prompt
    assert "REMOVE_ORPHAN_FILES" in prompt
    assert "REWRITE_POSITION_DELETE_FILES" in prompt
    assert '"decisions"' in prompt


def test_parse_maintenance_decisions() -> None:
    decisions = parse_maintenance_decisions(decision_response())

    assert len(decisions) == 1
    assert decisions[0].operation == "REWRITE_DATA_FILES"
    assert decisions[0].should_execute is True


def test_parse_maintenance_decisions_from_fenced_json() -> None:
    decisions = parse_maintenance_decisions(f"```json\n{decision_response()}\n```")

    assert len(decisions) == 1
    assert decisions[0].operation == "REWRITE_DATA_FILES"


def test_plan_maintenance_with_fake_model(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    model = BindableFakeChatModel(responses=[decision_response()])

    decisions = plan_maintenance([table_health_payload()], model=model)

    assert len(decisions) == 1
    assert decisions[0].table == "events"
    assert decisions[0].priority == "HIGH"


def test_run_planning_graph_with_fake_model(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    model = BindableFakeChatModel(responses=[decision_response()])

    decisions = run_planning_graph([table_health_payload()], model=model)

    assert len(decisions) == 1
    assert decisions[0].operation == "REWRITE_DATA_FILES"


def test_blank_openai_model_env_uses_default_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "")

    assert _resolve_model(None) == DEFAULT_MODEL
    assert _resolve_model("") == DEFAULT_MODEL
