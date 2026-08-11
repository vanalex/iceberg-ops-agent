from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .table_health import REWRITE_DATA_FILES, TableHealth
except ImportError:
    from table_health import REWRITE_DATA_FILES, TableHealth


@dataclass(frozen=True)
class CostEstimate:
    cost: str
    benefit: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "cost": self.cost,
            "benefit": self.benefit,
            "reason": self.reason,
        }


def estimate_operation_cost(
    health: TableHealth | dict[str, Any],
    operation: str,
) -> CostEstimate:
    payload = health.to_dict() if isinstance(health, TableHealth) else health
    data_file_count = int(payload.get("data_file_count", 0))
    small_file_ratio = float(payload.get("small_file_ratio", 0.0))

    if operation == REWRITE_DATA_FILES:
        if data_file_count >= 1_000:
            cost = "HIGH"
        elif data_file_count >= 100:
            cost = "MEDIUM"
        else:
            cost = "LOW"

        if small_file_ratio >= 0.75 and data_file_count >= 100:
            benefit = "HIGH"
        elif small_file_ratio >= 0.50 and data_file_count >= 10:
            benefit = "MEDIUM"
        else:
            benefit = "LOW"

        return CostEstimate(
            cost=cost,
            benefit=benefit,
            reason="Estimated from data_file_count and small_file_ratio.",
        )

    return CostEstimate(
        cost="UNKNOWN",
        benefit="UNKNOWN",
        reason="No cost model is implemented for this operation yet.",
    )
