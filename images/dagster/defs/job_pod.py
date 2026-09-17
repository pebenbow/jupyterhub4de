"""
Builds and runs one Job Pod per Dagster op invocation.

Config (notebook image, PVC claim name, /code and /data subpaths, Hive
Metastore URI) all comes from the shared ConfigMap
(charts/jupyterhub4de/templates/configmap.yaml) via env vars, so the
static chart templates and this runtime-built Job spec can't drift
(issue #5).
"""
import os
import time

from dagster import Failure, OpExecutionContext, op
from kubernetes import client as k8s, config as k8s_config

# Job Pod resources — not specified by issues #4/#5; chosen to leave
# headroom for an interactive notebook session on the single-node
# 24-core/64GB tower. Tune if real pipelines need more.
JOB_POD_CPU_REQUEST = "2"
JOB_POD_MEMORY_REQUEST = "4Gi"
JOB_POD_CPU_LIMIT = "4"
JOB_POD_MEMORY_LIMIT = "8Gi"

POLL_INTERVAL_SECONDS = 5


def _load_k8s_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def make_job_pod_op(*, name: str, script_path: str):
    """Returns an @op that runs `script_path` (relative to the shared
    PVC's /code subpath) inside a fresh Job Pod using the notebook image.
    """

    @op(name=name)
    def _op(context: OpExecutionContext) -> None:
        _load_k8s_config()
        batch = k8s.BatchV1Api()

        namespace = os.environ["K8S_NAMESPACE"]
        notebook_image = os.environ["NOTEBOOK_IMAGE"]
        pvc_claim_name = os.environ["PVC_CLAIM_NAME"]
        code_subpath = os.environ["CODE_SUBPATH"]
        data_subpath = os.environ["DATA_SUBPATH"]
        hive_metastore_uri = os.environ["HIVE_METASTORE_URI"]

        job_name = f"{name.replace('_', '-')}-{int(time.time())}"

        job_manifest = k8s.V1Job(
            metadata=k8s.V1ObjectMeta(name=job_name, namespace=namespace),
            spec=k8s.V1JobSpec(
                backoff_limit=0,
                template=k8s.V1PodTemplateSpec(
                    spec=k8s.V1PodSpec(
                        restart_policy="Never",
                        containers=[
                            k8s.V1Container(
                                name="job-pod",
                                image=notebook_image,
                                command=["python", f"/code/{script_path}"],
                                env=[
                                    k8s.V1EnvVar(
                                        name="HIVE_METASTORE_URI",
                                        value=hive_metastore_uri,
                                    ),
                                ],
                                resources=k8s.V1ResourceRequirements(
                                    requests={
                                        "cpu": JOB_POD_CPU_REQUEST,
                                        "memory": JOB_POD_MEMORY_REQUEST,
                                    },
                                    limits={
                                        "cpu": JOB_POD_CPU_LIMIT,
                                        "memory": JOB_POD_MEMORY_LIMIT,
                                    },
                                ),
                                volume_mounts=[
                                    k8s.V1VolumeMount(
                                        name="shared-pvc",
                                        mount_path="/code",
                                        sub_path=code_subpath,
                                        read_only=True,
                                    ),
                                    k8s.V1VolumeMount(
                                        name="shared-pvc",
                                        mount_path="/data",
                                        sub_path=data_subpath,
                                    ),
                                ],
                            )
                        ],
                        volumes=[
                            k8s.V1Volume(
                                name="shared-pvc",
                                persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(
                                    claim_name=pvc_claim_name
                                ),
                            )
                        ],
                    )
                ),
            ),
        )

        batch.create_namespaced_job(namespace=namespace, body=job_manifest)
        context.log.info(f"Launched Job Pod {job_name}")

        try:
            while True:
                status = batch.read_namespaced_job_status(job_name, namespace).status
                if status.succeeded:
                    context.log.info(f"Job Pod {job_name} succeeded")
                    return
                if status.failed:
                    raise Failure(f"Job Pod {job_name} failed — see `kubectl logs -n {namespace} job/{job_name}`")
                time.sleep(POLL_INTERVAL_SECONDS)
        finally:
            batch.delete_namespaced_job(
                job_name,
                namespace,
                propagation_policy="Background",
            )

    return _op
