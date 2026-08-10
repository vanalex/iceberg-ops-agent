from polaris_spark import create_spark_session, env


def main() -> None:
    catalog = env("CATALOG", "lakehouse")
    spark = create_spark_session("list-polaris-iceberg-tables")

    try:
        namespaces = [
            row["namespace"] for row in spark.sql(f"SHOW NAMESPACES IN {catalog}").collect()
        ]

        if not namespaces:
            print(f"No namespaces found in catalog {catalog}")
            return

        for namespace in namespaces:
            print(f"{catalog}.{namespace}")
            tables = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}").collect()

            if not tables:
                print("  no tables")
                continue

            for table in tables:
                table_name = table["tableName"]
                is_temporary = table["isTemporary"]
                print(f"  {table_name} temporary={is_temporary}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
