from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .maintenance_planner import MaintenanceDecision
    from .policy import PolicyResult
    from .table_health import NO_ACTION, REWRITE_DATA_FILES
except ImportError:
    from maintenance_planner import MaintenanceDecision
    from policy import PolicyResult
    from table_health import NO_ACTION, REWRITE_DATA_FILES


@dataclass(frozen=True)
class ExecutionResult:
    catalog: str
    namespace: str
    table: str
    operation: str
    status: str
    sql: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_decision(
    spark: Any,
    decision: MaintenanceDecision,
    policy_result: PolicyResult,
) -> ExecutionResult:
    if not policy_result.approved:
        return ExecutionResult(
            catalog=decision.catalog,
            namespace=decision.namespace,
            table=decision.table,
            operation=decision.operation,
            status="SKIPPED",
            sql=None,
            message=policy_result.reason,
        )

    if decision.operation == NO_ACTION:
        return ExecutionResult(
            catalog=decision.catalog,
            namespace=decision.namespace,
            table=decision.table,
            operation=decision.operation,
            status="SKIPPED",
            sql=None,
            message="No action requested.",
        )

    if decision.operation == REWRITE_DATA_FILES:
        table_arg = f"{decision.namespace}.{decision.table}"
        sql = (
            f"CALL {decision.catalog}.system.rewrite_data_files("
            f"table => '{table_arg}'"
            ")"
        )
        spark.sql(sql).collect()
        return ExecutionResult(
            catalog=decision.catalog,
            namespace=decision.namespace,
            table=decision.table,
            operation=decision.operation,
            status="SUCCEEDED",
            sql=sql,
            message="rewrite_data_files completed.",
        )

    return ExecutionResult(
        catalog=decision.catalog,
        namespace=decision.namespace,
        table=decision.table,
        operation=decision.operation,
        status="FAILED",
        sql=None,
        message="No executor is implemented for this operation.",
    )
