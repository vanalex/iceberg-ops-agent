from polaris_spark import create_spark_session, env, parse_table_specs


DEFAULT_TABLE_SPECS = [
    ("demo", "events"),
    ("demo", "orders"),
    ("analytics", "sessions"),
    ("analytics", "page_views"),
]


def create_events_table(spark, table_identifier: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_identifier} (
            id BIGINT,
            event_type STRING,
            created_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES (
            'write.target-file-size-bytes' = '536870912',
            'write.delete.mode' = 'merge-on-read',
            'write.update.mode' = 'merge-on-read',
            'write.merge.mode' = 'merge-on-read'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {table_identifier}
        VALUES
            (1, 'created', TIMESTAMP '2026-08-09 10:00:00'),
            (2, 'updated', TIMESTAMP '2026-08-09 10:05:00'),
            (3, 'deleted', TIMESTAMP '2026-08-09 10:10:00')
        """
    )


def create_orders_table(spark, table_identifier: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_identifier} (
            order_id BIGINT,
            customer_id BIGINT,
            order_total DECIMAL(10, 2),
            created_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES (
            'write.target-file-size-bytes' = '536870912'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {table_identifier}
        VALUES
            (1001, 11, 42.50, TIMESTAMP '2026-08-09 11:00:00'),
            (1002, 12, 19.99, TIMESTAMP '2026-08-09 11:05:00'),
            (1003, 11, 128.75, TIMESTAMP '2026-08-09 11:10:00')
        """
    )


def create_sessions_table(spark, table_identifier: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_identifier} (
            session_id STRING,
            user_id BIGINT,
            duration_seconds INT,
            started_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES (
            'write.target-file-size-bytes' = '268435456'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {table_identifier}
        VALUES
            ('s-001', 11, 302, TIMESTAMP '2026-08-09 12:00:00'),
            ('s-002', 12, 45, TIMESTAMP '2026-08-09 12:03:00'),
            ('s-003', 13, 811, TIMESTAMP '2026-08-09 12:15:00')
        """
    )


def create_page_views_table(spark, table_identifier: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_identifier} (
            view_id BIGINT,
            session_id STRING,
            path STRING,
            viewed_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES (
            'write.target-file-size-bytes' = '268435456'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {table_identifier}
        VALUES
            (1, 's-001', '/home', TIMESTAMP '2026-08-09 12:00:05'),
            (2, 's-001', '/pricing', TIMESTAMP '2026-08-09 12:01:10'),
            (3, 's-002', '/docs', TIMESTAMP '2026-08-09 12:03:20')
        """
    )


def create_generic_table(spark, table_identifier: str) -> None:
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_identifier} (
            id BIGINT,
            value STRING,
            created_at TIMESTAMP
        )
        USING iceberg
        TBLPROPERTIES (
            'write.target-file-size-bytes' = '536870912'
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {table_identifier}
        VALUES
            (1, 'alpha', TIMESTAMP '2026-08-09 13:00:00'),
            (2, 'beta', TIMESTAMP '2026-08-09 13:05:00')
        """
    )


def create_table(spark, catalog: str, namespace: str, table: str) -> None:
    table_identifier = f"{catalog}.{namespace}.{table}"
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.{namespace}")

    if table == "events":
        create_events_table(spark, table_identifier)
    elif table == "orders":
        create_orders_table(spark, table_identifier)
    elif table == "sessions":
        create_sessions_table(spark, table_identifier)
    elif table == "page_views":
        create_page_views_table(spark, table_identifier)
    else:
        create_generic_table(spark, table_identifier)

    count = spark.sql(f"SELECT count(*) AS row_count FROM {table_identifier}").collect()[0][
        "row_count"
    ]
    print(f"Created or updated {table_identifier} with {count} rows")


def main() -> None:
    catalog = env("CATALOG", "lakehouse")
    table_specs = parse_table_specs(DEFAULT_TABLE_SPECS)

    spark = create_spark_session("create-polaris-iceberg-tables")
    try:
        for namespace, table in table_specs:
            create_table(spark, catalog, namespace, table)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
