# PROTOTYPE — throwaway image for jupyterhub4de issue #3.
# Answers: can one image run JupyterHub (single-user, DummyAuthenticator) +
# PySpark 4.x local mode + Delta Lake + MLflow client + Hive Metastore client?
#
# Base: quay.io/jupyter/pyspark-notebook, built by the Jupyter Docker Stacks
# project. It already knows how to assemble Spark 4.x + matching Hadoop +
# OpenJDK from build args (docker-stacks added Spark-4.x support in 2026),
# so we don't hand-roll a Spark install — we ride their tested build logic
# and layer JupyterHub, Delta, MLflow, and Hive Metastore config on top.
ARG SPARK_VERSION=4.0.0
ARG HADOOP_VERSION=3
ARG OPENJDK_VERSION=21

FROM quay.io/jupyter/pyspark-notebook:python-3.12 AS base

ARG SPARK_VERSION
ARG HADOOP_VERSION
ARG OPENJDK_VERSION

# docker-stacks resolves these build args itself when the image is built
# from source; the published python-3.12 tag already bundles a recent Spark
# 4.x + Hadoop 3 + OpenJDK 21 combination, so no re-download is needed here.
# Pin versions are enforced instead via the pip/conda installs below.

USER root

# Hive Metastore client talks over Thrift; Spark resolves the matching
# hive-metastore-client jars itself via Ivy at first use
# (spark.sql.hive.metastore.jars=maven), so no extra system packages beyond
# curl (already present) are required here.

USER ${NB_UID}

# ---- Pinned, mutually-compatible versions -------------------------------
# pyspark          4.0.0   already baked into the base image's SPARK_HOME
# delta-spark      4.0.0   only delta-spark 4.0.x targets pyspark 4.0.x
#                          (4.2.x requires pyspark>=4.0.1,<=4.1.1 — see
#                          delta-io/delta#6888); pin exact to avoid drift
# jupyterhub       5.2.1   single-user server + DummyAuthenticator, run
#                          alongside the notebook's own jupyterhub-singleuser
# mlflow           2.22.0  client-only per the map's settled decision;
#                          no tracking-server extras installed
RUN pip install --no-cache-dir \
        "pyspark==4.0.0" \
        "delta-spark==4.0.0" \
        "jupyterhub==5.2.1" \
        "mlflow==2.22.0"

# Hive Metastore connection settings: point Spark's HiveExternalCatalog at
# an external metastore service over Thrift instead of the embedded Derby
# metastore. metastore.version pinned to 4.0.0 per issue #2's research
# (spark.sql.hive.metastore.version supports up to the 4.0.0-4.1.0 range);
# metastore.jars=maven lets Spark fetch matching client jars on first use
# instead of us vendoring them into the image.
COPY --chown=${NB_UID}:${NB_GID} hive-site.xml /usr/local/spark/conf/hive-site.xml

# JupyterHub entrypoint: this image is spawned per-user by JupyterHub's
# KubeSpawner in the real deployment, but for this single-container
# prototype the entrypoint runs jupyterhub-singleuser directly so the
# question "does everything import and start in one container" can be
# answered without standing up a separate hub process yet.
COPY --chown=${NB_UID}:${NB_GID} entrypoint.sh /usr/local/bin/entrypoint.sh
USER root
RUN chmod +x /usr/local/bin/entrypoint.sh
USER ${NB_UID}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
