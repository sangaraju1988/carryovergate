#!/bin/sh
# Build a flat arXiv package (no subfolders). The generated table rows are pasted
# straight into main.tex, because arXiv's file scanner does not see \rowsfrom
# (a primitive \@@input) and would mark the row files as unused.
# Run from paper/ after compiling main.tex (needs main.bbl).
set -e
rm -rf dist && mkdir -p dist/arxiv
python3 - <<'PY'
import re
s = open("main.tex").read()
s = re.sub(r"\\rowsfrom\{generated/([^}]+)\}", lambda m: open("generated/" + m.group(1)).read().rstrip("\n"), s)
s = s.replace("figures/fig_", "fig_").replace("\\input{generated/numbers.tex}", "\\input{numbers.tex}")
assert "\\rowsfrom{" not in s.split("\\begin{document}")[1]
open("dist/arxiv/main.tex", "w").write(s)
PY
cp main.bbl IEEEtran.cls figures/fig_benchmark.pdf figures/fig_harness.pdf generated/numbers.tex dist/arxiv/
(cd dist/arxiv && COPYFILE_DISABLE=1 tar -czf ../carryovergate-arxiv.tar.gz *)
cp main.pdf dist/Sangaraju-carryovergate.pdf
