#!/bin/sh
# dagster.yaml configures QueuedRunCoordinator, which only dequeues and
# launches runs via the dagster-daemon process — dagster-webserver alone
# will accept a run into the queue but never launch it. Both share
# DAGSTER_HOME's sqlite-backed storage, so they run in this one container.
set -eu

# Starting both processes against a fresh (or missing) sqlite storage file
# at once is a race: each tries to create/stamp the alembic_version table
# and one loses. Run the schema migration once, up front, so both
# processes start against an already-initialized instance.
dagster instance migrate

dagster-daemon run &
DAEMON_PID=$!

trap 'kill "$DAEMON_PID" 2>/dev/null' EXIT

exec dagster-webserver -h 0.0.0.0 -p 3000 -w /opt/dagster/app/workspace.yaml
