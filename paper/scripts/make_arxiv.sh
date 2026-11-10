#!/bin/sh
# Build a flat arXiv package (no subfolders), so it survives any upload method.
# Run from paper/ after compiling main.tex (needs main.bbl).
set -e
rm -rf dist && mkdir -p dist/arxiv
sed -e 's#figures/fig_#fig_#g' -e 's#generated/##g' main.tex > dist/arxiv/main.tex
cp main.bbl IEEEtran.cls figures/fig_benchmark.pdf figures/fig_harness.pdf \
   generated/numbers.tex generated/tab_benchmark_rows.tex generated/tab_env_rows.tex dist/arxiv/
(cd dist/arxiv && COPYFILE_DISABLE=1 tar -czf ../carryovergate-arxiv.tar.gz *)
cp main.pdf dist/Sangaraju-carryovergate.pdf
