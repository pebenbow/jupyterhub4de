"""
Dagster definitions for the jupyterhub4de platform.

Each job launches one Job Pod (the notebook image, running a pipeline
script) via the Kubernetes API, waits for it to finish, and surfaces its
logs. See docs/adr/0001-dagster-launches-job-pods.md for why this shape
(fresh Job Pod per run, not a shared/attached Spark session) was chosen.
"""
from dagster import Definitions, job

from .job_pod import make_job_pod_op

# One op/job per pipeline script under the shared PVC's /code subpath.
# Add an entry here per pipeline; the op itself is generic (parameterized
# by script path), so new pipelines don't need new Python — just a new
# `make_job_pod_op(...)` call and `@job` wrapper below.
run_example_pipeline_op = make_job_pod_op(
    name="run_example_pipeline",
    script_path="pipelines/example_pipeline.py",
)


@job
def example_pipeline_job():
    run_example_pipeline_op()


defs = Definitions(jobs=[example_pipeline_job])
