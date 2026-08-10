import os

from pyspark.sql import SparkSession


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def create_spark_session() -> SparkSession:
    catalog = env("CATALOG", "lakehouse")
    polaris_url = env("POLARIS_URL", "http://localhost:8181")
    client_id = env("POLARIS_CLIENT_ID", "root")
    client_secret = env("POLARIS_CLIENT_SECRET", "s3cr3t")
    realm = env("POLARIS_REALM", "POLARIS")
    minio_url = env("MINIO_URL", "http://localhost:9000")
    minio_access_key = env("MINIO_ACCESS_KEY", "minio_root")
    minio_secret_key = env("MINIO_SECRET_KEY", "m1n1opwd")
    iceberg_version = env("ICEBERG_VERSION", "1.11.0")
    iceberg_spark_runtime = env("ICEBERG_SPARK_RUNTIME", "4.1_2.13")

    iceberg_packages = ",".join(
        [
            f"org.apache.iceberg:iceberg-spark-runtime-{iceberg_spark_runtime}:{iceberg_version}",
            f"org.apache.iceberg:iceberg-aws-bundle:{iceberg_version}",
        ]
    )

    return (
        SparkSession.builder.appName("create-polaris-iceberg-context")
        .master(env("SPARK_MASTER", "local[*]"))
        .config("spark.jars.packages", iceberg_packages)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.type", "rest")
        .config(f"spark.sql.catalog.{catalog}.uri", f"{polaris_url}/api/catalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", catalog)
        .config(f"spark.sql.catalog.{catalog}.rest.auth.type", "oauth2")
        .config(f"spark.sql.catalog.{catalog}.credential", f"{client_id}:{client_secret}")
        .config(f"spark.sql.catalog.{catalog}.scope", "PRINCIPAL_ROLE:ALL")
        .config(
            f"spark.sql.catalog.{catalog}.oauth2-server-uri",
            f"{polaris_url}/api/catalog/v1/oauth/tokens",
        )
        .config(f"spark.sql.catalog.{catalog}.header.Polaris-Realm", realm)
        .config(f"spark.sql.catalog.{catalog}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"spark.sql.catalog.{catalog}.s3.endpoint", minio_url)
        .config(f"spark.sql.catalog.{catalog}.s3.path-style-access", "true")
        .config(f"spark.sql.catalog.{catalog}.s3.access-key-id", minio_access_key)
        .config(f"spark.sql.catalog.{catalog}.s3.secret-access-key", minio_secret_key)
        .config("spark.hadoop.fs.s3a.endpoint", minio_url)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.access.key", minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", minio_secret_key)
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )


def main() -> None:
    catalog = env("CATALOG", "lakehouse")
    namespace = env("NAMESPACE", "default")
    table = env("TABLE", "events")

    spark = create_spark_session()
    try:
        table_identifier = f"{catalog}.{namespace}.{table}"
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.{namespace}")
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
        spark.sql(f"SELECT * FROM {table_identifier}").show(truncate=False)
        print(f"Created Polaris Iceberg context for {table_identifier}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
