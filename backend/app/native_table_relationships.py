"""Source-bound ruled Native tables; no OCR, provider, or inferred text cells.

Geometry is a lazy, versioned companion to canonical Native text. Original PDF
hash, page and normalized extraction must agree before geometry can support IR.
Unruled/merged/overlapping or unaligned cells are deliberately unsupported.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re

from app.structured_evidence import (
    EvidenceSource, FieldBinding, Fragment, NativeCellProof, NativeTableProof,
    Relation, StructuredEvidenceBlock, MAX_BLOCKS, MAX_TEXT, _domain,
)

POLICY_VERSION = 'native-table-relationships-v1'
MAX_WORDS = 20_000
MAX_CELLS = 4096
MAX_TABLES = 32
_HEADERS = {
    'item': 'item', 'partida': 'item', 'ítem': 'item',
    'description': 'description', 'descripción': 'description', 'descripcion': 'description',
    'quantity': 'quantity', 'cantidad': 'quantity',
    'unit': 'unit', 'unidad': 'unit', 'unidad de medida': 'unit', 'unit of measure': 'unit',
    'brand': 'brand', 'marca': 'brand', 'fabricante/marca': 'brand',
    'model': 'model', 'modelo': 'model',
}


def _role(value: str) -> str | None:
    return _HEADERS.get(' '.join(value.casefold().split()))


def _may_have_headers(text: str) -> bool:
    # A cheap shape gate only, never proof. Hand-serialized v1 fixtures do not
    # need an original-layout lookup. No planner consumes this bridge.
    roles = {_role(line.strip()) for line in text.splitlines()}
    return {'item', 'description', 'quantity'} <= roles


def _words_with_offsets(page, text):
    from app.content_normalization import _normalize_text
    words = page.get_text('words', sort=False)
    if len(words) > MAX_WORDS:
        raise ValueError('NATIVE_TABLE_WORD_LIMIT')
    result = []
    cursor = 0
    for word in words:
        literal = _normalize_text(word[4])
        if not literal:
            continue
        start = text.find(literal, cursor)
        if start < 0 or text[cursor:start].strip():
            raise ValueError('NATIVE_TABLE_WORD_ALIGNMENT_REQUIRED')
        if not all(math.isfinite(v) for v in word[:4]):
            raise ValueError('NATIVE_TABLE_INVALID_GEOMETRY')
        result.append((start, start + len(literal), tuple(word[:4]), (word[5], word[6])))
        cursor = start + len(literal)
    if text[cursor:].strip():
        raise ValueError('NATIVE_TABLE_WORD_ALIGNMENT_REQUIRED')
    return result


def _inside(inner, outer):
    return (outer[0] <= inner[0] < inner[2] <= outer[2]
            and outer[1] <= inner[1] < inner[3] <= outer[3])


def _overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _cell_spans(box, words, text):
    grouped = defaultdict(list)
    for start, end, bbox, line in words:
        if _overlap(bbox, box):
            if not _inside(bbox, box):
                return None  # A word crossing a cell border cannot be assigned.
            grouped[line].append((start, end, bbox))
    spans = []
    for line in grouped.values():
        line.sort(key=lambda w: w[0])
        if any(text[a[1]:b[0]].strip() for a, b in zip(line, line[1:])):
            return None  # Interleaved extraction order is not one literal span.
        spans.append((line[0][0], line[-1][1], min(w[2][1] for w in line), min(w[2][0] for w in line)))
    # Reading order is local to this proven cell, not a page-wide proximity rule.
    spans.sort(key=lambda s: (s[2], s[3], s[0]))
    return tuple((start, end) for start, end, _, _ in spans)


def _build_block(source, text, table, header, row, roles, words, row_index, occurrence, engine, page_bbox):
    from app.scope_quantity_adapters import _unit_to_measure_kind
    role_spans = {}
    boxes = []
    for is_header, cells in ((True, header), (False, row)):
        for role, box in zip(roles, cells, strict=True):
            spans = _cell_spans(box, words, text)
            if not spans:
                return None
            name = 'header_' + role if is_header else role
            role_spans[name] = spans
            boxes.append((role, is_header, tuple(box), name))
    block = block_from_cell_spans(source, text, role_spans, roles, occurrence)
    if block is None:
        return None
    refs = {name: tuple(next(f.id for f in block.fragments if (f.start, f.end, f.role) == (a,b,name))
                        for a,b in spans) for name,spans in role_spans.items()}
    proof = NativeTableProof(engine_version=engine, page_bbox=page_bbox, table_bbox=tuple(table.bbox),
        row_index=row_index, cells=tuple(NativeCellProof(role=role, header=is_header, bbox=box,
            refs=refs[name]) for role, is_header, box, name in boxes))
    return block.model_copy(update={'native_table_proof': proof})


def block_from_cell_spans(source, text, role_spans, roles, occurrence, *, relation_rule=POLICY_VERSION):
    """Existing positive-row grammar; literals already proven by the physical adapter."""
    from app.scope_quantity_adapters import _unit_to_measure_kind
    values = {name: ' '.join(text[a:b] for a, b in spans) for name, spans in role_spans.items()}
    if (not re.fullmatch(r'0*[1-9]\d*', values['item'])
            or not re.fullmatch(r'\d+(?:\.\d+)?', values['quantity'])
            or not _unit_to_measure_kind(values['unit'])
            or any('?' in v or '¿' in v or re.search(r'\.{3,}\s*\d+\s*$', v) for v in values.values())):
        return None
    entries = sorted((a, b, role) for role, spans in role_spans.items() for a, b in spans)
    if len(entries) > 128:
        raise ValueError('STRUCTURED_FRAGMENT_LIMIT')
    fragments = tuple(Fragment(id=f'f{i}', start=a, end=b, text=text[a:b], role=role, order=i)
                      for i, (a, b, role) in enumerate(entries))
    refs = {role: tuple(next(f.id for f in fragments if (f.start, f.end, f.role) == (a, b, role))
                        for a, b in spans) for role, spans in role_spans.items()}
    anchor = refs['item'][0]
    relations = []
    for role in roles:
        for ref in refs[role]:
            relations.extend(Relation(kind='HEADER_OF', anchor=h, target=ref, rule=relation_rule)
                             for h in refs['header_' + role])
            if role != 'item':
                kind = {'quantity': 'VALUE_FOR', 'unit': 'UNIT_FOR',
                        'brand': 'ATTRIBUTE_OF', 'model': 'ATTRIBUTE_OF'}.get(role, 'DESCRIBES_ITEM')
                relations.append(Relation(kind=kind, anchor=anchor, target=ref,
                                          support=refs['header_' + role], rule=relation_rule))
    relations.extend(Relation(kind='CONTINUES', anchor=a, target=b, support=(anchor,), rule=relation_rule)
                     for a, b in zip(refs['description'], refs['description'][1:]))
    return StructuredEvidenceBlock(source=source, occurrence=occurrence, item_raw=values['item'],
        domain=_domain(values['description']) or 'OTHER', fragments=fragments, relations=tuple(relations),
        fields=tuple(FieldBinding(name=r, value=values[r], refs=refs[r]) for r in roles if r != 'item'))


def reconstruct_native_tables(db, artifact, source: EvidenceSource, text: str, *, occurrence_start=0):
    if source.method != 'NATIVE' or not _may_have_headers(text):
        return ()
    if len(text) > MAX_TEXT:
        raise ValueError('STRUCTURED_TEXT_LIMIT')
    import pymupdf
    from app.models import TenderDocument
    from app.main import _resolve_document_file_path, _hash_file
    from app.content_normalization import _normalize_text
    document = db.get(TenderDocument, source.document_id)
    path = _resolve_document_file_path(document.stored_relative_path)
    with path.open('rb') as original:
        digest, size = _hash_file(original)
    if digest != source.original_sha256 or size != document.file_size_bytes:
        raise ValueError('NATIVE_TABLE_ORIGINAL_INTEGRITY_MISMATCH')
    blocks = []
    with pymupdf.open(path) as pdf:
        if not 1 <= source.page_number <= len(pdf):
            raise ValueError('NATIVE_TABLE_PAGE_MISMATCH')
        page = pdf[source.page_number - 1]
        if _normalize_text(page.get_text('text')) != text:
            raise ValueError('NATIVE_TABLE_TEXT_GENERATION_MISMATCH')
        tables = page.find_tables(strategy='lines_strict').tables
        if len(tables) > MAX_TABLES or sum(len(t.cells) for t in tables) > MAX_CELLS:
            raise ValueError('NATIVE_TABLE_LAYOUT_LIMIT')
        if not tables:
            return ()
        words = _words_with_offsets(page, text)
        for table in sorted(tables, key=lambda t: tuple(t.bbox)):
            rows = [r.cells for r in table.rows]
            if not rows or not 4 <= table.col_count <= 6:
                continue
            # Merged cells and duplicate cell membership are not rectangular proof.
            if any(len(r) != table.col_count or any(c is None for c in r)
                   or len(set(map(tuple, r))) != len(r) for r in rows):
                continue
            header = rows[0]
            header_spans = [_cell_spans(c, words, text) for c in header]
            if any(not s for s in header_spans):
                continue
            roles = [_role(' '.join(text[a:b] for a, b in spans)) for spans in header_spans]
            if (None in roles or len(set(roles)) != len(roles)
                    or not {'item', 'description', 'quantity', 'unit'} <= set(roles)):
                continue
            for row_index, row in enumerate(rows[1:], 1):
                block = _build_block(source, text, table, header, row, roles, words, row_index,
                    occurrence_start + len(blocks), pymupdf.VersionBind, tuple(page.rect))
                if block:
                    blocks.append(block)
                    if len(blocks) + occurrence_start > MAX_BLOCKS:
                        raise ValueError('STRUCTURED_BLOCK_LIMIT')
    return tuple(blocks)
