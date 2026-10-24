"""wordcount.py FILE.docx... - Word-style count: text of all paragraphs (incl. table cells and
equation text), words separated by ordinary whitespace."""
import re, sys, zipfile
for f in sys.argv[1:]:
    x = zipfile.ZipFile(f).read("word/document.xml").decode()
    n = 0
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S):
        t = "".join(re.findall(r"<(?:w|m):t(?: [^>]*)?>([^<]*)</(?:w|m):t>", p))
        n += len([w for w in re.split(r"[ \t\r\n]+", t) if w])
    print(f"{n:4d}  {f.split('/')[-1]}")
