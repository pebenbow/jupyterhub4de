# Context

## Glossary

**Platform**: The full stack under design — JupyterHub, Apache Spark (PySpark), Delta Lake, a Catalog Layer, MLflow, and Dagster, packaged as a custom container and stitched together by a Helm chart. This is the noun for "the thing we're building," distinct from any one Component.

**Catalog Layer**: The metadata/governance service Spark reads table definitions from — either Unity Catalog (OSS, preferred) or Hive Metastore (fallback). Referred to generically as "the Catalog Layer" until the Unity Catalog vs. Hive Metastore ticket resolves which implementation it is.

**Prototype Phase**: The current effort's scope — a single-user, single-node deployment on Docker Desktop's local Kubernetes, running on the instructor's research tower (64GB RAM, 24-core Intel Ultra 9 285), using local filesystem storage only. Distinguished from the RC Handoff.

**RC Handoff**: The future, separate effort (out of scope for this map) in which Research Computing colleagues take the Prototype Phase's architecture and implement a multi-user deployment (auth, RBAC, per-user quotas, namespace isolation). This map produces only a lightweight roadmap for that handoff, not the implementation.

**Course**: The Data Engineering class the Platform is being built to support, currently taught on Databricks; the Platform is meant to replace Databricks Free Edition starting no later than August 2027.

**Job Pod**: The ephemeral Kubernetes Job that Dagster launches to run a single pipeline, using the same custom image as the notebook container but independent of the notebook pod's lifecycle. Distinct from the notebook pod, which is the long-running interactive JupyterHub/Spark container a student works in.
_Avoid_: worker pod, task pod
