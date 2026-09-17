# Unity Catalog OSS vs. Hive Metastore for the Catalog Layer

Research for GitHub issue [#2](https://github.com/pebenbow/jupyterhub4de/issues/2) (child of wayfinder map issue #1).

**Scope note:** This document is research only. It does not make or imply a recommendation — that call belongs to a later decision session. It covers deployment, Spark/Delta integration, governance capability, and version compatibility for both options, evaluated against this project's actual environment: a single custom Linux container running JupyterHub/JupyterLab + PySpark in **local mode** (no cluster manager) + Delta Lake, deployed via Helm to Docker Desktop's single-node Kubernetes, single-user prototype phase, 64GB RAM / 24-core budget (resource cost is a minor factor).

---

## 1. Unity Catalog OSS (self-hosted, `github.com/unitycatalog/unitycatalog`)

### 1.1 Standalone deployment

- The server runs as a standalone Java process (JDK 17 required) started via `bin/start-uc-server`, with a Docker image buildable locally (`docker build -t unitycatalog/unitycatalog:local .`) and official images published to Docker Hub (`unitycatalog/unitycatalog`, plus a separate `unitycatalog/unitycatalog-ui` image for the web UI), per the 0.5.0/0.6.0 release notes' "Artifacts in this release" sections. ([GitHub Releases: v0.6.0](https://github.com/unitycatalog/unitycatalog/releases), [v0.5.0](https://github.com/unitycatalog/unitycatalog/releases))
- Configuration lives in `etc/conf/server.properties` (server settings, incl. `server.env` and `server.authorization`) and `etc/conf/server.log4j2.properties` (logging); logs go to `etc/logs/server.log`. ([docs.unitycatalog.io/server/configuration/](https://docs.unitycatalog.io/server/configuration/))
- **Backing storage/DB:** the metadata store is configured via `etc/conf/hibernate.properties` (Hibernate/JDBC-based). Default/dev modes use an embedded **H2** database — `server.env=test` uses an empty in-memory H2 instance; `server.env=dev` uses a file-backed H2 DB at `etc/db/h2db.mv.db` that persists across restarts. For a real backing DB, Unity Catalog documents pointing this at **PostgreSQL or MySQL** via a JDBC driver and an example config (`etc/db/postgres-example.yml`). ([docs.unitycatalog.io/server/configuration/](https://docs.unitycatalog.io/server/configuration/); web-search-located reference to `hibernate.properties` / `postgres-example.yml`, consistent with the configuration doc — verify exact filenames against the live doc when implementing)
- **Helm chart:** the `unitycatalog/unitycatalog` GitHub repo contains a `helm/` directory, and the 0.6.0 release notes explicitly reference a Helm-exposed config knob (`auth.accessTokenTimeout` mapping to `server.access-token-timeout`), confirming an official/maintained Helm chart exists as of 0.6.0. ([github.com/unitycatalog/unitycatalog](https://github.com/unitycatalog/unitycatalog), [Release notes v0.6.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- For file-backed table storage, UC supports local filesystem out of the box plus cloud object stores (S3 confirmed via `s3.bucketPath.i` / `s3.accessKey.i` / `s3.secretKey.i` / `s3.sessionToken.i` config keys, indexable for multiple buckets; Azure ABFS and GCS credential-vending are also referenced in the 0.5.0 release notes for the new `unitycatalog-hadoop` module). ([docs.unitycatalog.io/server/configuration/](https://docs.unitycatalog.io/server/configuration/); [Release notes v0.5.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0))

### 1.2 Spark + Delta Lake integration

Official integration doc: [docs.unitycatalog.io/integrations/unity-catalog-spark/](https://docs.unitycatalog.io/integrations/unity-catalog-spark/)

- Minimum versions stated there: **Apache Spark 3.5.3+** and **Delta Lake 3.2.1+**.
- The Spark connector is a **Spark catalog plugin** (`io.unitycatalog.spark.UCSingleCatalog`, implementing Spark's DataSourceV2 catalog API), *not* a Spark cluster requirement — it works with `local[*]` master, which matches this project's local-mode PySpark setup.
- Concrete config for a local session (from the official integration doc, and confirmed/extended by the 0.5.0/0.6.0 GitHub release notes which give exact `--packages` invocations):
  ```
  spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension
  spark.sql.catalog.<name>=io.unitycatalog.spark.UCSingleCatalog
  spark.sql.catalog.<name>.uri=http://localhost:8080
  spark.sql.catalog.<name>.token=<token-or-empty>
  spark.sql.defaultCatalog=<name>
  ```
- **JAR coordinates are Spark-version-pinned as of UC 0.5.0.** Starting with UC 0.5.0, the connector ships as *separate Maven artifacts per Spark minor version* rather than one universal artifact — `unitycatalog-spark_4.0_2.13`, `unitycatalog-spark_4.1_2.13`, and (new in 0.6.0) `unitycatalog-spark_4.2_2.13`. ([Release notes v0.5.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0), [v0.6.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- **Version pin table (from official release notes), UC connector ↔ Spark ↔ Delta:**

  | UC release | Spark connector artifact | Spark version | Required Delta version |
  |---|---|---|---|
  | 0.3.0 (2025-07-17) | `unitycatalog-spark_2.13:0.3.0` (single artifact) | Spark 3.5.3+ (per integration doc) | Delta 3.2.1+ (per integration doc) |
  | 0.5.0 (2026-06-18) | `unitycatalog-spark_4.0_2.13:0.5.0` / `unitycatalog-spark_4.1_2.13:0.5.0` | Spark 4.0.x / 4.1.x | **Delta 4.3.0** (release notes: "uc spark connector 0.5.0 will need to work with delta 4.3.0") |
  | 0.6.0 (2026-08-20) | `unitycatalog-spark_4.{0,1,2}_2.13:0.6.0` | Spark 4.0.x / 4.1.x / 4.2.x | **Delta 4.4.0** (release notes: "UC Spark connector 0.6.0 works with Delta Lake 4.4.0") |

  Sources: [UC 0.5.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0), [UC 0.6.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0), [UC Spark integration doc](https://docs.unitycatalog.io/integrations/unity-catalog-spark/).

  **Implication for this project:** the earlier UC 0.3.0-era combo (Spark 3.5.3 / Delta 3.2.1, single connector JAR, no Spark-version-suffixed artifacts) is the closest match to a "simple Spark 3.x install," but is now two minor UC releases and roughly a year+ behind current. Current UC releases (0.5.0+) target **Spark 4.x only** — there is no `unitycatalog-spark_3.5_2.13` artifact in the 0.5.0/0.6.0 release notes' artifact tables. This is a material constraint: if the container image is pinned to Spark 3.x, the only documented, still-listed UC Spark connector version is the older `io.unitycatalog:unitycatalog-spark_2.13:0.3.0` (paired with `delta-spark_2.13:4.0.0`+ per the integration doc's example, though the doc's stated minimum is Delta 3.2.1). This should be re-verified directly against Maven Central and the integration doc at implementation time, since UC's own docs page examples already show Delta 4.0.0 even for the older single-artifact connector.

- **Delta Lake ⇄ Unity Catalog table format note:** newer UC releases (0.5.0+) introduce a dedicated **"UC Delta API"** (`/api/2.1/unity-catalog/delta/v1/...`) for catalog-managed Delta tables, which the Spark connector uses by default from 0.5.0 onward, plus REST endpoints for credential vending, commits, and get-commits. Delta Lake's own "UniForm" feature (for Iceberg/Hudi interop) is referenced by the main UC README as a supported table format alongside Parquet/JSON/CSV. ([Release notes v0.5.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0); [unitycatalog/unitycatalog README](https://github.com/unitycatalog/unitycatalog))

### 1.3 Known self-hosting friction / rough edges

- **Spark-version churn / no long-term-stable connector pin.** The connector is now split per Spark minor version (4.0/4.1/4.2) and each UC release bumps its required Delta version (3.2.1 → 4.3.0 → 4.4.0 across just three releases in ~2 months of release cadence). A container image would need to track this pairing tightly or risk classpath/version mismatches. ([UC 0.5.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0), [UC 0.6.0](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- **View support is Spark-version-gated even within the "supported" Spark 4.x line.** As of UC 0.6.0, creating/dropping SQL views requires Spark 4.2's v2 view-catalog API; Spark 4.0/4.1 can only read views, not create them. This kind of engine-version gating on catalog features is a recurring pattern to expect. ([UC 0.6.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- **Auth/token lifetime is a moving target.** UC 0.6.0 introduced token expiration (default 24h) for access tokens issued via `/auth/tokens`, a breaking change from prior versions where tokens never expired — deployments need `server.access-token-timeout` tuned explicitly if long-lived sessions matter. ([UC 0.6.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- **PostgreSQL support for managed Delta tables was only recently fixed.** UC 0.6.0's changelog lists a bug fix: "the server could not work with PostgreSQL because of an incompatible column definition" for managed Delta tables — implying real-world Postgres-backed deployments had a functional gap before that fix. Anyone deploying UC against Postgres should be on 0.6.0+. ([UC 0.6.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.6.0))
- **No dedicated `docs/deployment.md` was retrievable at the expected path** (`github.com/unitycatalog/unitycatalog/blob/main/docs/deployment.md` returned 404 at research time) — deployment docs may have moved to `docs.unitycatalog.io/deployment/` (referenced in search results but not independently fetched here); this path should be re-verified before writing Helm chart / container-image tickets against it.

### 1.4 Governance capability: OSS reality vs. Databricks-managed marketing

- **What works in self-hosted OSS today**, per the official server docs:
  - Catalogs, schemas, tables/views/functions/models as securable objects, exposed over a REST API. ([unitycatalog.io README](https://github.com/unitycatalog/unitycatalog))
  - A **privilege/grant model**: privileges such as `USE CATALOG` and `CREATE CATALOG` can be granted to users/service principals by an admin via CLI or Python SDK; access control works by "granting privileges... on securable objects" and a principal must be explicitly granted a privilege to act. ([docs.unitycatalog.io/server/users-privileges/](https://docs.unitycatalog.io/server/users-privileges/))
  - **Authentication/authorization is off by default in local/dev usage** and is explicitly togglable: `server.authorization=disable` (no login screen, no profile menu, open access) vs. `server.authorization=enable` (external auth provider, e.g. Google/Okta, plus a local UC user database that principals must additionally be registered in — external auth success alone doesn't grant access). This is a good match for a single-user prototype phase (governance features can be exercised in `enable` mode without needing a real IdP integration to test the model) and generalizes cleanly to a future multi-user setup by flipping this one flag and wiring an IdP. ([docs.unitycatalog.io/server/auth/](https://docs.unitycatalog.io/server/auth/))
  - Credential vending / credential-scoped filesystem for cloud storage (S3/ABFS/GCS), now in a reusable `unitycatalog-hadoop` module usable outside Spark. ([UC 0.5.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.5.0))
  - "Metric views" (governed semantic layer / reusable aggregations) went from experimental (0.5.0) to fully supported (0.6.0, Spark 4.2 only) — this is a genuinely OSS-available governance-adjacent feature, not Databricks-exclusive.
- **What was not confirmed as present in OSS** (absence of evidence, not confirmed absence — flagged for follow-up): the fetched OSS docs made **no mention of audit logging or data lineage** features. Databricks' managed Unity Catalog markets lineage and audit-log capabilities prominently ([Databricks Unity Catalog docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)), but this research did not find corresponding OSS server documentation or REST endpoints for either. This should be treated as a likely **governance gap between OSS and Databricks-managed UC** until directly disproven (e.g., by grepping the `unitycatalog/unitycatalog` source for lineage/audit endpoints).
- **Multi-user carry-forward note:** the catalog/schema/table hierarchy plus the grant-based privilege model (`USE CATALOG`, `CREATE CATALOG`, presumably `SELECT`/`MODIFY` per the general permissions-model description) are the concepts that would carry into a future multi-user deployment; only the identity-provider wiring (`server.authorization=enable` + external IdP) would need to be added, not a different governance model.

---

## 2. Hive Metastore (standalone)

### 2.1 Standalone deployment

- Multiple community-maintained Docker images and Helm charts exist for standalone Hive Metastore-on-Kubernetes, none from an official Apache-published Helm chart:
  - [OKDP/hive-metastore](https://github.com/OKDP/hive-metastore) — custom Docker image + Helm chart, explicitly aimed at "Spark, Trino and Hive shar[ing] a single metadata catalog backed by PostgreSQL/MySQL and S3-compatible object storage."
  - [getindata/hive-metastore](https://github.com/getindata/hive-metastore) — Helm chart requiring a Postgres DB, configurable via chart values (host/port/db name/user/password).
  - [ssl-hep/hive-metastore](https://github.com/ssl-hep/hive-metastore) — simpler chart; runs an init-schema Kubernetes Job that waits for Postgres and builds the schema.
- **Backing DB:** all surveyed standalone deployments use **PostgreSQL** (some support MySQL) as the metastore RDBMS — this is the traditional Hive Metastore backing store; Derby is the classic embedded/single-process fallback for local/dev use but is not recommended beyond trivial testing (well-established Hive operational knowledge, not independently re-verified against an Apache Hive primary source in this pass — flag for confirmation against `cwiki.apache.org` Hive admin docs if precision is needed).
- Setup is schema-init-then-serve: a bootstrap/init job runs the Hive schema-tool against the RDBMS, then the metastore service (a Thrift server) starts and serves catalog metadata over the Thrift protocol.

### 2.2 Integration maturity with Spark + Delta Lake

- Spark's own docs describe first-class, long-standing Hive Metastore support: instantiate `SparkSession` with `.enableHiveSupport()`, place `hive-site.xml` (`core-site.xml`, `hdfs-site.xml` if relevant) on the Spark `conf/` classpath, and set `spark.sql.warehouse.dir` for the default warehouse location (this replaced the deprecated `hive.metastore.warehouse.dir` as of Spark 2.0.0). ([spark.apache.org/docs/latest/sql-data-sources-hive-tables.html](https://spark.apache.org/docs/latest/sql-data-sources-hive-tables.html))
- Spark supports a **wide range of Hive Metastore versions** via `spark.sql.hive.metastore.version` (default **2.3.10**): documented ranges are 2.0.0–2.3.10, 3.0.0–3.1.3, and 4.0.0–4.1.0, with `spark.sql.hive.metastore.jars` controlling whether Spark uses its `builtin` bundled Hive 2.3.10 client, downloads via `maven`, or uses a custom `path`/classpath. ([spark.apache.org/docs/latest/sql-data-sources-hive-tables.html](https://spark.apache.org/docs/latest/sql-data-sources-hive-tables.html))
- Delta Lake's own docs confirm Hive Metastore integration via the standard catalog config (`spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`, `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`), available "since 3.0" of Delta. Critically, Delta's docs state **the metastore is not the source of truth** for a Delta table — "the table definition in the metastore may not contain all the metadata like schema and properties" — the Delta transaction log at the table location is authoritative; Delta optionally pushes schema/property updates back to Hive asynchronously via `spark.databricks.delta.catalog.update.enabled`. ([docs.delta.io/latest/delta-batch.html](https://docs.delta.io/latest/delta-batch.html))
- This is a materially simpler, more stable integration surface than Unity Catalog's: one config pair (`spark.sql.extensions` + `spark.sql.catalog.spark_catalog=DeltaCatalog`) plus `enableHiveSupport()`, no separate per-Spark-minor-version catalog connector JAR to track, and a metastore version range that has been stable across many Spark releases (contrast UC's per-Spark-minor artifact churn documented above).

### 2.3 Pedagogical capability vs. Unity Catalog: governance model

- **Hive Metastore itself has no built-in fine-grained access-control/authorization model.** Apache Hive's own "LanguageManual Authorization" documents Hive's authorization options (legacy `Default`/storage-based authorization, `SQL standards based authorization` (`SQLStdHiveAuthorization`), and pluggable authorization) — these are Hive **query-engine** (HiveServer2/CLI) features, layered on top of, not part of, the bare Hive Metastore service. ([cwiki.apache.org Hive LanguageManual Authorization](https://hive.apache.org/docs/latest/language/languagemanual-authorization/))
- Historically, **fine-grained/centralized authorization for Hive was bolted on externally** via **Apache Ranger** or **Apache Sentry**, both of which implement authorization as plugins/agents on top of Hive (e.g., `RangerHiveAuthorizer`, configured via `hive.security.authorization.manager`), with a dedicated Ranger "Hive Metastore security agent" specifically introduced to close gaps where CLI/DDL access bypassed HiveServer2-level Ranger enforcement. ([cwiki.apache.org Ranger Plugin for Hive MetaStore](https://cwiki.apache.org/confluence/display/RANGER/Ranger+Plugin+for+Hive+MetaStore), [Cloudera blog: Hive Authorization Using Apache Ranger](https://blog.cloudera.com/best-practices-for-hive-authorization-using-apache-ranger-in-hdp-2-2/))
- **Net effect for teaching purposes:** a bare standalone Hive Metastore, as would be deployed in this project's Helm chart, gives students a real, working table/schema catalog and Spark integration, but **no governance/grants/access-control story on its own** — that would require deploying and integrating a separate system (Ranger/Sentry), which is a much larger scope than the Catalog Layer ticket. Unity Catalog (OSS), by contrast, ships its own grant/privilege model in the base server (see §1.4), even if lineage/audit are not confirmed present in OSS.

---

## 3. Version compatibility summary tables

### 3.1 Spark 3.x/4.x + Delta Lake (official Delta Lake compatibility matrix)

| Delta Lake version | Compatible Apache Spark version |
|---|---|
| 4.0.x | 4.0.x |
| 3.3.x | 3.5.x |
| 3.2.x | 3.5.x |
| 3.1.x | 3.5.x |
| 3.0.x | 3.5.x |
| 2.4.x | 3.4.x |
| 2.3.x / 2.2.x / 2.1.x | 3.3.x |
| 2.0.x | 3.2.x |
| 1.2.x / 1.1.x | 3.2.x |
| 1.0.x | 3.1.x |
| 0.7.x / 0.8.x | 3.0.x |
| < 0.7.0 | 2.4.2 – 2.4.x |

Source: [docs.delta.io/releases/](https://docs.delta.io/releases/). (Note: this table as fetched does not show a Delta 4.1.x/4.2.x row explicitly, though Delta blog posts referenced Delta 4.1.0 supporting Spark 4.1.0/4.0.1 and Delta 4.2 defaulting to Spark 4.2 while supporting 4.1.0/4.0.1 — re-check `docs.delta.io/releases/` directly at implementation time for the current full table.)

### 3.2 Spark + Delta + Unity Catalog OSS (from UC release notes, see §1.2 for full detail)

| UC connector version | Spark version | Delta version |
|---|---|---|
| `unitycatalog-spark_2.13:0.3.0` | 3.5.3+ (per integration doc) | 3.2.1+ (per integration doc; doc's own example uses 4.0.0) |
| `unitycatalog-spark_4.{0,1}_2.13:0.5.0` | 4.0.x / 4.1.x | 4.3.0 |
| `unitycatalog-spark_4.{0,1,2}_2.13:0.6.0` | 4.0.x / 4.1.x / 4.2.x | 4.4.0 |

### 3.3 Spark + Delta + Hive Metastore

| Component | Version range |
|---|---|
| Spark Hive Metastore client support (`spark.sql.hive.metastore.version`) | 2.0.0–2.3.10, 3.0.0–3.1.3, 4.0.0–4.1.0 (default: bundled 2.3.10) |
| Delta Lake Hive Metastore integration | Available since Delta 3.0 via standard `DeltaCatalog`/`DeltaSparkSessionExtension` config; stable across Delta/Spark versions per §3.1 matrix (no separate metastore-version pinning found — metastore treated as non-authoritative pointer, not a tightly coupled dependency) |

Source: [spark.apache.org Hive Tables doc](https://spark.apache.org/docs/latest/sql-data-sources-hive-tables.html), [docs.delta.io Table Batch Reads/Writes](https://docs.delta.io/latest/delta-batch.html).

---

## 4. Open items for the follow-up decision session

- Re-verify `docs.unitycatalog.io/deployment/` directly (the `docs/deployment.md` GitHub path 404'd) for the authoritative Helm chart values and Postgres/MySQL `hibernate.properties` configuration syntax before writing the Helm chart ticket.
- Confirm whether a Spark-3.5.x-compatible UC Spark connector JAR (`unitycatalog-spark_2.13:0.3.x` line) is still published/maintained on Maven Central, or whether adopting UC OSS today effectively forces a Spark 4.x upgrade for this project's container image.
- Directly inspect the `unitycatalog/unitycatalog` source/issue tracker for audit-log or lineage functionality before treating their absence from the docs as a confirmed gap.
- Confirm Derby-vs-Postgres guidance for standalone Hive Metastore against an Apache Hive primary source (this pass relied on community Helm chart READMEs, not `cwiki.apache.org`).
