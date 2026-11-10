#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/paper/build"
cd "$root/paper/supplementary"
for doc in formal-foundations safety-properties model-checking heartbench extended-results reproducibility harness2-integration; do
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$root/paper/build" "$doc.tex" > "$root/paper/build/$doc-build.txt"
done
cd "$root/docs/ieeesoftware"
pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$root/paper/build" main.tex > "$root/paper/build/main-build.txt"
python3 "$root/experiments/scripts/word_count.py" > "$root/paper/build/word-count.json"
(cd "$root/paper/build" && BIBINPUTS="$root/docs/ieeesoftware:" bibtex main > main-bibtex.txt)
pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$root/paper/build" main.tex > "$root/paper/build/main-build.txt"
pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$root/paper/build" main.tex > "$root/paper/build/main-build.txt"
