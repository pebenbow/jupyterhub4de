#!/bin/bash
# PROTOTYPE entrypoint — issue #3.
# Runs a single-user JupyterHub server directly (DummyAuthenticator, no
# real hub process) so this one container can be smoke-tested standalone.
# The real Helm-chart deployment (#5) will run jupyterhub (hub) and
# jupyterhub-singleuser (spawned per user) as intended, in separate pods.
set -euo pipefail

exec jupyterhub-singleuser \
    --ip=0.0.0.0 \
    --port=8888 \
    --notebook-dir="${HOME}"
