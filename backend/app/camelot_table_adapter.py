"""Camelot proposes physical cells; only verified Native words supply evidence."""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from app.camelot_table_contract import (CamelotCell, CamelotTableProposal,
    CamelotWordMatch, CamelotCellMatch, CamelotNativeProof, CONFIG_SHA256,
    DETECTOR_VERSION, POLICY_VERSION, bottom_to_top, digest, check_digest)
from app.native_table_relationships import (_may_have_headers, _words_with_offsets,
    _role, block_from_cell_spans)
from app.structured_evidence import MAX_TEXT, MAX_BLOCKS

MAX_ORIGINAL_BYTES = 128 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 35


def dependency_identity():
    packages = ('camelot-py', 'playa-pdf', 'pypdfium2', 'opencv-python-headless',
                'numpy', 'pandas', 'PyMuPDF')
    return tuple((p, importlib.metadata.version(p)) for p in packages)


@lru_cache(maxsize=16)
def _physical_json(path, original_sha256, page_number, config_sha256, dependencies):
    # Only immutable physical proposals are memoized; original hash/Native
    # generation are checked before every lookup. New processes replay afresh.
    with tempfile.TemporaryDirectory(prefix='licitia-camelot-') as directory:
        output = Path(directory) / 'proposal.json'
        with (Path(directory) / 'stderr').open('w+') as errors:
            result = subprocess.run([sys.executable, '-m', 'app.camelot_table_worker',
                path, str(page_number), str(output)], cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.DEVNULL, stderr=errors, timeout=WORKER_TIMEOUT_SECONDS,
                check=False)
        if result.returncode or not output.is_file():
            raise ValueError('CAMELOT_WORKER_FAILED')
        if output.stat().st_size > MAX_OUTPUT_BYTES:
            raise ValueError('CAMELOT_PROPOSAL_SIZE_LIMIT')
        return output.read_text()


class CamelotTableRelationshipAdapter:
    def propose(self, path, source, page_bbox):
        deps = dependency_identity()
        if dict(deps)['camelot-py'] != DETECTOR_VERSION:
            raise ValueError('CAMELOT_VERSION_MISMATCH')
        raw = json.loads(_physical_json(str(path), source.original_sha256,
            source.page_number, CONFIG_SHA256, deps))
        proposals = []
        for i, t in enumerate(sorted(raw, key=lambda t: tuple(t['bbox']))):
            payload = dict(detector='camelot-py', detector_version=DETECTOR_VERSION,
                parser='lattice', engine='combined', config_sha256=CONFIG_SHA256,
                source_identity_sha256=digest(source.model_dump(mode='json')),
                table_index=i, page_bbox=page_bbox, bbox=bottom_to_top(t['bbox'],page_bbox[3]),
                row_count=t['row_count'], column_count=t['column_count'],
                cells=tuple(CamelotCell(**(c | {'bbox':bottom_to_top(c['bbox'],page_bbox[3])}))
                            for c in t['cells']))
            proposal = CamelotTableProposal(**payload, proposal_sha256='')
            proposals.append(proposal.model_copy(update={'proposal_sha256':digest(
                proposal.model_dump(mode='json',exclude={'proposal_sha256'}))}))
        return tuple(proposals)


def _valid_rect(b, outer):
    return outer[0] <= b[0] < b[2] <= outer[2] and outer[1] <= b[1] < b[3] <= outer[3]


def _normalize(value):
    return ' '.join(value.split())


def match_cells(proposal, words, text):
    """Unique physical ownership + exact Native literal agreement, no epsilon."""
    check_digest(proposal, 'proposal_sha256')
    if (len(proposal.cells) != proposal.row_count * proposal.column_count
            or len({(c.row,c.column) for c in proposal.cells}) != len(proposal.cells)
            or not _valid_rect(proposal.bbox, proposal.page_bbox)):
        return None
    if any(c.row >= proposal.row_count or c.column >= proposal.column_count
           or not _valid_rect(c.bbox, proposal.bbox) or not all(c.borders)
           for c in proposal.cells):
        return None  # Merged/broken topology not a complete rectangular proof.
    grid = {(c.row,c.column):c for c in proposal.cells}
    # A rectangular proposal must supply the same disjoint column bands in
    # every row and the same row bands in every column; no overlapping cells.
    columns = [(grid[(0,c)].bbox[0],grid[(0,c)].bbox[2]) for c in range(proposal.column_count)]
    rows = [(grid[(r,0)].bbox[1],grid[(r,0)].bbox[3]) for r in range(proposal.row_count)]
    if (any(a[1] != b[0] for a,b in zip(columns,columns[1:]))
            or any(a[1] != b[0] for a,b in zip(rows,rows[1:]))
            or any((c.bbox[0],c.bbox[2]) != columns[c.column]
                   or (c.bbox[1],c.bbox[3]) != rows[c.row] for c in proposal.cells)):
        return None
    assignments = defaultdict(list)
    for word in words:
        a,b,box,line = word
        cx,cy = (box[0]+box[2])/2,(box[1]+box[3])/2
        cells = [c for c in proposal.cells if c.bbox[0]<=cx<c.bbox[2] and c.bbox[1]<=cy<c.bbox[3]]
        if len(cells)>1:
            return None
        if cells:
            assignments[(cells[0].row,cells[0].column)].append(word)
    matches = {}
    for cell in proposal.cells:
        members = assignments[(cell.row,cell.column)]
        groups = defaultdict(list)
        for word in members:
            groups[word[3]].append(word)
        spans = []
        for group in groups.values():
            group.sort(key=lambda w:w[0])
            if any(text[a[1]:b[0]].strip() for a,b in zip(group,group[1:])):
                return None
            spans.append((group[0][0],group[-1][1],min(w[2][1] for w in group),min(w[2][0] for w in group)))
        spans.sort(key=lambda x:(x[2],x[3],x[0]))
        spans = tuple((a,b) for a,b,_,_ in spans)
        literal_value = ' '.join(text[a:b] for a,b in spans)
        if _normalize(literal_value) != _normalize(cell.raw_text):
            return None  # Detector strings never replace missing Native evidence.
        matches[(cell.row,cell.column)] = (spans, tuple(members))
    return matches


def _prove_row(source, text, proposal, matches, roles, row, occurrence, deps):
    bindings = {}
    for r in (0,row):
        for col,role in enumerate(roles):
            spans,_ = matches[(r,col)]
            if not spans:
                return None
            bindings[('header_' if r==0 else '')+role] = spans
    block = block_from_cell_spans(source,text,bindings,roles,occurrence,
                                 relation_rule=POLICY_VERSION)
    if block is None:
        return None
    cell_proofs = []
    for r in (0,row):
        for col,role in enumerate(roles):
            name = ('header_' if r==0 else '')+role
            spans,members = matches[(r,col)]
            refs = tuple(next(f.id for f in block.fragments if (f.start,f.end,f.role)==(a,b,name)) for a,b in spans)
            cell = next(c for c in proposal.cells if (c.row,c.column)==(r,col))
            cell_proofs.append(CamelotCellMatch(row=r,column=col,role=role,header=r==0,
                bbox=cell.bbox,refs=refs,words=tuple(CamelotWordMatch(
                    fragment_ref=next(f.id for f in block.fragments if f.role==name and f.start<=a<b<=f.end),
                    start=a,end=b,bbox=box) for a,b,box,_ in members)))
    proof = CamelotNativeProof(engine_version=dict(deps)['PyMuPDF'],proposal=proposal,dependencies=deps,row_index=row,
                               cells=tuple(cell_proofs),proof_sha256='')
    proof = proof.model_copy(update={'proof_sha256':digest(proof.model_dump(mode='json',exclude={'proof_sha256'}))})
    return block.model_copy(update={'native_table_proof':proof})


def reconstruct_camelot_tables(db, artifact, source, text, *, occurrence_start=0):
    if source.method!='NATIVE' or source.source_scope!='FULL_PAGE' or not _may_have_headers(text):
        return ()
    if len(text)>MAX_TEXT:
        raise ValueError('STRUCTURED_TEXT_LIMIT')
    from app.models import TenderDocument
    from app.main import _resolve_document_file_path,_hash_file
    from app.content_normalization import _normalize_text
    import pymupdf
    document = db.get(TenderDocument,source.document_id)
    if document is None or document.mime_type!='application/pdf':
        return ()
    path = _resolve_document_file_path(document.stored_relative_path)
    if path.stat().st_size>MAX_ORIGINAL_BYTES:
        raise ValueError('CAMELOT_ORIGINAL_SIZE_LIMIT')
    with path.open('rb') as f:
        actual,size = _hash_file(f)
    if actual!=source.original_sha256 or size!=document.file_size_bytes:
        raise ValueError('NATIVE_TABLE_ORIGINAL_INTEGRITY_MISMATCH')
    with pymupdf.open(path) as pdf:
        if not 1<=source.page_number<=len(pdf):
            raise ValueError('CAMELOT_PAGE_MISMATCH')
        page = pdf[source.page_number-1]
        # No guessed offsets for rotated/cropped pages in this contract.
        if page.rotation or page.mediabox!=page.cropbox or tuple(page.rect)[:2]!=(0,0):
            return ()
        if _normalize_text(page.get_text('text'))!=text:
            raise ValueError('NATIVE_TABLE_TEXT_GENERATION_MISMATCH')
        words = _words_with_offsets(page,text)
        proposals = CamelotTableRelationshipAdapter().propose(path,source,tuple(page.rect))
    blocks = []
    deps = dependency_identity()
    for proposal in proposals:
        if not 4<=proposal.column_count<=6:
            continue
        matches = match_cells(proposal,words,text)
        if matches is None:
            continue
        roles = [_role(' '.join(text[a:b] for a,b in matches[(0,col)][0])) for col in range(proposal.column_count)]
        if None in roles or len(set(roles))!=len(roles) or not {'item','description','quantity','unit'}<=set(roles):
            continue
        for row in range(1,proposal.row_count):
            block = _prove_row(source,text,proposal,matches,roles,row,occurrence_start+len(blocks),deps)
            if block:
                blocks.append(block)
                if len(blocks)+occurrence_start>MAX_BLOCKS:
                    raise ValueError('STRUCTURED_BLOCK_LIMIT')
    return tuple(blocks)
