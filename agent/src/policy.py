from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .maintenance_planner import MaintenanceDecision
    from .table_health import (
        ALLOWED_MAINTENANCE_OPERATIONS,
        NO_ACTION,
        REWRITE_DATA_FILES,
        TableHealth,
    )
except ImportError:
    from maintenance_planner import MaintenanceDecision
    from table_health import (
        ALLOWED_MAINTENANCE_OPERATIONS,
        NO_ACTION,
        REWRITE_DATA_FILES,
        TableHealth,
    )


EXECUTABLE_OPERATIONS = {
    NO_ACTION,
    REWRITE_DATA_FILES,
}


@dataclass(frozen=True)
class PolicyResult:
    catalog: str
    namespace: str
    table: str
    operation: str
    approved: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_decision(
    decision: MaintenanceDecision,
    health: TableHealth | dict[str, Any],
    *,
    min_confidence: float = 0.80,
    min_data_files_for_rewrite: int = 10,
) -> PolicyResult:
    payload = health.to_dict() if isinstance(health, TableHealth) else health

    if decision.operation not in ALLOWED_MAINTENANCE_OPERATIONS:
        return _reject(decision, "Operation is not in the canonical maintenance operation set.")

    if decision.operation not in EXECUTABLE_OPERATIONS:
        return _reject(decision, "Operation is recognized but no safe executor is implemented yet.")

    if decision.operation == NO_ACTION:
        return PolicyResult(
            catalog=decision.catalog,
            namespace=decision.namespace,
            table=decision.table,
            operation=decision.operation,
            approved=False,
            reason="No maintenance execution requested.",
        )

    if not decision.should_execute:
        return _reject(decision, "Planner did not request execution.")

    if decision.confidence < min_confidence:
        return _reject(decision, f"Confidence {decision.confidence:.2f} is below {min_confidence:.2f}.")

    data_file_count = int(payload.get("data_file_count", 0))
    if decision.operation == REWRITE_DATA_FILES and data_file_count < min_data_files_for_rewrite:
        return _reject(
            decision,
            f"Only {data_file_count} data files; rewrite_data_files is not worth executing yet.",
        )

    return PolicyResult(
        catalog=decision.catalog,
        namespace=decision.namespace,
        table=decision.table,
        operation=decision.operation,
        approved=True,
        reason="Decision passed deterministic policy validation.",
    )


def _reject(decision: MaintenanceDecision, reason: str) -> PolicyResult:
    return PolicyResult(
        catalog=decision.catalog,
        namespace=decision.namespace,
        table=decision.table,
        operation=decision.operation,
        approved=False,
        reason=reason,
    )
