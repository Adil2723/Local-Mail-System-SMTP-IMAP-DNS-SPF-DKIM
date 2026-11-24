#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec docker compose -f network/compose.yaml -f network/compose.beta.yaml -f network/compose.imap.yaml -f network/compose.integration.yaml -f network/compose.spf.yaml -f network/compose.dkim.yaml -f network/compose.alpha-imap.yaml "$@"
