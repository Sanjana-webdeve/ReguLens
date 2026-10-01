"""Cleaning -> section detection -> chunking. Preserves page, section number, heading, paragraph."""
import re
from collections import Counter
from dataclasses import dataclass

from app.ingestion.parser import Page

MAX_CHARS = 1400

NUMBERED = re.compile(
    r"^(?:(?:Section|Chapter|Part|Article|Regulation|Clause|Paragraph|Para)\s+)?(\d{1,3}(?:\.\d{1,3}){0,5})[\.\)]?\s+(\S.*)$",
    re.I | re.S)
ALPHA_HEADING = re.compile(r"^(?:(?:Chapter|Part|Section|Annex(?:ure)?)\s+[IVXLC\d]+[\.:\-]?\s*)(.*)$", re.I)


@dataclass
class ChunkData:
    page: int
    page_end: int
    section_number: str
    heading: str
    text: str


def _norm_for_repeat(s: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", s.strip().lower()))


def clean_pages(pages: list[Page]) -> list[Page]:
    """Drop repeated headers/footers and bare page numbers; de-hyphenate; collapse whitespace."""
    repeated = set()
    if len(pages) >= 4:
        cnt = Counter()
        for p in pages:
            cnt.update({_norm_for_repeat(x) for x in p.paragraphs if len(x) < 120})
        repeated = {k for k, v in cnt.items() if v >= 0.5 * len(pages)}
    out = []
    for p in pages:
        paras = []
        for para in p.paragraphs:
            if len(para) < 120 and _norm_for_repeat(para) in repeated:
                continue
            if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?", para.strip(), re.I):
                continue
            para = re.sub(r"(\w)-\n(\w)", r"\1\2", para)
            para = "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in para.split("\n") if ln.strip())
            if para:
                paras.append(para)
        out.append(Page(p.number, paras))
    return out


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, cur = [], ""
    for s in re.split(r"(?<=[.;:])\s+", text):
        if len(cur) + len(s) > MAX_CHARS and cur:
            parts.append(cur.strip())
            cur = ""
        cur += s + " "
    if cur.strip():
        parts.append(cur.strip())
    return parts


def build_chunks(pages: list[Page]) -> list[ChunkData]:
    section, heading = "", ""
    units = []  # (page, section, heading, text)
    for p in pages:
        for para in p.paragraphs:
            lines = para.split("\n")
            first = lines[0]
            m = NUMBERED.match(first)
            body = " ".join(lines)
            if m:
                num, rest = m.group(1), m.group(2)
                is_heading = len(first) <= 110 and not first.rstrip().endswith((".", ";", ":", ",")) and rest[:1].isupper()
                if is_heading:
                    section, heading = num, rest.strip()
                    body = " ".join(lines[1:]).strip()
                    if not body:
                        continue
                else:
                    section = num
            elif len(lines) == 1 and len(first) <= 90 and (first.isupper() or ALPHA_HEADING.match(first)) and len(first) > 3:
                heading = first.strip()
                continue
            units.append((p.number, section, heading, body))

    chunks: list[ChunkData] = []
    cur: ChunkData | None = None
    for page, sec, head, text in units:
        for piece in _split_long(text):
            new_section = cur is None or sec != cur.section_number
            if cur is None or new_section or len(cur.text) + len(piece) > MAX_CHARS:  # a new section always starts a new chunk (precise citations)
                if cur:
                    chunks.append(cur)
                cur = ChunkData(page, page, sec, head, piece)
            else:
                cur.text += "\n" + piece
                cur.page_end = page
    if cur:
        chunks.append(cur)
    return chunks
