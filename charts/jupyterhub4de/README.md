# jupyterhub4de Helm chart

Single umbrella chart for the jupyterhub4de prototype (map: [Local JupyterHub
data engineering platform](https://github.com/pebenbow/jupyterhub4de/issues/1)).
Chart shape decided in [issue #5](https://github.com/pebenbow/jupyterhub4de/issues/5):
Zero to JupyterHub and Postgres are external subchart dependencies; Dagster,
Hive Metastore, the shared PVC, RBAC, and the cross-component ConfigMap are
plain templates in this top-level chart — none of them need an independent
install/upgrade lifecycle.

## Why `singleuser.storage.type: none`

Z2JH's default `storage.type: dynamic` provisions one PVC per user. This
prototype needs one PVC *shared* between the notebook pod and every
Dagster-launched Job Pod (issue #5), so dynamic per-user storage is turned
off in `values.yaml` and the shared PVC (`templates/pvc.yaml`) is mounted
into the singleuser pod explicitly via `extraVolumes`/`extraVolumeMounts`.
This is a deliberate deviation from Z2JH's default pattern, worth knowing
before changing storage settings here.

## Why Postgres only backs Hive Metastore

Z2JH's hub defaults to an embedded sqlite database for its own state, which
is fine for this single-node, single-user prototype. The `postgresql`
dependency exists solely to give Hive Metastore a real concurrent-access
backing store instead of embedded Derby (issue #5) — concurrent access from
a notebook pod and a Job Pod at the same time is a core scenario, not an
edge case.

## Getting pipeline code onto the shared PVC

Pipeline scripts (e.g. `pipelines/example_pipeline.py` in this repo) aren't
baked into the notebook image — they live on the shared PVC's `/code`
subpath so they can be updated without a rebuild (issue #4). For this
manual prototype, copy them in via `kubectl cp`, e.g.:

```
kubectl -n jupyterhub4de cp pipelines/example_pipeline.py \
  <a-notebook-or-job-pod>:/home/jovyan/code/example_pipeline.py
```

## Build, push, install (manual — no CI/CD per the map's settled decisions)

```
docker build -t ghcr.io/pebenbow/jupyterhub4de-notebook:latest images/notebook
docker push ghcr.io/pebenbow/jupyterhub4de-notebook:latest

docker build -t ghcr.io/pebenbow/jupyterhub4de-dagster:latest images/dagster
docker push ghcr.io/pebenbow/jupyterhub4de-dagster:latest

helm dependency update charts/jupyterhub4de
helm install jupyterhub4de charts/jupyterhub4de \
  -n jupyterhub4de --create-namespace
```

## Verification checklist

- [ ] Singleuser pod starts; `python -c "import pyspark, delta, mlflow"` succeeds inside it.
- [ ] A `SparkSession` with Hive support enabled can `CREATE TABLE` and see it via `SHOW TABLES` (proves the metastore wiring end to end).
- [ ] Triggering `example_pipeline_job` in the Dagster webserver produces a Job Pod that writes a Delta table to the shared PVC, and the notebook pod can read it back.
