-- Move the citeproc reference list (Div#refs, appended at the end of the document)
-- to directly under the "References" heading, before the appendices.
-- Must run AFTER --citeproc.
function Pandoc(doc)
  local refs, rest = nil, {}
  for _, b in ipairs(doc.blocks) do
    if b.t == "Div" and b.identifier == "refs" then refs = b else table.insert(rest, b) end
  end
  if not refs then return doc end
  local out = {}
  for _, b in ipairs(rest) do
    table.insert(out, b)
    if b.t == "Header" and pandoc.utils.stringify(b) == "References" then table.insert(out, refs) end
  end
  doc.blocks = out
  return doc
end
