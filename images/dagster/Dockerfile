# Dagster orchestration image — issue #4/#5.
# Separate container from the notebook image: k8s API client only, no
# PySpark/Spark install. Each Dagster run launches a fresh Job Pod using the
# *notebook* image (images/notebook) instead of running Spark in-process
# here (see docs/adr/0001-dagster-launches-job-pods.md).
FROM python:3.12-slim

RUN pip install --no-cache-dir \
        "dagster==1.9.9" \
        "dagster-webserver==1.9.9" \
        "dagster-k8s==0.25.9" \
        "kubernetes==31.0.0"

WORKDIR /opt/dagster/app
COPY workspace.yaml /opt/dagster/app/workspace.yaml
COPY defs /opt/dagster/app/defs

ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p "${DAGSTER_HOME}"
COPY dagster.yaml "${DAGSTER_HOME}/dagster.yaml"

EXPOSE 3000
ENTRYPOINT ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/opt/dagster/app/workspace.yaml"]
