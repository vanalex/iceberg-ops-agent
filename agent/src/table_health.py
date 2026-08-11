from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

NO_ACTION = "NO_ACTION"
REWRITE_DATA_FILES = "REWRITE_DATA_FILES"
REWRITE_MANIFESTS = "REWRITE_MANIFESTS"
EXPIRE_SNAPSHOTS = "EXPIRE_SNAPSHOTS"
REMOVE_ORPHAN_FILES = "REMOVE_ORPHAN_FILES"
REWRITE_POSITION_DELETE_FILES = "REWRITE_POSITION_DELETE_FILES"

ALLOWED_MAINTENANCE_OPERATIONS = {
    NO_ACTION,
    REWRITE_DATA_FILES,
    REWRITE_MANIFESTS,
    EXPIRE_SNAPSHOTS,
    REMOVE_ORPHAN_FILES,
    REWRITE_POSITION_DELETE_FILES,
}


@dataclass(frozen=True)
class TableIdentifier:
    catalog: str
    namespace: str
    table: str

    @property
    def sql_identifier(self) -> str:
        return f"{self.catalog}.{self.namespace}.{self.table}"


@dataclass(frozen=True)
class MaintenanceRecommendation:
    operation: str
    reason: str
    priority: str
    confidence: float


@dataclass(frozen=True)
class TableHealth:
    catalog: str
    namespace: str
    table: str
    snapshot_count: int
    data_file_count: int
    delete_file_count: int
    total_data_file_size_bytes: int
    avg_data_file_size_bytes: float | None
    min_data_file_size_bytes: int | None
    max_data_file_size_bytes: int | None
    target_file_size_bytes: int | None
    small_file_count: int
    small_file_ratio: float
    manifest_count: int
    orphan_file_count: int | None
    recommendation: MaintenanceRecommendation

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TableHealthCollector:
    def __init__(
        self,
        spark: Any,
        catalog: str,
        *,
        small_file_ratio_threshold: float = 0.50,
        small_file_size_ratio: float = 0.25,
        min_data_files_for_compaction: int = 2,
        snapshot_count_threshold: int = 100,
        delete_file_count_threshold: int = 10,
        manifest_count_threshold: int = 100,
        orphan_file_count_threshold: int = 1,
    ) -> None:
        self.spark = spark
        self.catalog = catalog
        self.small_file_ratio_threshold = small_file_ratio_threshold
        self.small_file_size_ratio = small_file_size_ratio
        self.min_data_files_for_compaction = min_data_files_for_compaction
        self.snapshot_count_threshold = snapshot_count_threshold
        self.delete_file_count_threshold = delete_file_count_threshold
        self.manifest_count_threshold = manifest_count_threshold
        self.orphan_file_count_threshold = orphan_file_count_threshold

    def scan(self) -> list[TableHealth]:
        health_results = []
        for table_identifier in self.discover_tables():
            health_results.append(self.collect_table_health(table_identifier))
        return health_results

    def discover_namespaces(self) -> list[str]:
        rows = self.spark.sql(f"SHOW NAMESPACES IN {self.catalog}").collect()
        return sorted(row["namespace"] for row in rows)

    def discover_tables(self) -> list[TableIdentifier]:
        tables = []
        for namespace in self.discover_namespaces():
            rows = self.spark.sql(f"SHOW TABLES IN {self.catalog}.{namespace}").collect()
            for row in rows:
                if row["isTemporary"]:
                    continue
                tables.append(
                    TableIdentifier(
                        catalog=self.catalog,
                        namespace=namespace,
                        table=row["tableName"],
                    )
                )
        return sorted(tables, key=lambda table: table.sql_identifier)

    def collect_table_health(self, table_identifier: TableIdentifier) -> TableHealth:
        target_file_size_bytes = self._target_file_size_bytes(table_identifier)
        data_file_metrics = self._data_file_metrics(table_identifier, target_file_size_bytes)
        snapshot_count = self._snapshot_count(table_identifier)
        delete_file_count = self._delete_file_count(table_identifier)
        manifest_count = self._manifest_count(table_identifier)

        recommendation = self.recommend(
            snapshot_count=snapshot_count,
            data_file_count=data_file_metrics["data_file_count"],
            delete_file_count=delete_file_count,
            small_file_ratio=data_file_metrics["small_file_ratio"],
            manifest_count=manifest_count,
            orphan_file_count=None,
        )

        return TableHealth(
            catalog=table_identifier.catalog,
            namespace=table_identifier.namespace,
            table=table_identifier.table,
            snapshot_count=snapshot_count,
            data_file_count=data_file_metrics["data_file_count"],
            delete_file_count=delete_file_count,
            total_data_file_size_bytes=data_file_metrics["total_data_file_size_bytes"],
            avg_data_file_size_bytes=data_file_metrics["avg_data_file_size_bytes"],
            min_data_file_size_bytes=data_file_metrics["min_data_file_size_bytes"],
            max_data_file_size_bytes=data_file_metrics["max_data_file_size_bytes"],
            target_file_size_bytes=target_file_size_bytes,
            small_file_count=data_file_metrics["small_file_count"],
            small_file_ratio=data_file_metrics["small_file_ratio"],
            manifest_count=manifest_count,
            orphan_file_count=None,
            recommendation=recommendation,
        )

    def _target_file_size_bytes(self, table_identifier: TableIdentifier) -> int | None:
        rows = self.spark.sql(f"SHOW TBLPROPERTIES {table_identifier.sql_identifier}").collect()
        for row in rows:
            if row["key"] == "write.target-file-size-bytes":
                return int(row["value"])
        return None

    def _data_file_metrics(
        self,
        table_identifier: TableIdentifier,
        target_file_size_bytes: int | None,
    ) -> dict[str, Any]:
        small_file_limit = None
        if target_file_size_bytes:
            small_file_limit = int(target_file_size_bytes * self.small_file_size_ratio)

        small_file_expression = "0"
        if small_file_limit:
            small_file_expression = (
                f"CASE WHEN file_size_in_bytes < {small_file_limit} THEN 1 ELSE 0 END"
            )

        row = self.spark.sql(
            f"""
            SELECT
                count(*) AS data_file_count,
                coalesce(sum(file_size_in_bytes), 0) AS total_data_file_size_bytes,
                avg(file_size_in_bytes) AS avg_data_file_size_bytes,
                min(file_size_in_bytes) AS min_data_file_size_bytes,
                max(file_size_in_bytes) AS max_data_file_size_bytes,
                coalesce(sum({small_file_expression}), 0) AS small_file_count
            FROM {table_identifier.sql_identifier}.files
            """
        ).collect()[0]

        data_file_count = int(row["data_file_count"])
        small_file_count = int(row["small_file_count"])
        small_file_ratio = small_file_count / data_file_count if data_file_count else 0.0

        return {
            "data_file_count": data_file_count,
            "total_data_file_size_bytes": int(row["total_data_file_size_bytes"]),
            "avg_data_file_size_bytes": self._optional_float(row["avg_data_file_size_bytes"]),
            "min_data_file_size_bytes": self._optional_int(row["min_data_file_size_bytes"]),
            "max_data_file_size_bytes": self._optional_int(row["max_data_file_size_bytes"]),
            "small_file_count": small_file_count,
            "small_file_ratio": small_file_ratio,
        }

    def _snapshot_count(self, table_identifier: TableIdentifier) -> int:
        row = self.spark.sql(
            f"SELECT count(*) AS snapshot_count FROM {table_identifier.sql_identifier}.snapshots"
        ).collect()[0]
        return int(row["snapshot_count"])

    def _delete_file_count(self, table_identifier: TableIdentifier) -> int:
        try:
            row = self.spark.sql(
                f"""
                SELECT count(*) AS delete_file_count
                FROM {table_identifier.sql_identifier}.all_delete_files
                """
            ).collect()[0]
            return int(row["delete_file_count"])
        except Exception:
            return 0

    def _manifest_count(self, table_identifier: TableIdentifier) -> int:
        try:
            row = self.spark.sql(
                f"SELECT count(*) AS manifest_count FROM {table_identifier.sql_identifier}.manifests"
            ).collect()[0]
            return int(row["manifest_count"])
        except Exception:
            return 0

    def recommend(
        self,
        *,
        snapshot_count: int,
        data_file_count: int,
        delete_file_count: int,
        small_file_ratio: float,
        manifest_count: int = 0,
        orphan_file_count: int | None = None,
    ) -> MaintenanceRecommendation:
        if (
            data_file_count >= self.min_data_files_for_compaction
            and small_file_ratio >= self.small_file_ratio_threshold
        ):
            return MaintenanceRecommendation(
                operation=REWRITE_DATA_FILES,
                reason="The table contains a high ratio of data files below the target size.",
                priority="HIGH",
                confidence=min(0.95, 0.60 + small_file_ratio * 0.35),
            )

        if delete_file_count >= self.delete_file_count_threshold:
            return MaintenanceRecommendation(
                operation=REWRITE_POSITION_DELETE_FILES,
                reason="The table contains enough position delete files to justify rewrite_position_delete_files.",
                priority="MEDIUM",
                confidence=0.80,
            )

        if manifest_count >= self.manifest_count_threshold:
            return MaintenanceRecommendation(
                operation=REWRITE_MANIFESTS,
                reason="The table has accumulated enough manifests to justify rewrite_manifests.",
                priority="MEDIUM",
                confidence=0.78,
            )

        if snapshot_count >= self.snapshot_count_threshold:
            return MaintenanceRecommendation(
                operation=EXPIRE_SNAPSHOTS,
                reason="The table has accumulated many snapshots.",
                priority="MEDIUM",
                confidence=0.75,
            )

        if (
            orphan_file_count is not None
            and orphan_file_count >= self.orphan_file_count_threshold
        ):
            return MaintenanceRecommendation(
                operation=REMOVE_ORPHAN_FILES,
                reason="The table location contains orphan files that are not referenced by Iceberg metadata.",
                priority="LOW",
                confidence=0.70,
            )

        return MaintenanceRecommendation(
            operation=NO_ACTION,
            reason="No maintenance threshold was exceeded.",
            priority="LOW",
            confidence=0.70,
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return None if value is None else int(value)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return None if value is None else float(value)
