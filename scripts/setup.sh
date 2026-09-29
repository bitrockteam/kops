#!/bin/sh
# Kept only as a thin shim: the host preflight now lives in scripts/setup.py, standard
# library, so the host needs no Bash for it. This file exists because this sandbox's
# destructive-file-operation policy blocked removing it in the session that replaced it.
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/setup.py preflight "$@"
