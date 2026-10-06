"""
to_docx.py - convert the LaTeX manuscript to an editable Word document.

Pipeline: main_modular.tex -> pandoc-friendly LaTeX (IEEE numbering made explicit,
TikZ figures replaced by 300-dpi PNG renders, algorithm as a numbered list)
-> pandoc (equations become native Word equations, IEEE-style references via citeproc).

Run from paper/:  python3 docx_build/to_docx.py
"""
import re, subprocess, os

B = "docx_build"
src = open("main_modular.tex").read()

# ---- label numbers from the LaTeX build (aux file) --------------------------------
labels = {}
for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{(.*?)\}\{", open(f"{B}/auxrun/main.aux").read()):
    k, v = m.group(1), m.group(2)
    v = v.replace("\\mbox  {", "").replace("\\mbox {", "").replace("}", "")
    if not k.startswith("leg:"):
        labels[k] = v

# ---- body only: from \maketitle to \end{document} -------------------------------------
pre, body = src.split("\\maketitle", 1)
body = body.split("\\end{document}")[0]
title = re.search(r"\\title\{(.*?)\}\n", pre).group(1)

# ---- inline generated tables, replace figures by PNGs ----------------------------------
def fig_png(m):
    name = m.group(2)
    width = "6.5in" if m.group(1) == "\\textwidth" else "4.6in"
    return f"\\includegraphics[width={width}]{{{B}/fig_{name}.png}}"
body = re.sub(r"\\resizebox\{(\\textwidth|\\columnwidth)\}\{!\}\{%\n\\input\{gen/fig_(\w+)\.tex\}\}", fig_png, body)
body = re.sub(r"\\resizebox\{\\columnwidth\}\{!\}\{%\n\\input\{(gen/tab_\w+\.tex)\}\}",
              lambda m: open(m.group(1)).read(), body)
# remaining \resizebox{...}{!}{% <tabular> } wrappers around inline tables
body = re.sub(r"\\resizebox\{\\columnwidth\}\{!\}\{%\n(\\begin\{tabular\}.*?\\end\{tabular\})\}",
              lambda m: m.group(1), body, flags=re.S)
body = body.replace("figure*", "figure").replace("table*", "table")

# ---- explicit IEEE numbering on headings ------------------------------------------------
ROM = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
out, sec, sub, in_app = [], 0, 0, False
for line in body.split("\n"):
    if line.strip() == "\\appendices":
        in_app, sec = True, 0
        continue
    m = re.match(r"\\section\{(.*?)\}(\\label\{[^}]*\})?(.*)$", line)
    if m:
        sec += 1; sub = 0
        num = f"Appendix {chr(64 + sec)}:" if in_app else f"{ROM[sec - 1]}."
        line = f"\\section*{{{num} {m.group(1)}}}" + m.group(3)
    m = re.match(r"\\subsection\{(.*?)\}(\\label\{[^}]*\})?(.*)$", line)
    if m:
        sub += 1
        line = f"\\subsection*{{{chr(64 + sub)}. {m.group(1)}}}" + m.group(3)
    out.append(line)
body = "\n".join(out)

# ---- captions with explicit "Fig. n." / "TABLE n" ---------------------------------------
def cap(env_body, kind):
    lab = re.search(r"\\label\{([^}]*)\}", env_body)
    if not lab or lab.group(1) not in labels:
        return env_body
    n = labels[lab.group(1)]
    prefix = f"Fig. {n}. " if kind == "figure" else f"TABLE {n}. "
    return re.sub(r"\\caption\{", lambda _: "\\caption{" + prefix, env_body, count=1)
body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", lambda m: cap(m.group(0), "figure"), body, flags=re.S)
body = re.sub(r"\\begin\{table\}.*?\\end\{table\}", lambda m: cap(m.group(0), "table"), body, flags=re.S)

# ---- equations: keep IEEE number as a tag ------------------------------------------------
def eq(m):
    inner = m.group(1)
    lab = re.search(r"\\label\{([^}]*)\}", inner)
    inner = re.sub(r"\\label\{[^}]*\}", "", inner).strip()
    n = labels.get(lab.group(1), "") if lab else ""
    return f"\\[ {inner} \\qquad ({n}) \\]"
body = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", eq, body, flags=re.S)

# ---- cross references --------------------------------------------------------------------
body = re.sub(r"\\eqref\{([^}]*)\}", lambda m: f"({labels.get(m.group(1), '?')})", body)
body = re.sub(r"\\ref\{([^}]*)\}", lambda m: labels.get(m.group(1), "?"), body)

# ---- algorithm as a numbered list --------------------------------------------------------
alg = r"""\noindent\textbf{Algorithm 1: \sys{} request handling at server $i$} (input: request $r$, visited set $V$, forward count $k$)
\begin{enumerate}
\item If $\mathrm{elig}(r,i)$ and $i$ is online and the local SLO is feasible: serve $r$ at $i$ and return.
\item If $k\ge K_{\max}$: serve late at $i$ if eligible, else drop; return.
\item Compute $w_{ij}(r)$ by (3) for all $j\notin V$.
\item If $\sum_j w_{ij}=0$: serve late at $i$ if eligible, else drop; return.
\item Sample $j\sim w_{ij}/\sum_{j'}w_{ij'}$ and debit $\hat\sigma_{ij}$.
\item Forward $r$ to $j$ with $V\cup\{j\}$ and $k+1$.
\end{enumerate}"""
body = re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", lambda _: alg, body, flags=re.S)

# ---- IEEE-specific commands ----------------------------------------------------------------
body = body.replace("\\IEEEPARstart{A}{I}", "AI")
body = re.sub(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}",
              lambda m: "\\noindent\\textbf{\\textit{Index Terms}}---" + m.group(1).strip(), body, flags=re.S)
body = re.sub(r"\\begin\{IEEEbiographynophoto\}\{(.*?)\}(.*?)\\end\{IEEEbiographynophoto\}",
              lambda m: f"\\noindent\\textbf{{{m.group(1)}}} {m.group(2).strip()}", body, flags=re.S)
body = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
              lambda _: "\\section*{References}\n", body, flags=re.S)
body = re.sub(r"(?m)^%.*\n", "", body)                     # comment lines
body = body.replace("\\centering", "")

affil = ("[First Author Name] and [Second Author Name] are with the [Department], [University], "
         "[City], [Country] (e-mail: [first.author@university.edu]; [second.author@university.edu]). "
         "Manuscript received [Month Day, Year]; revised [Month Day, Year].")
doc = f"""\\documentclass{{article}}
\\usepackage{{amsmath,amssymb,graphicx}}
\\newcommand{{\\sys}}{{\\textsc{{Trace}}}}
\\title{{{title}}}
\\author{{[First Author Name], [Student Member, IEEE] \\and [Second Author Name], [Member, IEEE]}}
\\date{{{affil}}}
\\begin{{document}}
\\maketitle
{body}
\\end{{document}}
"""
open(f"{B}/paper_pandoc.tex", "w").write(doc)
print("labels used:", len(labels))
