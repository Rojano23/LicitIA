"""Bounded local physical parser subprocess. No app, DB, providers or network."""
from __future__ import annotations
import json
from pathlib import Path
import sys


def main():
    import resource
    # Independent parser CPU budget; does not alter OCR/Vision budgets.
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    import camelot
    from app.camelot_table_contract import CONFIG, DETECTOR_VERSION
    if camelot.__version__ != DETECTOR_VERSION:
        raise ValueError('CAMELOT_VERSION_MISMATCH')
    path, page, output = sys.argv[1:]
    tables = camelot.read_pdf(path, pages=page, **CONFIG)
    if len(tables) > 32 or sum(t.shape[0] * t.shape[1] for t in tables) > 4096:
        raise ValueError('CAMELOT_LAYOUT_LIMIT')
    payload = [dict(bbox=list(t._bbox), row_count=t.shape[0], column_count=t.shape[1],
        cells=[dict(row=r, column=c, bbox=[cell.x1,cell.y1,cell.x2,cell.y2],
                    raw_text=cell.text, borders=[cell.left,cell.right,cell.top,cell.bottom])
               for r,row in enumerate(t.cells) for c,cell in enumerate(row)]) for t in tables]
    data = json.dumps(payload, allow_nan=False)
    if len(data.encode()) > 2 * 1024 * 1024:
        raise ValueError('CAMELOT_PROPOSAL_SIZE_LIMIT')
    Path(output).write_text(data)


if __name__ == '__main__':
    main()
