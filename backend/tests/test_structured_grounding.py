"""MG01–MG15 manifest integrity, synthetic local provenance only."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import pytest
from pydantic import ValidationError
from app.structured_evidence import StructuredEvidenceManifest
from app.structured_evidence_storage import (canonical_bytes,write_manifest,read_manifest,
    manifest_path,digest_from_locator,manifest_root)
from test_structured_interpretation import blocks, TABLE


@pytest.fixture
def proof(tmp_path,monkeypatch):
    import app.main
    monkeypatch.setattr(app.main,'get_licitia_data_root',lambda:tmp_path)
    return StructuredEvidenceManifest(blocks=blocks())


def test_MG01_versioned(proof):
    assert proof.version == 'STRUCTURED_EVIDENCE_001'
    with pytest.raises(ValidationError):
        StructuredEvidenceManifest.model_validate({**proof.model_dump(),'version':'old'})


def test_MG02_deterministic(proof):
    assert canonical_bytes(proof) == canonical_bytes(StructuredEvidenceManifest.model_validate(proof.model_dump()))


def test_MG03_hash_verified(proof):
    digest = write_manifest(proof)
    assert digest == hashlib.sha256(canonical_bytes(proof)).hexdigest()
    assert read_manifest(digest) == proof


def test_MG04_atomic_concurrent(proof):
    with ThreadPoolExecutor(max_workers=4) as pool:
        hashes = list(pool.map(lambda _:write_manifest(proof),range(12)))
    assert len(set(hashes)) == 1 and read_manifest(hashes[0]) == proof
    assert not list(manifest_root().glob('.proof-*'))


def test_MG05_exact_reference(proof):
    digest = write_manifest(proof)
    assert digest_from_locator('page:1|se:1:' + digest + '|block:0') == digest
    for locator in ['se:1:../escape','se:1:abc','se:1:' + digest + '|se:1:' + digest]:
        with pytest.raises(ValueError): digest_from_locator(locator)


def test_MG06_missing(proof):
    with pytest.raises(ValueError,match='MISSING'):read_manifest('0'*64)


def test_MG07_corruption(proof):
    digest = write_manifest(proof)
    manifest_path(digest).write_bytes(b'{}')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):read_manifest(digest)


def test_MG08_root_escape(proof,tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.mkdir()
    (tmp_path/'provenance').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='ROOT_ESCAPE'):write_manifest(proof)


def test_MG09_portable_reference(proof):
    digest = write_manifest(proof)
    assert '/' not in digest and '/tmp' not in canonical_bytes(proof).decode()
    assert manifest_path(digest).parent == manifest_root()


def test_MG10_separate_exact_fragments(proof):
    b = proof.blocks[0]
    assert all(TABLE[f.start:f.end] == f.text for f in b.fragments)
    assert b.field('description').refs != b.field('quantity').refs


def test_MG11_no_fake_quote(proof):
    b = proof.blocks[0]
    assert b.field('quantity').value not in b.fragment(b.field('description').refs[0]).text
    assert not any(f.text == 'Suministro de actuadores 12 PZA' for f in b.fragments)


def test_MG12_generic_identity(proof):
    assert write_manifest(proof) == hashlib.sha256(canonical_bytes(proof)).hexdigest()
    assert 'filename' not in proof.model_dump_json()


def test_MG13_idempotent(proof):
    digest = write_manifest(proof); path = manifest_path(digest); before = path.stat().st_mtime_ns
    assert write_manifest(proof) == digest and path.stat().st_mtime_ns == before


def test_MG14_changed_evidence(proof):
    other = StructuredEvidenceManifest(blocks=blocks(TABLE.replace('12','19')))
    assert write_manifest(other) != write_manifest(proof)


def test_MG15_no_overwrite_history(proof):
    digest = write_manifest(proof); path = manifest_path(digest)
    path.write_bytes(b'historical-corruption')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):write_manifest(proof)
    assert path.read_bytes() == b'historical-corruption'
