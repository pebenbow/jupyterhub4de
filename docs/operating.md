# Day-to-day operation

For building/pushing images and the first `helm install`, see
`charts/jupyterhub4de/README.md`. This doc is just the spin-up/spin-down
loop once the chart's already installed — no rebuild needed unless you've
changed `images/` or `charts/`.

## Spin up

1. Open Docker Desktop, wait for "Kubernetes is running" (bottom-left).
2. Check the release is still installed:
   ```
   helm -n jupyterhub4de list
   ```
   If it's not there (e.g. you ran `helm uninstall` last time), reinstall:
   ```
   cd charts/jupyterhub4de
   helm dependency update
   helm install jupyterhub4de . -n jupyterhub4de --create-namespace
   ```
3. Confirm pods are healthy (may take a minute after a cold Docker Desktop start):
   ```
   kubectl -n jupyterhub4de get pods
   ```
   Expect `hub`, `proxy`, `dagster`, `hive-metastore`, `<release>-postgresql`,
   and `user-scheduler` all `Running`. `hive-metastore` restarting once or
   twice early on (waiting for Postgres) is normal and self-resolves.
4. Port-forward the two UIs you need (each blocks its terminal — use
   separate tabs, or add `&` to background them):
   ```
   kubectl -n jupyterhub4de port-forward svc/proxy-public 8080:80
   kubectl -n jupyterhub4de port-forward svc/dagster 3000:3000
   ```
5. Open `http://localhost:8080` (JupyterHub — any username/password, it's
   DummyAuthenticator) and `http://localhost:3000` (Dagster).

## Spin down

Pick based on how long you're stepping away:

- **Just done for the session, keeping state**: stop the port-forwards
  (Ctrl-C) and quit Docker Desktop, or just leave it running if you'll be
  back soon. The release and its PVCs (notebook data, pipeline code, Hive
  Metastore's Postgres) persist across a Docker Desktop restart.
- **Freeing resources but keeping the deployment**: `helm` doesn't have a
  "pause" — just quit Docker Desktop (stops the whole local cluster,
  including this release) and `helm install` isn't needed next time, since
  Docker Desktop's Kubernetes state (and this namespace) comes back as-is
  when you restart it.
- **Tearing the deployment down entirely** (keeps images in GHCR, chart
  source in the repo — just removes it from the cluster):
  ```
  helm -n jupyterhub4de uninstall jupyterhub4de
  ```
  This deletes the Deployments/Services/etc. but **not** the PVCs
  (`jupyterhub4de-shared`, `hub-db-dir`, `data-jupyterhub4de-postgresql-0`)
  — add `kubectl -n jupyterhub4de delete pvc --all` if you also want to
  wipe notebook data, pipeline code, and Hive Metastore's catalog and
  start clean on the next `helm install`.

## Quick troubleshooting

- `hive-metastore` stuck restarting past the first minute: check
  `kubectl -n jupyterhub4de logs deploy/hive-metastore` — if it's a
  Postgres connection refusal, `<release>-postgresql-0` probably isn't
  ready yet; if it's `ClassNotFoundException: org.postgresql.Driver`, the
  JDBC-driver initContainer didn't run (see `templates/hive-metastore.yaml`).
- Notebook pod picked up your Dockerfile change but the running server
  didn't: Z2JH's spawner only applies a new pod template on (re)spawn —
  use **Hub Control Panel → Stop My Server**, then start it again.
- `port-forward` errors with `services "X" not found`: list the actual
  names with `kubectl -n jupyterhub4de get svc` — some subchart Services
  (e.g. Z2JH's `proxy-public`) aren't prefixed with the release name.
