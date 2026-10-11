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

# VS Code in the browser: jupyter-vscode-proxy registers a jupyter-server-proxy
# entry point (`vscode` -> jupyter_vscode_proxy:setup_vscode) that launches
# code-server behind JupyterHub's per-user proxy. jupyter-server-proxy is the
# package that actually reads that entry point and adds the Launcher tile —
# jupyter-vscode-proxy alone is a no-op without it.
RUN pip install --no-cache-dir jupyter-server-proxy jupyter-vscode-proxy

USER root
# install.sh caches its .deb under $HOME/.cache, and $HOME is still
# /home/jovyan here, so it leaves a root-owned ~/.cache behind that breaks
# anything jovyan later caches to (Quarto, pip, ...). Remove it in the same
# layer.
RUN curl -fsSL https://code-server.dev/install.sh | sh && \
    rm -rf /home/jovyan/.cache

# Lock down code-server for a shared student environment:
#  - GitHub.copilot-chat ships as a built-in extension in this code-server's
#    bundled VS Code (1.137.0), not core UI, so it can be disabled outright
#    via --vscode-option rather than merely hidden. jupyter-vscode-proxy
#    hardcodes its own `code-server ...` argv with no hook for extra flags,
#    so this wrapper shadows the real binary earlier in $PATH.
#  - This does NOT lock the extensions gallery (Q3's Spark/Dagster/etc.
#    extensions still need to install), so a student could still add a
#    third-party AI agent extension (Continue, Cody, Codeium) from Open VSX.
RUN mv /usr/bin/code-server /usr/bin/code-server.real && \
    printf '#!/bin/sh\nexec /usr/bin/code-server.real --vscode-option disable-extension=GitHub.copilot-chat "$@"\n' \
        > /usr/local/bin/code-server && \
    chmod +x /usr/local/bin/code-server

# Default settings baked into the image's user-data-dir. $HOME isn't on the
# shared PVC (only /data and /code subpaths are, per values.yaml), so this
# is reapplied fresh on every pod respawn and can't be permanently
# overridden by a student mid-session.
COPY --chown=${NB_UID}:${NB_GID} code-server-settings.json \
    /home/jovyan/.local/share/code-server/User/settings.json

USER ${NB_UID}

# Without these, opening a .ipynb in VS Code prompts to pick a "Python
# Environment or Jupyter Server" with nothing installed to satisfy either —
# the `ipynb` renderer is core to VS Code, but actually running cells needs
# ms-toolsai.jupyter (kernel management), which in turn needs ms-python.python
# (interpreter discovery/debugpy). Same $HOME-isn't-persisted reasoning as the
# settings.json above: baked into the image's default extensions-dir, so it
# survives every pod respawn without needing a per-session install.
RUN code-server --install-extension ms-python.python --force \
    && code-server --install-extension ms-toolsai.jupyter --force

# ---- Positron in the browser ----------------------------------------------
# Positron Server (Posit's data-science IDE, a VS Code fork) behind the same
# jupyter-server-proxy as code-server above — jupyter-positron-server adds a
# "Positron" Launcher tile. Positron is the primary IDE here; code-server
# stays installed alongside it for comparison.
#
# Positron Server needs a license file to start (free for academic use, from
# academic-licenses@posit.co). The license is NOT baked into this image (it's
# pushed to a registry); it arrives at runtime as a Kubernetes Secret, see
# charts/jupyterhub4de/values-positron-license.yaml. Without it the tile still
# appears, but opening it shows positron-server's "no license" error page.
#
# Version pairing matters: 2026.09.0+ validates license.lic from its own
# activation dir, which needs jupyter-positron-server >= 0.0.6. 0.0.6 is
# tagged on GitHub but not yet on PyPI, hence the tag tarball.
ARG POSITRON_VERSION=2026.09.1-2
ARG JUPYTER_POSITRON_SERVER_VERSION=0.0.6
ENV POSITRON_SERVER_DIR=/opt/positron-server

USER root
RUN mkdir -p "${POSITRON_SERVER_DIR}" && \
    curl -fsSL "https://cdn.posit.co/positron/releases/server/x86_64/positron-server-linux-x64-${POSITRON_VERSION}.tar.gz" \
        | tar -xz -C "${POSITRON_SERVER_DIR}" --strip-components=1

# Same Copilot lockdown as code-server's wrapper above, plus Positron's own
# built-in AI agent (posit.assistant). The wrapper has to replace the binary
# in place rather than shadow it from /usr/local/bin: jupyter-positron-server
# finds the license/activation dir relative to realpath(positron-server).
RUN mv "${POSITRON_SERVER_DIR}/bin/positron-server" "${POSITRON_SERVER_DIR}/bin/positron-server.real" && \
    printf '#!/bin/sh\nexec "$(dirname "$0")/positron-server.real" --disable-extension GitHub.copilot-chat --disable-extension posit.assistant "$@"\n' \
        > "${POSITRON_SERVER_DIR}/bin/positron-server" && \
    chmod +x "${POSITRON_SERVER_DIR}/bin/positron-server"

# Positron bundles the Quarto CLI; put it on PATH so `quarto render` /
# `quarto preview` also work from any terminal (JupyterLab's, code-server's).
RUN ln -s "${POSITRON_SERVER_DIR}/quarto/bin/quarto" /usr/local/bin/quarto

USER ${NB_UID}
ENV PATH="${POSITRON_SERVER_DIR}/bin:${PATH}"

RUN pip install --no-cache-dir \
        "https://github.com/posit-dev/jupyter-positron-server/archive/refs/tags/${JUPYTER_POSITRON_SERVER_VERSION}.tar.gz"

# On first launch positron-server installs the .vsix files in
# extensions/bootstrap (Quarto, Jupyter, debugpy, Ruff, ...) into
# ~/.positron-server/extensions. $HOME isn't persisted (see settings.json
# above), so left alone that would happen on every pod respawn; installing
# them here bakes them into the image instead. The CLI install path doesn't
# need a license.
RUN for vsix in "${POSITRON_SERVER_DIR}"/extensions/bootstrap/*.vsix; do \
        positron-server.real --install-extension "${vsix}" --force || exit 1; \
    done

COPY --chown=${NB_UID}:${NB_GID} positron-settings.json \
    /home/jovyan/.positron-server/data/User/settings.json

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
