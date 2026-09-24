#!/usr/bin/env python3
"""HTML report -> Markdown full-content conversion (stdlib only).
Handles: h1-h6, p, ul/ol/li, table/tr/th/td, strong/em/code, blockquote, br, a.
Skips script/style/head. Usage: html2md.py <file.html> [more...]"""
import html.parser
import pathlib
import re
import sys


class MD(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0          # inside script/style/head
        self.list_stack = []   # ('ul'|'ol', counter)
        self.in_table = False
        self.rows = []         # collected rows of current table
        self.cur_row = None
        self.cur_cell = None
        self.link_href = None
        self.in_heading = 0
        self.in_pre = False

    def w(self, s):
        if self.skip:
            return
        if self.cur_cell is not None:
            self.cur_cell.append(s)
        elif not self.in_table:
            self.out.append(s)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
            self.in_heading += 1
        elif tag == "p":
            self.out.append("\n\n")
        elif tag == "br":
            self.w("  \n")
        elif tag in ("strong", "b"):
            self.w("**")
        elif tag in ("em", "i"):
            self.w("*")
        elif tag == "code":
            self.w("`")
        elif tag == "pre":
            self.in_pre = True
            self.out.append("\n\n```\n")
        elif tag == "blockquote":
            self.out.append("\n\n> ")
        elif tag == "a":
            self.link_href = dict(attrs).get("href")
            self.w("[")
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
            self.out.append("\n")
        elif tag in ("div", "section", "article", "header", "footer", "figure",
                     "figcaption", "main", "aside"):
            self.out.append("\n")  # block boundary: unglue card/stat siblings
        elif tag == "li":
            if self.list_stack:
                kind = self.list_stack[-1]
                kind[1] += 1
                mark = "-" if kind[0] == "ul" else f"{kind[1]}."
                self.out.append("\n" + "  " * (len(self.list_stack) - 1) + mark + " ")
        elif tag == "table":
            self.in_table = True
            self.rows = []
        elif tag == "tr":
            self.cur_row = []
        elif tag in ("th", "td"):
            self.cur_cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip -= 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_heading -= 1
            self.out.append("\n")
        elif tag in ("p", "blockquote"):
            self.out.append("\n")
        elif tag == "span" and self.in_heading:
            self.w(" ")  # eyebrow-span inside heading: "</span>Модель" glue
        elif tag in ("div", "section", "article", "header", "footer", "figure",
                     "figcaption", "main", "aside"):
            self.out.append("\n")
        elif tag in ("strong", "b"):
            self.w("**")
        elif tag in ("em", "i"):
            self.w("*")
        elif tag == "code":
            self.w("`")
        elif tag == "pre":
            self.in_pre = False
            self.out.append("\n```\n")
        elif tag == "a":
            self.w("]")
            if self.link_href and not self.link_href.startswith("#"):
                self.w(f"({self.link_href})")
            self.link_href = None
        elif tag in ("ul", "ol"):
            self.list_stack.pop()
            self.out.append("\n")
        elif tag in ("th", "td") and self.cur_cell is not None:
            cell = re.sub(r"\s+", " ", "".join(self.cur_cell)).strip().replace("|", "\\|")
            self.cur_row.append(cell)
            self.cur_cell = None
        elif tag == "tr" and self.cur_row is not None:
            if any(c for c in self.cur_row):
                self.rows.append(self.cur_row)
            self.cur_row = None
        elif tag == "table":
            self.in_table = False
            if self.rows:
                width = max(len(r) for r in self.rows)
                rows = [r + [""] * (width - len(r)) for r in self.rows]
                self.out.append("\n\n")
                self.out.append("| " + " | ".join(rows[0]) + " |\n")
                self.out.append("|" + " --- |" * width + "\n")
                for r in rows[1:]:
                    self.out.append("| " + " | ".join(r) + " |\n")
                self.out.append("\n")

    def handle_data(self, data):
        if self.in_pre and not self.in_table:
            self.w(data.rstrip("\n") + "\n" if data.strip() else "")
        else:
            self.w(data if self.in_table else re.sub(r"\s+", " ", data))


def convert(path: pathlib.Path) -> pathlib.Path:
    p = MD()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = "".join(p.out)
    # junk lines: whitespace-only -> truly empty, then collapse 3+ newlines
    text = "\n".join(ln.rstrip() for ln in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    # space-squeeze only OUTSIDE fenced code blocks (pre keeps its indent)
    parts = re.split(r"(```)", text)
    in_fence = False
    for k, part in enumerate(parts):
        if part == "```":
            in_fence = not in_fence
            continue
        if not in_fence:
            parts[k] = re.sub(r" +", " ", part)
    text = "".join(parts)
    text = re.sub(r"\*\*\s+\*\*", "", text)
    # chart/stat pairs across one blank line: "label\n\n9 316" -> "label — 9 316";
    # "10/10\n\nрешено на high" -> "10/10 решено на high"
    num = r"[\d][\d\s.,%×$/₽-]*"
    lines = text.split("\n")
    merged, i = [], 0
    while i < len(lines):
        cur = lines[i]
        j = i + 1 + (1 if i + 1 < len(lines) and lines[i + 1] == "" else 0)
        nxt = lines[j] if j < len(lines) else ""
        if (cur and nxt and not cur.startswith(("|", "#", "- ", "```"))
                and not nxt.startswith(("|", "#", "- ", "```"))
                and not cur.rstrip().endswith((".", "!", "?", ":"))):
            if re.fullmatch(num, nxt.strip()) and not re.fullmatch(num, cur.strip()):
                merged.append(cur.rstrip() + " — " + nxt.strip())
                i = j + 1
                continue
            if re.fullmatch(num, cur.strip()) and len(cur.strip()) <= 12:
                merged.append(cur.strip() + " " + nxt.strip())
                i = j + 1
                continue
        merged.append(cur)
        i += 1
    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    dst = path.with_suffix(".md")
    dst.write_text(text, encoding="utf-8")
    return dst


for arg in sys.argv[1:]:
    f = pathlib.Path(arg)
    out = convert(f)
    print(f"OK {out.name}: {len(out.read_text(encoding='utf-8'))} симв.")
