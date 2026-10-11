# Shared Spark session builder for pipeline scripts. Copied onto the shared
# PVC's /code alongside the scripts that import it (see
# charts/jupyterhub4de/README.md's "Getting pipeline code onto the shared
# PVC" section) — kubectl cp this file to the same pipelines/ subpath.
import os
import socket

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


def _free_ui_port(start: int = 4040, attempts: int = 16) -> int:
    # Spark would fall back to 4041, 4042, ... on its own if 4040 is taken
    # (e.g. a Positron console session plus a `quarto render` in the same
    # pod), but spark.ui.proxyBase has to name the port before the session
    # starts — so pick it here and pin spark.ui.port to match.
    for port in range(start, start + attempts):
        with socket.socket() as s:
            try:
                s.bind(("", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free Spark UI port in {start}-{start + attempts - 1}")


def get_spark(app_name: str) -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
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
    # Spark UI via the notebook pod's jupyter-server-proxy, at
    # /user/<name>/proxy/<port>/. The UI emits absolute links, so without
    # proxyBase every click escapes the proxy prefix and 404s. The env var
    # is set by JupyterHub in the notebook pod only — Job Pods skip this and
    # keep Spark's default UI, which nobody can reach and dies with the pod.
    prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
    if prefix:
        port = _free_ui_port()
        builder = builder.config("spark.ui.port", str(port)).config(
            "spark.ui.proxyBase", f"{prefix.rstrip('/')}/proxy/{port}"
        )
    return configure_spark_with_delta_pip(builder).getOrCreate()
