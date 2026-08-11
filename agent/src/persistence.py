from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

try:
    from .maintenance_planner import MaintenanceDecision
    from .operations import ExecutionResult
    from .policy import PolicyResult
    from .table_health import TableHealth
    from .verification import VerificationResult
except ImportError:
    from maintenance_planner import MaintenanceDecision
    from operations import ExecutionResult
    from policy import PolicyResult
    from table_health import TableHealth
    from verification import VerificationResult


SCHEMA = """
CREATE TABLE IF NOT EXISTS table_health_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    catalog TEXT NOT NULL,
    namespace TEXT NOT NULL,
    table_name TEXT NOT NULL,
    snapshot_count INTEGER NOT NULL,
    data_file_count INTEGER NOT NULL,
    delete_file_count INTEGER NOT NULL,
    manifest_count INTEGER NOT NULL,
    orphan_file_count INTEGER,
    small_file_count INTEGER NOT NULL,
    small_file_ratio REAL NOT NULL,
    avg_data_file_size_bytes REAL,
    target_file_size_bytes INTEGER,
    recommendation_operation TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_table_observed_at
ON table_health_observations (catalog, namespace, table_name, observed_at);

CREATE TABLE IF NOT EXISTS maintenance_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    catalog TEXT NOT NULL,
    namespace TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    priority TEXT NOT NULL,
    confidence REAL NOT NULL,
    should_execute INTEGER NOT NULL,
    rationale TEXT NOT NULL,
    action TEXT NOT NULL,
    validation TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_table_created_at
ON maintenance_decisions (catalog, namespace, table_name, created_at);

CREATE TABLE IF NOT EXISTS maintenance_policy_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    catalog TEXT NOT NULL,
    namespace TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    approved INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    catalog TEXT NOT NULL,
    namespace TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    sql TEXT,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    catalog TEXT NOT NULL,
    namespace TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    succeeded INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class MaintenanceStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def save_health_observations(self, health_results: Iterable[TableHealth]) -> None:
        self.initialize()
        rows = []
        for health in health_results:
            payload = health.to_dict()
            rows.append(
                (
                    health.catalog,
                    health.namespace,
                    health.table,
                    health.snapshot_count,
                    health.data_file_count,
                    health.delete_file_count,
                    health.manifest_count,
                    health.orphan_file_count,
                    health.small_file_count,
                    health.small_file_ratio,
                    health.avg_data_file_size_bytes,
                    health.target_file_size_bytes,
                    health.recommendation.operation,
                    json.dumps(payload, sort_keys=True),
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO table_health_observations (
                    catalog,
                    namespace,
                    table_name,
                    snapshot_count,
                    data_file_count,
                    delete_file_count,
                    manifest_count,
                    orphan_file_count,
                    small_file_count,
                    small_file_ratio,
                    avg_data_file_size_bytes,
                    target_file_size_bytes,
                    recommendation_operation,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_decisions(self, decisions: Iterable[MaintenanceDecision]) -> None:
        self.initialize()
        rows = []
        for decision in decisions:
            payload = decision.to_dict()
            rows.append(
                (
                    decision.catalog,
                    decision.namespace,
                    decision.table,
                    decision.operation,
                    decision.priority,
                    decision.confidence,
                    int(decision.should_execute),
                    decision.rationale,
                    decision.action,
                    decision.validation,
                    json.dumps(payload, sort_keys=True),
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO maintenance_decisions (
                    catalog,
                    namespace,
                    table_name,
                    operation,
                    priority,
                    confidence,
                    should_execute,
                    rationale,
                    action,
                    validation,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_policy_results(self, policy_results: Iterable[PolicyResult]) -> None:
        self.initialize()
        rows = []
        for result in policy_results:
            payload = result.to_dict()
            rows.append(
                (
                    result.catalog,
                    result.namespace,
                    result.table,
                    result.operation,
                    int(result.approved),
                    result.reason,
                    json.dumps(payload, sort_keys=True),
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO maintenance_policy_results (
                    catalog, namespace, table_name, operation, approved, reason, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_execution_results(self, execution_results: Iterable[ExecutionResult]) -> None:
        self.initialize()
        rows = []
        for result in execution_results:
            payload = result.to_dict()
            rows.append(
                (
                    result.catalog,
                    result.namespace,
                    result.table,
                    result.operation,
                    result.status,
                    result.sql,
                    result.message,
                    json.dumps(payload, sort_keys=True),
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO maintenance_executions (
                    catalog, namespace, table_name, operation, status, sql, message, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_verification_results(
        self,
        verification_results: Iterable[VerificationResult],
    ) -> None:
        self.initialize()
        rows = []
        for result in verification_results:
            payload = result.to_dict()
            rows.append(
                (
                    result.catalog,
                    result.namespace,
                    result.table,
                    result.operation,
                    result.status,
                    int(result.succeeded),
                    result.reason,
                    json.dumps(payload, sort_keys=True),
                )
            )

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO maintenance_verifications (
                    catalog, namespace, table_name, operation, status, succeeded, reason, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def latest_health_payloads(self) -> dict[tuple[str, str, str], dict]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT h.catalog, h.namespace, h.table_name, h.payload_json
                FROM table_health_observations h
                JOIN (
                    SELECT catalog, namespace, table_name, max(observed_at) AS observed_at
                    FROM table_health_observations
                    GROUP BY catalog, namespace, table_name
                ) latest
                ON h.catalog = latest.catalog
                AND h.namespace = latest.namespace
                AND h.table_name = latest.table_name
                AND h.observed_at = latest.observed_at
                """
            ).fetchall()
        return {
            (catalog, namespace, table): json.loads(payload)
            for catalog, namespace, table, payload in rows
        }

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
