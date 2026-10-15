"""Bounded Native row grammar and exact generation/character-span provenance.

Only labelled procurement item blocks with an explicit execution action are
eligible. Fields are explicit colon bindings separated by pipes/semicolons/newlines.
This is not a natural-language or visual table reconstruction engine.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DocumentPage, NormalizedContent, TenderDocument

NATIVE_SCOPE_VERSION = "native-scope-v1"
_ITEM = re.compile(r"(?im)^[ \t]*(?:PARTIDA|ITEM|I[TÍ]EM|CONCEPTO|NO\.?)[ \t]*:?[ \t]*([A-Z]?[- ]?\d+(?:\.\d+)*)\b")
_ACTION = re.compile(r"(?i)\b(suministro|suministrar|servicio de|prestaci[oó]n de|entrega de|entregar)\b")
_FIELD = re.compile(r"(?i)(?:^|[|;\n])[ \t]*(marca|brand|modelo|model|cantidad|quantity|unidad|unit)[ \t]*:[ \t]*([^|;\n]+)")


@dataclass(frozen=True)
class NativeScopeRow:
    start: int
    end: int
    text: str
    item_raw: str
    domain: str


def procurement_rows(text: str) -> tuple[NativeScopeRow, ...]:
    matches = list(_ITEM.finditer(text))
    rows = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end]
        start = match.start() + len(block) - len(block.lstrip())
        raw = block.strip()
        # Bound a block to its explicit item; questions/navigation never become scope.
        if not raw or '?' in raw or '¿' in raw or re.search(r'\.{3,}\s*\d+\s*$', raw):
            continue
        body_start = match.end() - start
        body = raw[body_start:].lstrip(' :|\t\r\n')
        action = _ACTION.match(body)
        if action is None:
            continue
        verb = action.group().lower()
        domain = ('SUPPLY' if verb.startswith('suministr') else
                  'DELIVERABLE' if verb.startswith('entreg') else 'SERVICE')
        rows.append(NativeScopeRow(start, start + len(raw), raw, match.group(1), domain))
    return tuple(rows)


def explicit_fields(text: str) -> dict[str, str]:
    aliases = {'marca': 'brand', 'brand': 'brand', 'modelo': 'model', 'model': 'model',
               'cantidad': 'quantity', 'quantity': 'quantity', 'unidad': 'unit', 'unit': 'unit'}
    fields: dict[str, str] = {}
    for match in _FIELD.finditer(text):
        name, value = aliases[match.group(1).lower()], match.group(2).strip()
        if name in fields:
            raise ValueError('AMBIGUOUS_NATIVE_FIELD')
        fields[name] = value
    return fields


def native_locator(db: Session, artifact, start: int, end: int) -> str:
    payload = artifact.payload or {}
    normalized = db.get(NormalizedContent, payload.get('normalized_content_id'))
    if normalized is None:
        raise ValueError('NATIVE_GENERATION_MISSING')
    _validate_generation(db, normalized, artifact.source_document_id, artifact.document_page_id)
    if normalized.normalized_text != payload.get('text'):
        raise ValueError('NATIVE_GENERATION_TEXT_MISMATCH')
    page = db.get(DocumentPage, artifact.document_page_id)
    document = db.get(TenderDocument, artifact.source_document_id)
    return (f'page:{page.page_number}|native_scope:1|normalized:{normalized.id}'
            f'|sha256:{normalized.content_sha256}|span:{start}:{end}|revision:{document.revision_number}')


def _validate_generation(db, normalized, document_id, page_id):
    page = db.get(DocumentPage, page_id)
    if (page is None or page.document_id != document_id or normalized.document_page_id != page_id
            or normalized.source_type not in {'NATIVE_PDF', 'NATIVE_TEXT'}):
        raise ValueError('NATIVE_GENERATION_IDENTITY_MISMATCH')
    if hashlib.sha256(normalized.normalized_text.encode()).hexdigest() != normalized.content_sha256:
        raise ValueError('NATIVE_GENERATION_HASH_MISMATCH')


def resolve_native_scope_payload(db: Session, scope_detail) -> dict:
    """Do not fall back to current page.text for versioned Native scope."""
    tokens = dict(token.split(':', 1) for token in scope_detail.source_locator.split('|') if ':' in token)
    if tokens.get('native_scope') != '1':
        # Legacy Native evidence can be read by legacy/custom adapters only.
        return {'text': '', 'source_scope': 'LEGACY_NATIVE_UNVERSIONED'}
    normalized = db.get(NormalizedContent, tokens.get('normalized'))
    if normalized is None:
        raise ValueError('NATIVE_GENERATION_MISSING')
    _validate_generation(db, normalized, scope_detail.source_document_id, scope_detail.document_page_id)
    document = db.get(TenderDocument, scope_detail.source_document_id)
    if document.tender_id != scope_detail.tender_id or str(document.revision_number) != tokens.get('revision'):
        raise ValueError('NATIVE_DOCUMENT_VERSION_MISMATCH')
    page = db.get(DocumentPage, scope_detail.document_page_id)
    if tokens.get('page') != str(page.page_number):
        raise ValueError('NATIVE_PAGE_NUMBER_MISMATCH')
    if tokens.get('sha256') != normalized.content_sha256:
        raise ValueError('NATIVE_GENERATION_HASH_MISMATCH')
    try:
        start, end = map(int, tokens['span'].split(':'))
    except (KeyError, ValueError) as exc:
        raise ValueError('NATIVE_SPAN_INVALID') from exc
    text = normalized.normalized_text
    if not 0 <= start < end <= len(text) or text[start:end] != scope_detail.source_excerpt:
        raise ValueError('NATIVE_SPAN_GROUNDING_MISMATCH')
    return {'text': text, 'scope_excerpt': text[start:end], 'source_scope': 'NATIVE_SCOPE_ROW',
            'normalized_content_id': normalized.id}
