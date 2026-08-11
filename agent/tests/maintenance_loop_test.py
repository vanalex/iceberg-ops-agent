import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.src.maintenance_graph import run_maintenance_graph
from agent.src.maintenance_planner import MaintenanceDecision
from agent.src.operations import execute_decision
from agent.src.policy import validate_decision
from agent.src.table_health import MaintenanceRecommendation, TableHealth
from agent.src.triggers import should_invoke_agent
from agent.src.verification import verify_execution


class BindableFakeChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


class FakeSpark:
    def __init__(self) -> None:
        self.statements = []

    def sql(self, statement: str):
        self.statements.append(statement)
        return self

    def collect(self):
        return []


def table_health(data_file_count: int = 20, small_file_ratio: float = 0.8) -> TableHealth:
    return TableHealth(
        catalog="lakehouse",
        namespace="demo",
        table="events",
        snapshot_count=1,
        data_file_count=data_file_count,
        delete_file_count=0,
        total_data_file_size_bytes=2958,
        avg_data_file_size_bytes=986.0,
        min_data_file_size_bytes=986,
        max_data_file_size_bytes=986,
        target_file_size_bytes=536870912,
        small_file_count=int(data_file_count * small_file_ratio),
        small_file_ratio=small_file_ratio,
        manifest_count=1,
        orphan_file_count=None,
        recommendation=MaintenanceRecommendation(
            operation="REWRITE_DATA_FILES",
            reason="The table contains a high ratio of data files below the target size.",
            priority="HIGH",
            confidence=0.95,
        ),
    )


def decision(
    *,
    operation: str = "REWRITE_DATA_FILES",
    confidence: float = 0.94,
    should_execute: bool = True,
) -> MaintenanceDecision:
    return MaintenanceDecision(
        catalog="lakehouse",
        namespace="demo",
        table="events",
        operation=operation,
        priority="HIGH",
        confidence=confidence,
        should_execute=should_execute,
        rationale="The table contains many small files.",
        action="Run Iceberg rewrite_data_files.",
        validation="Collect table health again.",
    )


def decision_response() -> str:
    return json.dumps({"decisions": [decision().to_dict()]})


def test_policy_approves_confident_data_file_rewrite() -> None:
    result = validate_decision(decision(), table_health())

    assert result.approved is True


def test_policy_rejects_low_value_compaction() -> None:
    result = validate_decision(decision(), table_health(data_file_count=3))

    assert result.approved is False
    assert "not worth executing" in result.reason


def test_executor_runs_hardcoded_rewrite_data_files_sql() -> None:
    spark = FakeSpark()
    approved = validate_decision(decision(), table_health())

    result = execute_decision(spark, decision(), approved)

    assert result.status == "SUCCEEDED"
    assert spark.statements == [
        "CALL lakehouse.system.rewrite_data_files(table => 'demo.events')"
    ]


def test_verifier_reports_data_file_improvement() -> None:
    spark = FakeSpark()
    before = table_health(data_file_count=20, small_file_ratio=0.8)
    after = table_health(data_file_count=4, small_file_ratio=0.1)
    execution = execute_decision(spark, decision(), validate_decision(decision(), before))

    result = verify_execution(before, after, execution)

    assert result.succeeded is True


def test_adaptive_trigger_ignores_healthy_stable_table() -> None:
    previous = table_health(data_file_count=5, small_file_ratio=0.1)
    current = table_health(data_file_count=5, small_file_ratio=0.1)

    assert should_invoke_agent(previous, current) is False


def test_full_graph_without_spark_plans_and_skips_execution(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    model = BindableFakeChatModel(responses=[decision_response()])

    result = run_maintenance_graph([table_health()], model=model)

    assert len(result["decisions"]) == 1
    assert result["policy_results"][0].approved is True
    assert result["execution_results"][0].status == "SKIPPED"
    assert result["verification_results"][0].status == "SKIPPED"
