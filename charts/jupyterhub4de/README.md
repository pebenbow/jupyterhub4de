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
subpath so they can be updated without a rebuild (issue #4). The shared
PVC is mounted at both `/code` (used by Job Pods and Hive Metastore) and
`/home/jovyan/code` (the same underlying files, visible from JupyterLab's
file browser, which is rooted at `$HOME` and can't see `/code` directly)
— use whichever's convenient, they're the same directory.

Each Dagster op in `images/dagster/defs/__init__.py` is registered with a
`script_path` **relative to `/code`**, e.g. `make_job_pod_op(...,
script_path="pipelines/example_pipeline.py")` expects the file at
`/code/pipelines/example_pipeline.py` (equivalently
`/home/jovyan/code/pipelines/example_pipeline.py`) — keep the path you
copy to in sync with what's registered, or the Job Pod fails with `No
such file or directory`.

For this manual prototype, copy scripts in via `kubectl cp`, e.g.:

```
kubectl -n jupyterhub4de cp pipelines/example_pipeline.py \
  jupyter-admin:/home/jovyan/code/pipelines/example_pipeline.py
kubectl -n jupyterhub4de cp pipelines/spark_session.py \
  jupyter-admin:/home/jovyan/code/pipelines/spark_session.py
```

`pipelines/spark_session.py` holds the shared `get_spark(app_name)` helper
(Delta + Hive metastore config in one place) that `example_pipeline.py` and
any notebook can import — copy it alongside any script that uses it.

## Porting Databricks notebooks

Notebooks need one addition Databricks doesn't require: call `spark.stop()`
in the final cell (or restart the kernel) when done. On Databricks, each
notebook attaches to a cluster the platform manages independently — an
unstopped session doesn't cost you anything personally. Here, the notebook
pod is a single resource-constrained JVM shared by everything that pod
runs, and Spark only allows one active `SparkContext` per JVM by default.
An unstopped session from one notebook will interfere with (or block) a
`get_spark(...)` call in another notebook run in the same pod, and holds
executor memory against the pod's resource limits (`values.yaml`) the
whole time it's alive.

## Spark UI

While a `get_spark(...)` session is alive in the notebook pod, its Spark UI
(Jobs, Stages, Storage, Executors, SQL tabs) is at
`<hub URL>/user/<name>/proxy/4040/` — e.g.
`http://localhost:8080/user/admin/proxy/4040/` with the port-forward from
`docs/operating.md`. A second concurrent session in the same pod gets 4041,
and so on (`get_spark` picks the first free port from 4040 and sets
`spark.ui.proxyBase` to match). The UI goes away with `spark.stop()` or a
kernel restart. Dagster Job Pods' Spark UIs aren't reachable — that would
need a Spark History Server.

## Positron and Quarto

The JupyterLab Launcher has three ways in: JupyterLab itself, VS Code
(code-server), and **Positron**, the primary student IDE. Course material is
written as Quarto documents (`.qmd`, see `notebooks/`), not `.ipynb`: plain
text that diffs cleanly, and in Positron each `{python}` cell runs in the
Python console, so `spark` stays inspectable in the Variables pane.
`quarto render foo.qmd` (Quarto ships with Positron and is on `PATH` in any
terminal) executes every cell top to bottom against the pod's real Spark +
Hive Metastore, so a successful render doubles as a check that the lesson
runs.

Copy lessons onto the shared PVC the same way as pipeline code:

```
kubectl -n jupyterhub4de cp notebooks/medallion_architecture.qmd \
  jupyter-admin:/home/jovyan/code/notebooks/medallion_architecture.qmd
```

**Positron Server needs a license file** (`license.lic`). It's free for
academic use; request it from academic-licenses@posit.co. Keep it at the repo
root (it's git-ignored) and install/upgrade with the overlay below. Without
it everything else works, but the Positron tile opens an error page saying
no license was found. `values-positron-license.yaml` explains why the
license wiring isn't in `values.yaml` itself.

## Build, push, install (manual — no CI/CD per the map's settled decisions)

```
docker build -t ghcr.io/pebenbow/jupyterhub4de-notebook:latest images/notebook
docker push ghcr.io/pebenbow/jupyterhub4de-notebook:latest

docker build -t ghcr.io/pebenbow/jupyterhub4de-dagster:latest images/dagster
docker push ghcr.io/pebenbow/jupyterhub4de-dagster:latest

helm dependency update charts/jupyterhub4de
helm install jupyterhub4de charts/jupyterhub4de \
  -n jupyterhub4de --create-namespace \
  -f charts/jupyterhub4de/values-positron-license.yaml \
  --set-file 'jupyterhub.singleuser.extraFiles.license\.lic.stringData'=./license.lic
```

(Drop the last two lines if you don't have a Positron license yet.)

## Verification checklist

- [ ] Singleuser pod starts; `python -c "import pyspark, delta, mlflow"` succeeds inside it.
- [ ] A `SparkSession` with Hive support enabled can `CREATE TABLE` and see it via `SHOW TABLES` (proves the metastore wiring end to end).
- [ ] With a `get_spark(...)` session open, `/user/<name>/proxy/4040/` shows the Spark UI and clicking into a job's stages stays under that prefix (proves `spark.ui.proxyBase`).
- [ ] The Launcher's Positron tile opens Positron; `quarto render` of a lesson in `~/code/notebooks/` succeeds.
- [ ] Triggering `example_pipeline_job` in the Dagster webserver produces a Job Pod that writes a Delta table to the shared PVC, and the notebook pod can read it back.
