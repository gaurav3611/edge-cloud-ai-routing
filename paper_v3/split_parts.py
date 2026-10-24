"""split_parts.py CITED.md OUTDIR PREFIX - split a citation-resolved manuscript into ~300-word
Word parts at paragraph boundaries. Headings, table captions and the algorithm caption stay
with the block that follows them; tables, equations and numbered lists are never split."""
import re, subprocess, sys, os

src, out, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
REF = os.path.join(os.path.dirname(__file__), "..", "paper", "docx_build", "reference.docx")
s = open(src).read()
start = s.index("# ") if "# " in s else 0
end = s.index("# References") if "# References" in s else len(s)
blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", s[start:end]) if b.strip()]
blocks = [b for b in blocks if not b.startswith("![")]


def wc(b):
    b = re.sub(r"\$[^$]*\$", "x", b)
    return len(re.findall(r"[A-Za-z0-9][\w'’\-]*", b))


def sticky(b):  # must stay with the next block
    return b.startswith("#") or b.startswith("TABLE") or b.startswith("**Algorithm")


units, cur = [], []
for b in blocks:
    if cur and (re.match(r"^\d+\. ", b) and re.match(r"^\d+\. ", cur[-1]) or sticky(cur[-1])):
        cur.append(b)
    else:
        if cur:
            units.append(cur)
        cur = [b]
if cur:
    units.append(cur)

chunks, ch, n = [], [], 0
for u in units:
    w = sum(wc(b) for b in u)
    if ch and n >= 220 and n + w > 340:
        chunks.append((ch, n)); ch, n = [], 0
    ch += u; n += w
if ch:
    if chunks and n < 120:            # fold a tiny tail into the previous part
        prev, pn = chunks.pop(); ch, n = prev + ch, pn + n
    chunks.append((ch, n))

os.makedirs(out, exist_ok=True)
N = len(chunks)
for k, (c, n) in enumerate(chunks, 1):
    fn = os.path.join(out, f"{prefix}_{k:02d}_of_{N:02d}")
    open(fn + ".md", "w").write("\n\n".join(c) + "\n")
    subprocess.run(["pandoc", fn + ".md", "-f", "markdown", "-t", "docx", f"--reference-doc={REF}",
                    "-o", fn + ".docx"], check=True)
    os.remove(fn + ".md")
    print(f"part {k:2d}: {n:3d} words  | {c[0][:70]!r}")
