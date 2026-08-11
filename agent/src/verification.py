from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .operations import ExecutionResult
    from .table_health import NO_ACTION, REWRITE_DATA_FILES, TableHealth
except ImportError:
    from operations import ExecutionResult
    from table_health import NO_ACTION, REWRITE_DATA_FILES, TableHealth


@dataclass(frozen=True)
class VerificationResult:
    catalog: str
    namespace: str
    table: str
    operation: str
    status: str
    succeeded: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_execution(
    before: TableHealth,
    after: TableHealth | None,
    execution: ExecutionResult,
) -> VerificationResult:
    if execution.status == "SKIPPED":
        return VerificationResult(
            catalog=execution.catalog,
            namespace=execution.namespace,
            table=execution.table,
            operation=execution.operation,
            status="SKIPPED",
            succeeded=False,
            reason=execution.message,
        )

    if execution.status != "SUCCEEDED":
        return VerificationResult(
            catalog=execution.catalog,
            namespace=execution.namespace,
            table=execution.table,
            operation=execution.operation,
            status="FAILED",
            succeeded=False,
            reason=execution.message,
        )

    if after is None:
        return VerificationResult(
            catalog=execution.catalog,
            namespace=execution.namespace,
            table=execution.table,
            operation=execution.operation,
            status="UNKNOWN",
            succeeded=False,
            reason="No post-maintenance health metrics were collected.",
        )

    if execution.operation == REWRITE_DATA_FILES:
        improved = (
            after.small_file_ratio < before.small_file_ratio
            or after.data_file_count < before.data_file_count
            or (
                after.avg_data_file_size_bytes is not None
                and before.avg_data_file_size_bytes is not None
                and after.avg_data_file_size_bytes > before.avg_data_file_size_bytes
            )
        )
        return VerificationResult(
            catalog=execution.catalog,
            namespace=execution.namespace,
            table=execution.table,
            operation=execution.operation,
            status="SUCCEEDED" if improved else "NO_IMPROVEMENT",
            succeeded=improved,
            reason=(
                "Post-maintenance metrics improved."
                if improved
                else "Execution completed but file metrics did not improve."
            ),
        )

    if execution.operation == NO_ACTION:
        return VerificationResult(
            catalog=execution.catalog,
            namespace=execution.namespace,
            table=execution.table,
            operation=execution.operation,
            status="SKIPPED",
            succeeded=False,
            reason="No action was executed.",
        )

    return VerificationResult(
        catalog=execution.catalog,
        namespace=execution.namespace,
        table=execution.table,
        operation=execution.operation,
        status="UNKNOWN",
        succeeded=False,
        reason="No verifier is implemented for this operation.",
    )
