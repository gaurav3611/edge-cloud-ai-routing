"""template_docx.py TEMPLATE.docx OUT.docx - build the revised manuscript (build/final.md) in the
formatting of the user's template: Times New Roman; 20 pt bold centred title; 14 pt centred author
block; bold-italic 10 pt "Abstract" heading; bold 10 pt justified abstract; 11 pt justified body;
small-caps centred section headings; italic subsection headings; 9 pt captions; 9 pt tables with
top/bottom rules and a ruled bold header row; 9 pt hanging-indent references."""
import re, sys, os, zipfile, shutil, subprocess

TPL, OUT = sys.argv[1], sys.argv[2]
B = "build/tpl"
os.makedirs(B, exist_ok=True)
TNR = '<w:rFonts w:ascii="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman"/>'


def pstyle(sid, name, ppr, rpr, based="Normal", nxt=None, kind="paragraph", custom=True):
    n = f'<w:next w:val="{nxt}"/>' if nxt else ""
    c = ' w:customStyle="1"' if custom else ""
    return (f'<w:style w:type="{kind}"{c} w:styleId="{sid}"><w:name w:val="{name}"/><w:basedOn w:val="{based}"/>{n}'
            f'<w:qFormat/><w:pPr>{ppr}</w:pPr><w:rPr>{TNR}<w:color w:val="000000"/>{rpr}</w:rPr></w:style>')


SP = lambda b, a, extra="": f'<w:spacing w:before="{b}" w:after="{a}" w:line="264" w:lineRule="auto"/>{extra}'
SZ = lambda s: f'<w:sz w:val="{s}"/><w:szCs w:val="{s}"/>'
NEW = [
    pstyle("BodyText", "Body Text", SP(0, 120) + '<w:jc w:val="both"/>', SZ(22), custom=False),
    pstyle("FirstParagraph", "First Paragraph", SP(0, 120) + '<w:jc w:val="both"/>', SZ(22), based="BodyText"),
    pstyle("Compact", "Compact", SP(0, 60) + '<w:jc w:val="both"/>', SZ(22), based="BodyText"),
    pstyle("ImageCaption", "Image Caption", SP(60, 200) + '<w:jc w:val="both"/>', SZ(18)),
    pstyle("TableCaption", "Table Caption", '<w:keepNext/>' + SP(60, 160) + '<w:jc w:val="center"/>', SZ(18)),
    pstyle("CaptionedFigure", "Captioned Figure", '<w:keepNext/>' + SP(120, 0) + '<w:jc w:val="center"/>', SZ(22)),
    pstyle("Figure", "Figure", '<w:keepNext/>' + SP(120, 0) + '<w:jc w:val="center"/>', SZ(22)),
    pstyle("Bibliography", "Bibliography", SP(0, 60) + '<w:ind w:left="400" w:hanging="400"/><w:jc w:val="left"/>', SZ(18)),
    pstyle("TableText", "Table Text", '<w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>', SZ(18)),
    pstyle("TableTextSmall", "Table Text Small", '<w:spacing w:before="10" w:after="10" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>', SZ(15)),
    pstyle("AuthorBlock", "Author Block", '<w:keepNext/>' + SP(0, 80) + '<w:jc w:val="center"/>', SZ(28)),
    pstyle("AbstractHeading", "Abstract Heading", '<w:keepNext/>' + SP(120, 60) + '<w:jc w:val="left"/>',
           '<w:b/><w:bCs/><w:i/><w:iCs/>' + SZ(20)),
    pstyle("AbstractText", "Abstract Text", SP(0, 200) + '<w:jc w:val="both"/>', '<w:b/><w:bCs/>' + SZ(20)),
    pstyle("IndexTerms", "Index Terms", SP(0, 120) + '<w:jc w:val="both"/>', SZ(22)),
    ('<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:rPr>'
     '<w:color w:val="156082"/><w:u w:val="single"/></w:rPr></w:style>'),
    ('<w:style w:type="table" w:styleId="Table"><w:name w:val="Table"/><w:basedOn w:val="TableNormal"/>'
     '<w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>'
     f'<w:rPr>{TNR}' + SZ(18) + '</w:rPr><w:tblPr><w:jc w:val="center"/><w:tblBorders>'
     '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
     '</w:tblBorders><w:tblCellMar><w:top w:w="20" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
     '<w:bottom w:w="20" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
     '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr><w:tcPr><w:tcBorders>'
     '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders><w:vAlign w:val="bottom"/>'
     '</w:tcPr></w:tblStylePr></w:style>'),
    ('<w:style w:type="table" w:styleId="TableSmall"><w:name w:val="Table Small"/><w:basedOn w:val="Table"/>'
     '<w:pPr><w:spacing w:before="10" w:after="10" w:line="240" w:lineRule="auto"/></w:pPr>'
     f'<w:rPr>{TNR}' + SZ(14) + '</w:rPr><w:tblPr><w:tblCellMar><w:top w:w="10" w:type="dxa"/><w:left w:w="40" w:type="dxa"/>'
     '<w:bottom w:w="10" w:type="dxa"/><w:right w:w="40" w:type="dxa"/></w:tblCellMar></w:tblPr>'
     '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr><w:tcPr><w:tcBorders>'
     '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders><w:vAlign w:val="bottom"/>'
     '</w:tcPr></w:tblStylePr></w:style>'),
]

# ---- 1. reference.docx = template with its styles extended -------------------------------
ref = f"{B}/reference.docx"
zin = zipfile.ZipFile(TPL)
st = zin.read("word/styles.xml").decode()
st = st.replace('<w:rPrDefault><w:rPr>', f'<w:rPrDefault><w:rPr>{TNR}<w:color w:val="000000"/>', 1)
for s in NEW:
    sid = re.search(r'w:styleId="([^"]+)"', s).group(1)
    st = re.sub(rf'<w:style [^>]*w:styleId="{sid}".*?</w:style>', "", st, flags=re.S)
    st = st.replace("</w:styles>", s + "</w:styles>")
doc = zin.read("word/document.xml").decode()
sect = re.search(r"<w:sectPr.*?</w:sectPr>", doc, re.S).group(0)
body = re.sub(r"<w:body>.*</w:body>", f"<w:body><w:p/>{sect}</w:body>", doc, flags=re.S)
with zipfile.ZipFile(ref, "w", zipfile.ZIP_DEFLATED) as z:
    for it in zin.infolist():
        if it.filename.startswith("word/media/"):
            continue
        data = zin.read(it.filename)
        if it.filename == "word/styles.xml":
            data = st.encode()
        elif it.filename == "word/document.xml":
            data = body.encode()
        elif it.filename == "word/_rels/document.xml.rels":
            data = re.sub(r'<Relationship [^>]*media/[^>]*/>', "", data.decode()).encode()
        z.writestr(it, data)

# ---- 2. manuscript markdown with the front matter in template styles ----------------------
md = open("build/final.md").read()
fm, rest = md.split("***Abstract***", 1)
title = re.search(r'title:\s*"([^"]+)"', fm).group(1)
abstract, rest = rest.split("***Index Terms***", 1)
idx, rest = rest.split("\n", 1)
emails = ["nithishkumar.r2023@vitstudent.ac.in", "ganesh.khekare@vit.ac.in", "gauravnitehs.gandhi2023@vitstudent.ac.in"]
links = ", ".join(f"[{e}](mailto:{e})" + ("^\\*^" if "khekare" in e else "") for e in emails)
front = f'''---
title: "{title}"
---

::: {{custom-style="AuthorBlock"}}
Nithish Kumar, Ganesh Khekare^\\*^, and Gaurav Nitesh Gandhi

School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, Tamil Nadu, India

{links}
:::

::: {{custom-style="AbstractHeading"}}
Abstract
:::

::: {{custom-style="AbstractText"}}
{abstract.strip().strip("*").strip()}
:::

::: {{custom-style="IndexTerms"}}
***Index Terms***{idx.strip()}
:::
'''
open(f"{B}/manuscript.md", "w").write(front + rest)

# ---- 3. pandoc + table widths -------------------------------------------------------------
R = "../paper"
subprocess.run(["pandoc", f"{B}/manuscript.md", "-t", "docx", "--citeproc", f"--bibliography={R}/refs.bib",
                f"--csl={R}/docx_build/ieee.csl", f"--reference-doc={ref}", f"--lua-filter={R}/docx_build/refs_here.lua",
                "--resource-path=.:build:..", "-o", f"{B}/raw.docx"], check=True)
subprocess.run(["python3", f"{R}/docx_build/postprocess.py", f"{B}/raw.docx", f"{B}/fixed.docx"], check=True)
# wide tables (7+ columns): compact style so that every value stays on one line
zin = zipfile.ZipFile(f"{B}/fixed.docx")
x = zin.read("word/document.xml").decode()
def small(t):
    t = t.group(0)
    wide = len(re.findall(r"<w:gridCol ", t)) >= 7
    if wide:
        t = re.sub(r'<w:tblStyle w:val="[^"]*"\s*/>', '<w:tblStyle w:val="TableSmall" />', t)
    ps = "TableTextSmall" if wide else "TableText"
    t = re.sub(r'<w:pStyle w:val="(Compact|BodyText|FirstParagraph)"\s*/>', f'<w:pStyle w:val="{ps}" />', t)
    return t
x = re.sub(r"<w:tbl>.*?</w:tbl>", small, x, flags=re.S)
def tcap(p):
    p = p.group(0)
    txt = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
    if re.match(r"TABLE [IVX]+\.", txt):
        p = re.sub(r'<w:pStyle w:val="[^"]*"\s*/>', '<w:pStyle w:val="TableCaption" />', p, count=1)
    return p
x = re.sub(r"<w:p>.*?</w:p>|<w:p [^>]*>.*?</w:p>", tcap, x, flags=re.S)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for it in zin.infolist():
        z.writestr(it, x.encode() if it.filename == "word/document.xml" else zin.read(it.filename))
print("wrote", OUT)
