"""
postprocess.py IN.docx OUT.docx - fix pandoc's Word tables.

1. Column widths: pandoc gives every column the same narrow width; size each table to the
   full text width (6.5 in) with columns proportional to their longest cell text.
2. Math-only cells: Word renders a paragraph that contains nothing but an equation as a
   centred display equation; a zero-width space keeps it inline and left-aligned.
"""
import re, sys, zipfile

src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src)
xml = zin.read("word/document.xml").decode("utf8")
FULL = 9360  # 6.5 in in twips


def text_len(cell_xml):
    t = "".join(re.findall(r"<(?:w|m):t[^>]*>([^<]*)</(?:w|m):t>", cell_xml))
    return len(t.strip())


def fix_table(tbl):
    rows = re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S)
    ncol = len(re.findall(r"<w:gridCol ", tbl))
    if ncol == 0:
        return tbl
    widest = [3] * ncol
    for r in rows:
        col = 0
        for c in re.findall(r"<w:tc>.*?</w:tc>", r, re.S):
            span = re.search(r'<w:gridSpan w:val="(\d+)"', c)
            span = int(span.group(1)) if span else 1
            if span == 1 and col < ncol:
                widest[col] = max(widest[col], min(text_len(c), 48))
            col += span
    total = sum(widest)
    widths = [max(500, round(FULL * w / total)) for w in widest]
    widths[-1] += FULL - sum(widths)
    grid = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}" />' for w in widths) + "</w:tblGrid>"
    tbl = re.sub(r"<w:tblGrid>.*?</w:tblGrid>", grid, tbl, flags=re.S)
    tbl = re.sub(r'<w:tblW [^>]*/>', f'<w:tblW w:type="dxa" w:w="{FULL}" />', tbl)
    tbl = re.sub(r"<w:tcW [^>]*/>", "", tbl)

    def inline_math(p):
        body = re.sub(r"<m:oMath>.*?</m:oMath>", "", p, flags=re.S)
        if "<m:oMath>" in p and "<w:t" not in body:
            zw = '<w:r><w:t xml:space="preserve">​</w:t></w:r>'
            if "</w:pPr>" in p:
                return p.replace("</w:pPr>", "</w:pPr>" + zw, 1)
            return re.sub(r"^<w:p( [^>]*)?>", lambda m: m.group(0) + zw, p)
        return p
    return re.sub(r"<w:p( [^>]*)?>.*?</w:p>", lambda m: inline_math(m.group(0)), tbl, flags=re.S)


xml, n = re.subn(r"<w:tbl>.*?</w:tbl>", lambda m: fix_table(m.group(0)), xml, flags=re.S)
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = xml.encode("utf8") if item.filename == "word/document.xml" else zin.read(item.filename)
        zout.writestr(item, data)
print("tables fixed:", n)
