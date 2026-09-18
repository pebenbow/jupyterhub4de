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
    # hive.metastore.uris isn't a spark.*-namespaced key, so a plain
    # .config() call is silently ignored (Spark logs a warning) — the
    # actual connection comes from the notebook image's baked-in
    # hive-site.xml (images/notebook/hive-site.xml). The
    # spark.hadoop. prefix is what actually reaches Hadoop/Hive config.
    .config("spark.hadoop.hive.metastore.uris", os.environ["HIVE_METASTORE_URI"])
    # Spark computes a database's default table location from this
    # client-side setting, not from the metastore server's own
    # hive.metastore.warehouse.dir — without it, CREATE TABLE fails
    # trying to create a /home/jovyan/spark-warehouse/... dir that
    # doesn't exist in this Job Pod. Must match the notebook pod's/Hive
    # Metastore's mount path (charts/jupyterhub4de/values.yaml) so table
    # locations resolve to the same real directory from every pod.
    .config("spark.sql.warehouse.dir", "/data/warehouse")
)
spark = configure_spark_with_delta_pip(builder).getOrCreate()

spark.sql("CREATE DATABASE IF NOT EXISTS example")
spark.range(5).write.format("delta").mode("overwrite").saveAsTable("example.numbers")
spark.sql("SELECT * FROM example.numbers").show()

spark.stop()
