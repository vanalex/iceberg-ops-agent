import sqlite3

from agent.src.maintenance_planner import MaintenanceDecision
from agent.src.operations import ExecutionResult
from agent.src.persistence import MaintenanceStore
from agent.src.policy import PolicyResult
from agent.src.table_health import MaintenanceRecommendation, TableHealth
from agent.src.verification import VerificationResult


def table_health() -> TableHealth:
    return TableHealth(
        catalog="lakehouse",
        namespace="demo",
        table="events",
        snapshot_count=1,
        data_file_count=3,
        delete_file_count=0,
        total_data_file_size_bytes=2958,
        avg_data_file_size_bytes=986.0,
        min_data_file_size_bytes=986,
        max_data_file_size_bytes=986,
        target_file_size_bytes=536870912,
        small_file_count=3,
        small_file_ratio=1.0,
        manifest_count=1,
        orphan_file_count=None,
        recommendation=MaintenanceRecommendation(
            operation="REWRITE_DATA_FILES",
            reason="The table contains a high ratio of data files below the target size.",
            priority="HIGH",
            confidence=0.95,
        ),
    )


def maintenance_decision() -> MaintenanceDecision:
    return MaintenanceDecision(
        catalog="lakehouse",
        namespace="demo",
        table="events",
        operation="REWRITE_DATA_FILES",
        priority="LOW",
        confidence=0.75,
        should_execute=True,
        rationale="All data files are small, but the table has few files.",
        action="Run Iceberg rewrite_data_files when convenient.",
        validation="Collect table health again and compare file-size metrics.",
    )


def test_store_persists_health_observations_and_decisions(tmp_path) -> None:
    database_path = tmp_path / "maintenance.db"
    store = MaintenanceStore(database_path)

    store.save_health_observations([table_health()])
    store.save_decisions([maintenance_decision()])
    store.save_policy_results(
        [
            PolicyResult(
                catalog="lakehouse",
                namespace="demo",
                table="events",
                operation="REWRITE_DATA_FILES",
                approved=True,
                reason="Approved.",
            )
        ]
    )
    store.save_execution_results(
        [
            ExecutionResult(
                catalog="lakehouse",
                namespace="demo",
                table="events",
                operation="REWRITE_DATA_FILES",
                status="SUCCEEDED",
                sql="CALL lakehouse.system.rewrite_data_files(table => 'demo.events')",
                message="Done.",
            )
        ]
    )
    store.save_verification_results(
        [
            VerificationResult(
                catalog="lakehouse",
                namespace="demo",
                table="events",
                operation="REWRITE_DATA_FILES",
                status="SUCCEEDED",
                succeeded=True,
                reason="Improved.",
            )
        ]
    )

    with sqlite3.connect(database_path) as connection:
        health_count = connection.execute(
            "SELECT count(*) FROM table_health_observations"
        ).fetchone()[0]
        decision_count = connection.execute(
            "SELECT count(*) FROM maintenance_decisions"
        ).fetchone()[0]
        decision_operation = connection.execute(
            "SELECT operation FROM maintenance_decisions"
        ).fetchone()[0]
        policy_count = connection.execute(
            "SELECT count(*) FROM maintenance_policy_results"
        ).fetchone()[0]
        execution_count = connection.execute(
            "SELECT count(*) FROM maintenance_executions"
        ).fetchone()[0]
        verification_count = connection.execute(
            "SELECT count(*) FROM maintenance_verifications"
        ).fetchone()[0]

    assert health_count == 1
    assert decision_count == 1
    assert decision_operation == "REWRITE_DATA_FILES"
    assert policy_count == 1
    assert execution_count == 1
    assert verification_count == 1
