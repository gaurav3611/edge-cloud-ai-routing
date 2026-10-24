"""ieee_build.py - convert the assembled manuscript (build/final.md) into IEEEtran LaTeX (build/ieee/main.tex).
Headings become numbered \\section/\\subsection, display equations become numbered equation
environments, pipe tables become table floats, images become figure floats, citations become \\cite."""
import re, subprocess, os, shutil

SRC = "build/final.md"
OUT = "build/ieee"
os.makedirs(OUT + "/figures", exist_ok=True)


def md2tex(md):
    t = subprocess.run(["pandoc", "-f", "markdown", "-t", "latex", "--natbib", "--wrap=none"],
                       input=md, capture_output=True, text=True, check=True).stdout.strip()
    t = re.sub(r"\\citep\{([^}]*)\}", r"\\cite{\1}", t)
    t = re.sub(r"\\citet\{([^}]*)\}", r"\\cite{\1}", t)
    t = t.replace("\\cite{", "\\cite{")
    # merge adjacent cites: \cite{a}, \cite{b} -> \cite{a,b}
    for _ in range(5):
        t = re.sub(r"\\cite\{([^}]*)\},\s*\\cite\{([^}]*)\}", r"\\cite{\1,\2}", t)
    t = t.replace("\\pandocbounded{", "{").replace("\\tightlist\n", "")
    return t


def inline(md):
    t = md2tex(md)
    return t.replace("\n\n", " ")


s = open(SRC).read()
title = re.search(r'title:\s*"([^"]+)"', s).group(1)
body = s.split("---", 2)[2]
blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", body) if b.strip()]

out = []
abstract, keywords = None, None
i = 0
in_app = False
nfig = 0
while i < len(blocks):
    b = blocks[i]
    if b.startswith("Nithish Kumar") or b.startswith("School of Computer") or b.startswith("nithishkumar"):
        i += 1; continue
    if b.strip() == "***Abstract***":
        abstract = blocks[i + 1].strip().strip("*").strip()
        i += 2; continue
    if b.startswith("***Index Terms***"):
        keywords = b.split("—", 1)[1].strip().rstrip(".")
        i += 1; continue
    m = re.match(r"^# (.*)$", b)
    if m:
        h = m.group(1).strip()
        if h.startswith("References"):
            out.append("\\bibliographystyle{IEEEtran}\n\\bibliography{refs}")
            i += 1
            # skip the citeproc refs div if present
            while i < len(blocks) and blocks[i].startswith(":::"):
                i += 1
            continue
        if h.startswith("Appendix"):
            if not in_app:
                out.append("\\appendices"); in_app = True
            h = re.sub(r"^Appendix [A-Z]:\s*", "", h)
            out.append(f"\\section{{{inline(h)}}}")
        elif h in ("Data and Code Availability", "Acknowledgment"):
            out.append(f"\\section*{{{h}}}")
        else:
            h = re.sub(r"^[IVX]+\.\s*", "", h)
            out.append(f"\\section{{{inline(h)}}}")
        i += 1; continue
    m = re.match(r"^## (.*)$", b)
    if m:
        h = re.sub(r"^[A-Z]\.\s*", "", m.group(1).strip())
        out.append(f"\\subsection{{{inline(h)}}}")
        i += 1; continue
    # display equations (possibly attached to text before/after)
    if "$$" in b:
        parts = re.split(r"(\$\$.*?\$\$)", b, flags=re.S)
        for p in parts:
            if not p.strip():
                continue
            if p.startswith("$$"):
                e = p.strip("$").strip()
                e = re.sub(r",?\\qquad\\qquad\((\d+)\)\s*$", "", e).strip()
                e = re.sub(r"\\qquad\\qquad\((\d+)\)", "", e).strip().rstrip(",").rstrip(".")
                out.append("\\begin{equation}\n" + e + "\n\\end{equation}")
            else:
                out.append(md2tex(p.strip()))
        i += 1; continue
    # figure
    m = re.match(r"^!\[(.*)\]\((.*?)\)(\{width=([\d.]+)in\})?\s*$", b, re.S)
    if m:
        cap, path, w = m.group(1), m.group(2), float(m.group(4) or 6.5)
        cap = re.sub(r"^Fig\.\s*\d+\.\s*", "", cap)
        name = os.path.basename(path)
        shutil.copy(path, f"{OUT}/figures/{name}")
        wide = w > 5
        env = "figure*" if wide else "figure"
        width = "\\textwidth" if wide else "\\columnwidth"
        nfig += 1
        out.append(f"\\begin{{{env}}}[!t]\n\\centering\n\\includegraphics[width={width}]{{figures/{name}}}\n"
                   f"\\caption{{{inline(cap)}}}\n\\label{{fig:{nfig}}}\n\\end{{{env}}}")
        i += 1; continue
    # table: caption block followed by a pipe table
    if b.startswith("TABLE") and i + 1 < len(blocks) and blocks[i + 1].lstrip().startswith("|"):
        cap = re.sub(r"^TABLE [IVX]+\.\s*", "", b.strip())
        rows = [r.strip() for r in blocks[i + 1].split("\n") if r.strip()]
        cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|?\s*-", r)]
        ncol = len(cells[0])
        wide = ncol >= 6 or sum(len(c) for c in cells[0]) > 70 or any(len(" ".join(r)) > 90 for r in cells)
        env = "table*" if wide else "table"
        width = "\\textwidth" if wide else "\\columnwidth"
        tex_rows = []
        for k, r in enumerate(cells):
            r = (r + [""] * ncol)[:ncol]
            tr = " & ".join(inline(c) if c else "" for c in r) + " \\\\"
            tex_rows.append(tr)
            if k == 0:
                tex_rows.append("\\midrule")
        long_text = any(len(c) > 40 for r in cells for c in r)
        if long_text and ncol == 2:
            colspec = "@{}p{0.34\\linewidth}p{0.62\\linewidth}@{}" if not wide else "@{}p{0.3\\linewidth}p{0.66\\linewidth}@{}"
            tab = f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n" + "\n".join(tex_rows) + "\n\\bottomrule\n\\end{tabular}"
        else:
            colspec = "l" * ncol
            tab = ("\\begin{adjustbox}{max width=" + width + "}\n\\begin{tabular}{" + colspec + "}\n\\toprule\n" +
                   "\n".join(tex_rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{adjustbox}")
        out.append(f"\\begin{{{env}}}[!t]\n\\centering\n\\caption{{{inline(cap)}}}\n\\footnotesize\n{tab}\n\\end{{{env}}}")
        i += 2; continue
    if b.lstrip().startswith("|"):
        raise SystemExit("table without caption: " + b[:80])
    out.append(md2tex(b))
    i += 1

pre = r"""\documentclass[journal]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{adjustbox}
\usepackage{cite}
\usepackage{url}
\usepackage{textcomp}
\usepackage{newunicodechar}
\newunicodechar{µ}{\ensuremath{\mu}}
\newunicodechar{±}{\ensuremath{\pm}}
\newunicodechar{×}{\ensuremath{\times}}
\newunicodechar{−}{\ensuremath{-}}
\newunicodechar{≥}{\ensuremath{\geq}}
\newunicodechar{≤}{\ensuremath{\leq}}
\newunicodechar{Φ}{\ensuremath{\Phi}}
\newunicodechar{γ}{\ensuremath{\gamma}}
\newunicodechar{ρ}{\ensuremath{\rho}}
\newunicodechar{λ}{\ensuremath{\lambda}}
\newunicodechar{Δ}{\ensuremath{\Delta}}
\newunicodechar{ℓ}{\ensuremath{\ell}}
\newunicodechar{→}{\ensuremath{\rightarrow}}
\newunicodechar{​}{}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\def\UrlBreaks{\do\/\do-\do.}
\hyphenation{EPARA TRACE}
\begin{document}
"""
authors = r"""\author{Nithish~Kumar, Ganesh~Khekare$^{*}$, and Gaurav~Nitesh~Gandhi\\[4pt]
{\normalsize School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, Tamil Nadu, India}\\
{\normalsize nithishkumar.r2023@vitstudent.ac.in, ganesh.khekare@vit.ac.in$^{*}$, gauravnitehs.gandhi2023@vitstudent.ac.in}\\
{\normalsize $^{*}$Corresponding author}}"""
tex = (pre + f"\\title{{{inline(title)}}}\n" + authors + "\n\\maketitle\n\n" +
       "\\begin{abstract}\n" + inline(abstract) + "\n\\end{abstract}\n\n" +
       "\\begin{IEEEkeywords}\n" + inline(keywords) + "\n\\end{IEEEkeywords}\n\n" +
       "\n\n".join(out) + "\n\n\\end{document}\n")
open(f"{OUT}/main.tex", "w").write(tex)
shutil.copy("../paper/refs.bib", f"{OUT}/refs.bib")
print("wrote", f"{OUT}/main.tex", len(tex), "chars;", nfig, "figures")
