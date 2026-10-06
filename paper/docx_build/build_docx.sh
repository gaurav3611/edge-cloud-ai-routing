#!/bin/sh
# Rebuild paper/main.docx from paper/main_modular.tex. Run from paper/.
set -e
python3 docx_build/to_docx.py
pandoc docx_build/paper_pandoc.tex -f latex -t docx -o docx_build/draft.docx \
  --reference-doc=docx_build/reference.docx --bibliography=refs.bib --csl=docx_build/ieee.csl \
  --citeproc --lua-filter=docx_build/refs_here.lua --resource-path=.:docx_build
python3 docx_build/postprocess.py docx_build/draft.docx main.docx
