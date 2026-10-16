"""Bounded, acquisition-free relational interpretation of exact text fragments.

This grammar is deliberately independent of the perception planner. A delimited
header supplies column roles; a labelled item supplies a block boundary. Neither
text proximity nor an isolated numeral establishes ownership.
"""
from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION = 'structured-evidence-v1'
MANIFEST_VERSION = 'STRUCTURED_EVIDENCE_001'
MAX_TEXT = 500_000
MAX_BLOCKS = 256


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')


class EvidenceSource(FrozenModel):
    tender_id: str
    document_id: str
    page_id: str
    page_number: int
    revision: int
    method: Literal['NATIVE', 'OCR', 'VISION']
    artifact_key: str
    generation_id: str
    text_sha256: str
    offset_space: Literal['NORMALIZED_TEXT', 'VISION_RAW_LINES']
    contract_version: str | None = None
    capability: Literal['TRANSCRIPTION'] = 'TRANSCRIPTION'
    original_sha256: str = ''
    acquisition_identity: tuple[tuple[str, str], ...] = ()
    source_scope: Literal['FULL_PAGE', 'REGION', 'UNKNOWN'] = 'UNKNOWN'
    region_id: str | None = None
    # No geometry is implied by text order. Coordinates belong to an actual
    # source generation and are intentionally absent in legacy text sources.


class Fragment(FrozenModel):
    id: str
    start: int
    end: int
    text: str
    role: str
    order: int


class Relation(FrozenModel):
    kind: Literal['HEADER_OF', 'DESCRIBES_ITEM', 'VALUE_FOR', 'UNIT_FOR', 'ATTRIBUTE_OF', 'CONTINUES']
    anchor: str
    target: str
    support: tuple[str, ...] = ()
    rule: str


class FieldBinding(FrozenModel):
    name: str
    value: str
    refs: tuple[str, ...]


class StructuredEvidenceBlock(FrozenModel):
    policy_version: str = POLICY_VERSION
    source: EvidenceSource
    occurrence: int
    item_raw: str
    domain: Literal['SUPPLY', 'SERVICE', 'DELIVERABLE', 'OTHER']
    fragments: tuple[Fragment, ...]
    relations: tuple[Relation, ...]
    fields: tuple[FieldBinding, ...]
    state: Literal['SUPPORTED', 'AMBIGUOUS'] = 'SUPPORTED'
    review_required: Literal[True] = True
    reasons: tuple[str, ...] = ()

    def field(self, name: str) -> FieldBinding | None:
        return next((f for f in self.fields if f.name == name), None)

    def fragment(self, ref: str) -> Fragment:
        return next(f for f in self.fragments if f.id == ref)


class StructuredEvidenceManifest(FrozenModel):
    version: Literal['STRUCTURED_EVIDENCE_001'] = MANIFEST_VERSION
    blocks: tuple[StructuredEvidenceBlock, ...] = Field(min_length=1, max_length=64)


_ALIASES = {'partida': 'item', 'item': 'item', 'ítem': 'item',
            'descripción': 'description', 'descripcion': 'description',
            'cantidad': 'quantity', 'quantity': 'quantity', 'unidad': 'unit', 'unit': 'unit',
            'marca': 'brand', 'brand': 'brand', 'modelo': 'model', 'model': 'model'}
_ITEM = re.compile(r'(?i)^(?:PARTIDA|ITEM|ÍTEM)\s*:?[ \t]*(\d+(?:\.\d+)*)\s*:?[ \t]*')
_ACTION = re.compile(r'(?i)^(suministro\b|suministrar\b|servicio de\b|prestaci[oó]n de\b|entrega de\b|entregar\b)')
_LABEL = re.compile(r'(?i)^(marca|brand|modelo|model|cantidad|quantity|unidad|unit)\s*:\s*(.+)$')


def _domain(description: str) -> str | None:
    m = _ACTION.match(description)
    if not m:
        return None
    verb = m.group().lower()
    return 'SUPPLY' if verb.startswith('suministr') else 'DELIVERABLE' if verb.startswith('entreg') else 'SERVICE'


def _cells(text: str, start: int, end: int, delimiter: str):
    result = []
    cursor = start
    for cell in text[start:end].split(delimiter):
        left = cursor + len(cell) - len(cell.lstrip())
        right = cursor + len(cell.rstrip())
        result.append((left, right, text[left:right]))
        cursor += len(cell) + 1
    return result


def reconstruct(source: EvidenceSource, text: str) -> tuple[StructuredEvidenceBlock, ...]:
    """Interpret labelled blocks and explicit delimited tables; never acquire data.

    A table must have unique item/description/quantity/unit columns. Procurement
    action plus exact numeric quantity and recognized unit gives positive row
    identity. Labelled multiline continuations require indentation; labelled
    subordinate fields require their own explicit roles. Blank lines terminate
    blocks/tables. Cross-page proximity is never a continuation proof.
    """
    if len(text) > MAX_TEXT:
        raise ValueError('STRUCTURED_TEXT_LIMIT')
    from app.scope_quantity_adapters import _unit_to_measure_kind
    lines = []
    pos = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        lines.append((pos, pos + len(line), line))
        pos += len(raw)
    blocks = []
    header = None
    index = 0
    while index < len(lines):
        start, end, raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            header = None
            index += 1
            continue
        delimiter = '|' if '|' in raw else '\t' if '\t' in raw else None
        cells = _cells(text, start, end, delimiter) if delimiter else []
        roles = [_ALIASES.get(c[2].lower()) for c in cells]
        if cells and all(roles) and len(set(roles)) == len(roles) and {'item','description','quantity','unit'} <= set(roles):
            header = (delimiter, roles, cells)
            index += 1
            continue
        specs = []
        relation_rule = 'labelled-item-v1'
        if header and delimiter == header[0] and len(cells) == len(header[1]):
            values = dict(zip(header[1], cells))
            item = values['item'][2]
            desc = values['description'][2]
            quantity, unit = values['quantity'][2], values['unit'][2]
            if (not re.fullmatch(r'\d+(?:\.\d+)*', item) or not desc
                    or not re.fullmatch(r'\d+(?:\.\d+)?', quantity) or not _unit_to_measure_kind(unit)):
                header = None
                index += 1
                continue
            specs = [(role, *cell) for role, cell in values.items()]
            specs += [('header_' + role, *cell) for role, cell in zip(header[1], header[2])]
            relation_rule = 'delimited-column-v1'
            index += 1
        else:
            header = None
            m = _ITEM.match(stripped)
            if not m:
                index += 1
                continue
            left = start + len(raw) - len(raw.lstrip())
            specs = [('item', left, left + m.end(), text[left:left + m.end()])]
            item = m.group(1)
            body_start = left + m.end()
            body = text[body_start:end].strip()
            # An immediate action may be on the following line, with a labelled
            # item boundary supplying the relationship (not the page number).
            if not body and index + 1 < len(lines):
                index += 1
                bs, be, br = lines[index]
                body_start = bs + len(br) - len(br.lstrip())
                end = be
                body = text[body_start:end]
            if not _domain(body):
                index += 1
                continue
            # Split explicitly labelled fields; each value remains a literal ref.
            parts = _cells(text, body_start, end, '|')
            desc = parts[0][2]
            specs.append(('description', *parts[0]))
            for a,b,value in parts[1:]:
                label = _LABEL.match(value)
                if label:
                    vstart = a + label.start(2)
                    specs.append((_ALIASES[label.group(1).lower()], vstart,b,text[vstart:b]))
            index += 1
            while index < len(lines):
                cs,ce,cr = lines[index]
                value = cr.strip()
                label = _LABEL.match(value)
                if label:
                    a = cs + len(cr) - len(cr.lstrip()) + label.start(2)
                    specs.append((_ALIASES[label.group(1).lower()],a,ce,text[a:ce]))
                elif cr.startswith((' ', '\t')) and value and not _ITEM.match(value):
                    a = cs + len(cr) - len(cr.lstrip())
                    specs.append(('description',a,ce,text[a:ce]))
                else:
                    break
                index += 1
        if any('?' in value or '¿' in value or re.search(r'\.{3,}\s*\d+\s*$',value) for _,_,_,value in specs):
            continue
        fragments = tuple(Fragment(id=f'f{i}',start=a,end=b,text=v,role=role,order=i)
                          for i,(role,a,b,v) in enumerate(sorted(specs,key=lambda s:(s[1],s[2],s[0]))) if v)
        if len(fragments) > 128:
            raise ValueError('STRUCTURED_FRAGMENT_LIMIT')
        by_role = {}
        for f in fragments:
            by_role.setdefault(f.role,[]).append(f)
        anchor = by_role['item'][0].id
        fields = []
        relations = [Relation(kind='HEADER_OF',anchor=h.id,target=anchor,rule=relation_rule)
                     for h in by_role.get('header_item',[])]
        descriptions = by_role.get('description',[])
        relations += [Relation(kind='CONTINUES',anchor=previous.id,target=current.id,
                               support=(anchor,),rule='indented-description-v1')
                      for previous,current in zip(descriptions,descriptions[1:])]
        ambiguous = False
        for role, entries in by_role.items():
            if role.startswith('header_') or role == 'item':
                continue
            if role != 'description' and len(entries) != 1:
                ambiguous = True
            fields.append(FieldBinding(name=role,value=' '.join(f.text for f in entries),refs=tuple(f.id for f in entries)))
            for f in entries:
                head = tuple(h.id for h in by_role.get('header_' + role, []))
                kind = {'quantity':'VALUE_FOR','unit':'UNIT_FOR','brand':'ATTRIBUTE_OF','model':'ATTRIBUTE_OF'}.get(role,'DESCRIBES_ITEM')
                relations.append(Relation(kind=kind,anchor=anchor,target=f.id,support=head,rule=relation_rule))
                relations += [Relation(kind='HEADER_OF',anchor=h,target=f.id,rule=relation_rule) for h in head]
        blocks.append(StructuredEvidenceBlock(source=source,occurrence=len(blocks),item_raw=item,
            domain=_domain(desc) or 'OTHER',fragments=fragments,relations=tuple(relations),fields=tuple(fields),
            state='AMBIGUOUS' if ambiguous else 'SUPPORTED',reasons=('DUPLICATE_FIELD',) if ambiguous else ()))
        if len(blocks) > MAX_BLOCKS:
            raise ValueError('STRUCTURED_BLOCK_LIMIT')
    return tuple(blocks)
