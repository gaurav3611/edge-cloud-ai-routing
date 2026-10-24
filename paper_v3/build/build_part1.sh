set -e
cd "$(dirname "$0")"
python3 - <<'EOF'
s=open('../static.md').read()
s=s.replace("Fig. 1 summarizes the design.","![Fig. 1. Overview of TRACE. Left: edge servers carry a clearance level $c$ and a trust domain $d$ (fill colour) and synchronize state over a ring every $H$ seconds; the cloud tier performs periodic placement and serves as a fallback for requests of sensitivity at most 1. A request may only be processed at an eligible server (green); processing a sensitivity-2 request at a clearance-0 server is blocked (red). Ingress servers relay ciphertext only. Right: the per-request decision path executed by every server.](../figures_v3/fig_arch.png){width=6.5in}\n\nFig. 1 summarizes the design.",1)
head=open('head.md').read()
open('draft.md','w').write(head+open('../intro.md').read()+"\n\n"+s+"\n\n# References\n")
EOF
R=../../paper
pandoc draft.md -t docx --citeproc --bibliography=$R/refs.bib --csl=$R/docx_build/ieee.csl --reference-doc=$R/docx_build/reference.docx --lua-filter=$R/docx_build/refs_here.lua --resource-path=.:.. -o raw.docx
python3 $R/docx_build/postprocess.py raw.docx TRACE_revision_draft_Sec_I-V.docx
pandoc draft.md -t markdown-citations-raw_html-fenced_divs-bracketed_spans-native_divs-simple_tables-multiline_tables-grid_tables --citeproc --bibliography=$R/refs.bib --csl=$R/docx_build/ieee.csl --wrap=none -o cited.md
