"""split_exact.py SEG.md OUTDIR PREFIX START [LIMIT]
Split manuscript text into Word parts of at most LIMIT (default 300) words, as close to LIMIT
as possible. Cuts only at sentence ends (never inside $...$ math) or between table rows (the
table header is repeated). Word counts are taken on pandoc's plain-text rendering, which is
what Word's word count shows for the same text (equations rendered as text)."""
import re, subprocess, sys, os, functools

src, out, prefix, start = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else 300
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "paper", "docx_build", "reference.docx")


@functools.lru_cache(maxsize=None)
def words(md):
    t = subprocess.run(["pandoc", "-f", "markdown", "-t", "plain", "--wrap=none"], input=md,
                       capture_output=True, text=True).stdout
    return len(t.split())


ABBR = r"(?<!e\.g)(?<!i\.e)(?<!Eq)(?<!Sec)(?<!al)(?<!w\.p)(?<!vs)(?<!Fig)(?<!cf)"


def sentences(p):
    # protect math, then split after . ? ! followed by space + capital/markup
    maths = []
    q = re.sub(r"\$[^$]+\$", lambda m: maths.append(m.group(0)) or f"\x00{len(maths)-1}\x00", p)
    parts = re.split(ABBR + r"(?<=[.?!])\s+(?=[A-Z*_(\[\\])", q)
    return [re.sub(r"\x00(\d+)\x00", lambda m: maths[int(m.group(1))], x) for x in parts]


blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", open(src).read()) if b.strip()]
# atoms: (text, kind, joiner)  kind: 'head' sticks to next; 'row' table row; 'sent' sentence
atoms = []
for b in blocks:
    if b.startswith("![" ):
        continue
    if b.startswith("#") or b.startswith("TABLE") or b.startswith("**Algorithm"):
        atoms.append(dict(t=b, kind="head"))
    elif b.lstrip().startswith("|"):
        lines = b.split("\n")
        hdr = "\n".join(lines[:2])
        for i, r in enumerate(lines[2:]):
            atoms.append(dict(t=r, kind="row", hdr=hdr, first=(i == 0)))
    elif re.match(r"^\d+\. ", b):
        atoms.append(dict(t=b, kind="item", newpar=True))
    else:
        ss = sentences(b)
        for i, x in enumerate(ss):
            atoms.append(dict(t=x, kind="sent", newpar=(i == 0)))


def render(chunk):
    out_, prev = [], None
    for a in chunk:
        if a["kind"] == "row":
            if prev is None or prev["kind"] != "row":
                out_.append("\n\n" + a["hdr"] + "\n" + a["t"])
            else:
                out_.append("\n" + a["t"])
        elif a["kind"] == "head":
            out_.append("\n\n" + a["t"])
        elif a["kind"] == "item":
            out_.append(("\n" if prev is not None and prev["kind"] == "item" else "\n\n") + a["t"])
        else:
            if a["newpar"] or prev is None or prev["kind"] in ("head", "row", "item"):
                out_.append("\n\n" + a["t"])
            else:
                out_.append(" " + a["t"])
        prev = a
    return "".join(out_).strip() + "\n"


chunks, cur = [], []
for a in atoms:
    trial = cur + [a]
    # a heading never ends a part: test with the heading only if something follows anyway
    if cur and words(render(trial)) > LIMIT:
        # move trailing headings to the next part
        carry = []
        while cur and cur[-1]["kind"] == "head":
            carry.insert(0, cur.pop())
        chunks.append(cur)
        cur = carry + [a]
    else:
        cur = trial
if cur:
    chunks.append(cur)

os.makedirs(out, exist_ok=True)
for k, c in enumerate(chunks, start):
    md = render(c)
    fn = os.path.join(out, f"{prefix}_{k:02d}")
    open(fn + ".md", "w").write(md)
    subprocess.run(["pandoc", fn + ".md", "-f", "markdown", "-t", "docx", f"--reference-doc={REF}",
                    "-o", fn + ".docx"], check=True)
    os.remove(fn + ".md")
    print(f"part {k:2d}: {words(md):3d} words | {md[:60]!r}")
