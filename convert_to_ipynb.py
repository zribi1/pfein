"""Convert the Colab-style .py into a real .ipynb that Colab can open."""
import json
import re
import sys
from pathlib import Path

SRC = Path(r"c:\Users\MSI\Desktop\Pfein\pfefm_complete_optimized_colab.py")
DST = Path(r"c:\Users\MSI\Desktop\Pfein\pfefm_complete_optimized_colab.ipynb")

text = SRC.read_text(encoding="utf-8")

# Drop the leading "# -*- coding: utf-8 -*-" line (Colab adds this back).
lines = text.splitlines()
if lines and lines[0].startswith("# -*-"):
    lines = lines[1:]
text = "\n".join(lines)

# Strategy: split into cells. Conventions used in the source file:
#   - A top-level triple-quoted string at column 0 is a MARKDOWN cell.
#   - Everything else is grouped into CODE cells, split at lines that
#     start with "# ============================================================"
#     followed by another "# ============" line below. We treat each
#     "# === ... # === ... # ===" header block as the start of a new code cell.

cells = []

# 1. Pull out top-level triple-quoted blocks first.
# Pattern matches """...""" that starts at col 0.
md_pattern = re.compile(r'(?ms)^"""(.*?)"""\s*$')

# Tokenize: walk through file capturing markdown blocks and code in between.
pos = 0
tokens = []
for m in md_pattern.finditer(text):
    if m.start() > pos:
        tokens.append(("code", text[pos:m.start()]))
    tokens.append(("markdown", m.group(1).strip()))
    pos = m.end()
if pos < len(text):
    tokens.append(("code", text[pos:]))

# 2. Inside each "code" token, split into multiple code cells at section
# headers (lines of "# ===..." that look like a banner).
HEADER = re.compile(r"^# ={20,}\s*$", re.MULTILINE)

def split_code_into_cells(code: str):
    """Split a chunk of code into smaller cells using "# ===..." banners."""
    if not code.strip():
        return []
    # Find banner positions; each banner pair (top + title + bottom) marks
    # the START of a new cell. We treat any single banner line as a cut.
    parts = []
    last = 0
    matches = list(HEADER.finditer(code))
    if not matches:
        return [code.strip()]
    # Walk through banners. Group consecutive banner lines as one boundary.
    boundaries = []
    i = 0
    while i < len(matches):
        # find a "header block" = banner, optional comment lines, banner
        start = matches[i].start()
        boundaries.append(start)
        # skip subsequent banners that are within ~10 lines (the closing one)
        j = i + 1
        while j < len(matches) and code.count("\n", matches[i].end(), matches[j].start()) <= 10:
            j += 1
        i = j
    # Slice
    out = []
    boundaries.append(len(code))
    for k in range(len(boundaries) - 1):
        chunk = code[boundaries[k]:boundaries[k + 1]].strip()
        if chunk:
            out.append(chunk)
    # Anything before the first banner
    head = code[:boundaries[0]].strip()
    if head:
        out.insert(0, head)
    return out

ipy_cells = []
for kind, content in tokens:
    if kind == "markdown":
        if content.strip():
            ipy_cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": content.strip().splitlines(keepends=True),
            })
    else:
        for chunk in split_code_into_cells(content):
            ipy_cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": chunk.splitlines(keepends=True),
            })

# Make sure each "source" is a list of strings ending with \n (except last).
def normalize_source(src):
    if isinstance(src, str):
        src = src.splitlines(keepends=True)
    # ensure each line ends with \n except possibly the last
    fixed = []
    for i, ln in enumerate(src):
        if i < len(src) - 1 and not ln.endswith("\n"):
            ln = ln + "\n"
        fixed.append(ln)
    return fixed

for c in ipy_cells:
    c["source"] = normalize_source(c["source"])

notebook = {
    "cells": ipy_cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.10",
        },
        "colab": {
            "provenance": [],
            "toc_visible": True,
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

DST.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {DST} with {len(ipy_cells)} cells "
      f"({sum(1 for c in ipy_cells if c['cell_type'] == 'markdown')} markdown, "
      f"{sum(1 for c in ipy_cells if c['cell_type'] == 'code')} code)")
