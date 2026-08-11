from __future__ import annotations

from typing import Any

try:
    from .table_health import TableHealth
except ImportError:
    from table_health import TableHealth


def should_invoke_agent(
    previous: TableHealth | dict[str, Any] | None,
    current: TableHealth | dict[str, Any],
    *,
    small_file_ratio_threshold: float = 0.50,
    min_data_files: int = 10,
    snapshot_count_threshold: int = 100,
    manifest_count_threshold: int = 100,
    delete_file_count_threshold: int = 10,
) -> bool:
    current_payload = current.to_dict() if isinstance(current, TableHealth) else current
    if previous is None:
        return True

    previous_payload = previous.to_dict() if isinstance(previous, TableHealth) else previous

    data_file_count = int(current_payload.get("data_file_count", 0))
    small_file_ratio = float(current_payload.get("small_file_ratio", 0.0))
    snapshot_count = int(current_payload.get("snapshot_count", 0))
    manifest_count = int(current_payload.get("manifest_count", 0))
    delete_file_count = int(current_payload.get("delete_file_count", 0))

    if small_file_ratio >= small_file_ratio_threshold and data_file_count >= min_data_files:
        return True
    if snapshot_count >= snapshot_count_threshold:
        return True
    if manifest_count >= manifest_count_threshold:
        return True
    if delete_file_count >= delete_file_count_threshold:
        return True

    previous_data_file_count = int(previous_payload.get("data_file_count", 0))
    return previous_data_file_count > 0 and data_file_count >= previous_data_file_count * 2
