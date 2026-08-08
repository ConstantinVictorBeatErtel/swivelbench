"""Write real Excel (.xlsx) and Word (.docx) files with the stdlib only.

OOXML is a zip of XML parts. Good enough for open-in-Excel/Word and for the
viz to deep-link; not a full Office feature surface.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def write_xlsx(path: Path, *, title: str, rows: list[tuple[str, object]]) -> Path:
    """Write a one-sheet workbook. `rows` are (label, value) pairs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_rows = [
        _xlsx_row(1, [("Financial model",), (title,)]),
        _xlsx_row(2, [("Field",), ("Value",)]),
    ]
    for i, (k, v) in enumerate(rows, start=3):
        sheet_rows.append(_xlsx_row(i, [(str(k),), (v,)]))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    wb = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Model" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


def _xlsx_row(r: int, cells: list[tuple]) -> str:
    parts = []
    for i, cell in enumerate(cells):
        col = chr(ord("A") + i)
        ref = f"{col}{r}"
        val = cell[0]
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            parts.append(f'<c r="{ref}"><v>{val}</v></c>')
        else:
            parts.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>'
            )
    return f'<row r="{r}">{"".join(parts)}</row>'


def write_docx(path: Path, *, title: str, sections: list[tuple[str, str]]) -> Path:
    """Write a simple multi-heading Word memo."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    paras = [_p(title, bold=True, size=28)]
    for heading, body in sections:
        paras.append(_p(heading, bold=True, size=22))
        for line in (body or "").splitlines() or [""]:
            paras.append(_p(line, size=20))
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paras)}<w:sectPr/></w:body></w:document>'
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return path


def _p(text: str, *, bold: bool = False, size: int = 20) -> str:
    rpr = f'<w:rPr><w:sz w:val="{size}"/>{"<w:b/>" if bold else ""}</w:rPr>'
    return (
        "<w:p><w:r>"
        f"{rpr}<w:t xml:space=\"preserve\">{escape(text)}</w:t>"
        "</w:r></w:p>"
    )
