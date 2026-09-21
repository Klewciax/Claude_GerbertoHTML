#!/usr/bin/env bash
# Mozna uruchomic z dowolnego katalogu: bash examples/minimal/run_example.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Pozwala uruchomic "python3 -m pcb_report" bez wczesniejszego "pip install -e .",
# niezaleznie od katalogu, z ktorego ten skrypt zostal wywolany.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

cd "$SCRIPT_DIR"
# Auto-wykrywanie: bez podawania nazw plików (patrz README, sekcja "auto-wykrywanie plikow").
python3 -m pcb_report . -o report.html

echo
echo "Gotowe: $SCRIPT_DIR/report.html"
