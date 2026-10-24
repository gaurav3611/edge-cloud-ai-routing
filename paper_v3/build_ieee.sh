#!/bin/sh
# Rebuild the IEEE PDF: render templates, assemble, convert, compile (run from paper_v3/).
set -e
for f in energy_VII abstract discussion response; do python3 render.py $f.tmpl.md $f.md; done
python3 assemble.py
python3 ieee_build.py
cd build/ieee
cp /tmp/claude-0/ieeecls/IEEEtran.cls . 2>/dev/null || true
[ -f IEEEtran.bst ] || cp /usr/share/texlive/texmf-dist/bibtex/bst/base/ieeetr.bst IEEEtran.bst
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
grep -n "^!" main.log || echo "no LaTeX errors"
pdfinfo main.pdf | grep Pages
