"""split_words.py SEG.md OUTDIR PREFIX START [N]  - parts of exactly N words (last part = remainder).
Cuts may fall mid-sentence but never inside $...$ math or a table row. Counts = pandoc plain text."""
import re, subprocess, sys, os, functools
src, out, prefix, start = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 300
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper", "docx_build", "reference.docx")
@functools.lru_cache(maxsize=None)
def words(md):
    # Word-style count on the Word file: paragraph text incl. table cells and equation text
    import io, zipfile
    d = subprocess.run(["pandoc","-f","markdown","-t","docx","-o","-"], input=md.encode(), capture_output=True).stdout
    x = zipfile.ZipFile(io.BytesIO(d)).read("word/document.xml").decode()
    n = 0
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S):
        t = "".join(re.findall(r"<(?:w|m):t(?: [^>]*)?>([^<]*)</(?:w|m):t>", p))
        n += len([w for w in re.split(r"[ \t\r\n]+", t) if w])
    return n
blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", open(src).read()) if b.strip() and not b.startswith("![")]
# atoms: (text, weight, sep_before, kind, hdr)
atoms = []
for b in blocks:
    if b.lstrip().startswith("|"):
        L = b.split("\n"); hdr = "\n".join(L[:2])
        for i, r in enumerate(L[2:]):
            atoms.append(dict(t=r, w=words(hdr+"\n"+r)-words(hdr+"\n"+"|"+" |"*(r.count("|")-1)), sep="\n\n" if i==0 else "\n", kind="row", hdr=hdr))
        continue
    toks = re.findall(r"\$[^$]+\$\S*|\S+", b)
    for i, t in enumerate(toks):
        w = words(t) if "$" in t else 1
        atoms.append(dict(t=t, w=w, sep="\n\n" if i == 0 else " ", kind="tok"))
def render(ch):
    s, prev = "", None
    for a in ch:
        if a["kind"] == "row" and (prev is None or prev["kind"] != "row"):
            s += "\n\n" + a["hdr"] + "\n" + a["t"]
        elif prev is None:
            s += a["t"]
        else:
            s += a["sep"] + a["t"]
        prev = a
    return s.strip() + "\n"
chunks, cur, n = [], [], 0
for a in atoms:
    if cur and n + a["w"] > N:
        chunks.append(cur); cur, n = [], 0
    cur.append(a); n += a["w"]
if cur: chunks.append(cur)
# exact-fit pass: fix counts using real pandoc counts by moving boundary tokens
for k in range(len(chunks)-1):
    for _ in range(60):
        w = words(render(chunks[k]))
        if w > N:
            chunks[k+1].insert(0, chunks[k].pop())
        elif w < N and chunks[k+1] and words(render(chunks[k]+[chunks[k+1][0]])) <= N:
            chunks[k].append(chunks[k+1].pop(0))
        else:
            break
# the last part can grow during the fit pass: split it again if needed
while words(render(chunks[-1])) > N:
    tail = []
    while words(render(chunks[-1])) > N:
        tail.insert(0, chunks[-1].pop())
    chunks.append(tail)
os.makedirs(out, exist_ok=True)
for k, c in enumerate(chunks, start):
    md = render(c); fn = os.path.join(out, f"{prefix}_{k:02d}")
    open(fn+".md","w").write(md)
    subprocess.run(["pandoc", fn+".md","-f","markdown","-t","docx",f"--reference-doc={REF}","-o",fn+".docx"], check=True)
    os.remove(fn+".md")
    print(f"part {k:2d}: {words(md):3d} words | starts {md[:50]!r} | ends {md.strip()[-50:]!r}")
