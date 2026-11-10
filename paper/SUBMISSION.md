# Submission package: "Carryovergate: Derivation-Authority Gating at Re-fire Time for LLM Agents"

## Files
- `dist/carryovergate-arxiv.tar.gz`: arXiv source upload, flat (no subfolders), 6 files; table rows are inlined so arXiv's scanner sees every file as used. Tested: extracts and compiles with pdflatex alone, using the shipped `main.bbl`. 6 pages.
- `dist/Sangaraju-carryovergate.pdf`: the compiled PDF, for the AGENT'27 HotCRP upload.
- `arxiv_abstract.txt`: plain-text abstract for the arXiv form (1,505 characters; the limit is 1,920).

## Rebuilding
```
python3 scripts/build_bib.py > refs.bib      # every reference pulled from arXiv / Crossref
python scripts/make_figures.py               # needs matplotlib; reads runs/full-v02-20261108T0432Z/metrics.json
pdflatex main && bibtex main && pdflatex main && pdflatex main
sh scripts/make_arxiv.sh                     # flat arXiv package in dist/ (no subfolders)
```

## arXiv form
- Title: Carryovergate: Derivation-Authority Gating at Re-fire Time for LLM Agents
- Authors: Venkata M Sangaraju
- Primary category: cs.CR. Suggested cross-lists: cs.AI, cs.SE.
- Comments: "6 pages, 3 figures, 3 tables. Code, preregistrations and per-sample results: https://github.com/sangaraju1988/carryovergate"
- License: your choice. CC BY 4.0 is common, and arXiv's non-exclusive licence is the most compatible with a later IEEE copyright transfer.

## AGENT'27 (ICSE 2027 workshop)
- Deadline: Fri 20 Nov 2026 AoE (extended from 13 Nov). Notification 11 Dec 2026, camera-ready 29 Jan 2027.
- Submission site: https://icse2027-agent.hotcrp.com/
- Full paper: up to 8 pages *including* references, IEEE conference template, single-anonymous review (names stay on). This paper is 6 pages.
- Source checked: https://conf.researchr.org/home/icse-2027/agent-2027. Re-read it before submitting, because the dates have moved once already.

## Before you submit
Done:
- `paper/` is pushed, so the Availability section's claim about the scripts is true.
- The placeholder Notes heading was removed from the v0.2 report.
- The email was removed from the author block. PDF metadata carries the title and author.
- arXiv endorsement is in place.

Still yours to do:
1. Keep the AI-assistance acknowledgment (IEEE requires one), but adjust its wording to match exactly how you used the tools.
2. Read the whole paper yourself. You are the author of record for every sentence.
