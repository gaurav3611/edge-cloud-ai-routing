#!/bin/sh
# Template-style PDF (single column, matching the authors' Word template). Run from paper_v3/.
set -e
MODE=template python3 ieee_build.py
cd build/tplpdf
[ -f IEEEtran.bst ] || cp /usr/share/texlive/texmf-dist/bibtex/bst/base/ieeetr.bst IEEEtran.bst
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null || true
grep -n "^!" main.log || echo "no LaTeX errors"
pdfinfo main.pdf | grep Pages
