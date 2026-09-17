# Example pipeline run by Dagster's example_pipeline_job (images/dagster/defs)
# inside a Job Pod using the notebook image. Lives on the shared PVC's
# /code subpath — see charts/jupyterhub4de/README.md for how pipeline
# scripts get onto that PVC (kubectl cp, not baked into an image), so
# pipeline code can be updated without a rebuild (issue #4).
import os

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

builder = (
    SparkSession.builder.appName("example-pipeline")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
    .config("spark.sql.catalogImplementation", "hive")
    .config("hive.metastore.uris", os.environ["HIVE_METASTORE_URI"])
)
spark = configure_spark_with_delta_pip(builder).getOrCreate()

spark.sql("CREATE DATABASE IF NOT EXISTS example")
spark.range(5).write.format("delta").mode("overwrite").saveAsTable("example.numbers")
spark.sql("SELECT * FROM example.numbers").show()

spark.stop()
