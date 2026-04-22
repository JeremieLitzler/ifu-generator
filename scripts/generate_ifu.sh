#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: bash scripts/generate_ifu.sh <année>" >&2
    echo "  ex:  bash scripts/generate_ifu.sh 2024" >&2
    exit 1
fi

YEAR="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"
python src/yuh_csv_ifu.py "$YEAR"
