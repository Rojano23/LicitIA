from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import fitz
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    Company,
    CompanyDocument,
    CompanyEvidence,
    CompanyEvidenceAnalysisStatus,
    CompanyEvidenceOrigin,
    CompanyEvidenceReview,
    CompanyEvidenceReviewStatus,
    CompanyEvidenceSubjectKind,
    CompanyEvidenceType,
)

COMPANY_EVIDENCE_EXTRACTOR_VERSION = "mvp-05.2"
MANUAL_EVIDENCE_EXTRACTOR_VERSION = "human-manual-entry"

TEXT_STATUS_EXTRACTED = "TEXT_EXTRACTED"
TEXT_STATUS_UNAVAILABLE = "TEXT_UNAVAILABLE"

FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_NOT_REVIEWED = "NOT_REVIEWED"

REVIEW_PENDING = CompanyEvidenceReviewStatus.PENDING.value
REVIEW_APPROVED = CompanyEvidenceReviewStatus.APPROVED.value
REVIEW_NEEDS_REVIEW = CompanyEvidenceReviewStatus.NEEDS_REVIEW.value
REVIEW_REJECTED = CompanyEvidenceReviewStatus.REJECTED.value

ACTION_APPROVE = "APPROVE"
ACTION_MARK_NEEDS_REVIEW = "MARK_NEEDS_REVIEW"
ACTION_REJECT = "REJECT"

_RFC_PATTERN = re.compile(r"\b([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b")
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})\b")
_SPACE_RE = re.compile(r"\s+")
_DATE_CAPTURE_PATTERN = r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})"


@dataclass(slots=True)
class SourceSegment:
    source_page: int | None
    source_locator: str
    text: str


@dataclass(slots=True)
class EvidenceCandidate:
    evidence_type: str
    subject_kind: str
    subject_name: str | None
    canonical_statement: str
    issuer: str | None
    reference_number: str | None
    issued_on: date | None
    valid_from: date | None
    valid_until: date | None
    period_start: date | None
    period_end: date | None
    analysis_status: str
    origin: str
    extractor_version: str
    source_page: int | None
    source_locator: str | None
    source_excerpt: str


def _normalize_space(value: str | None) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip())


def _fold_for_matching(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return _normalize_space(without_marks).lower()


def _canonical_case(value: str | None) -> str | None:
    normalized = _normalize_space(value)
    return normalized or None


def _canonical_subject(value: str | None) -> str | None:
    normalized = _canonical_case(value)
    if normalized is None:
        return None
    return normalized.rstrip(" .;,") or None


def _trim_preserve_lines(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [line.rstrip() for line in value.strip().splitlines()]
    trimmed = "\n".join(lines).strip()
    return trimmed or None


def _parse_date(raw_value: str | None) -> date | None:
    normalized = _normalize_space(raw_value)
    if not normalized:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def _extract_date_from_label(text: str, labels: tuple[str, ...]) -> date | None:
    for label in labels:
        match = re.search(rf"{label}\s*[:#-]?\s*{_DATE_CAPTURE_PATTERN}", text, flags=re.IGNORECASE)
        if match:
            return _parse_date(match.group(1))
    return None


def _extract_reference(text: str) -> str | None:
    patterns = (
        r"(?:folio|referencia|certificado no\.?|constancia no\.?|registro no\.?|n[úu]mero de certificado|numero de certificado)\s*[:#-]?\s*([A-Z0-9\-/]+)",
        r"(?:c[eé]dula profesional|licencia)\s*[:#-]?\s*([A-Z0-9\-/]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _canonical_case(match.group(1))
    return None


def _extract_subject(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"{label}\s*[:\-]\s*([^\n]+)", text, flags=re.IGNORECASE)
        if match:
            return _canonical_subject(match.group(1))
    return None


def _extract_issuer(text: str) -> str | None:
    for pattern in (
        r"(?:fue\s+emitid[oa]\s+por|emitid[oa]\s+por|emisor|issuer|autoridad)\s*(?::|-)?\s*([^\n\.]+)",
        r"(?:otorgad[oa] por)\s*([^\n\.]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _canonical_case(match.group(1))
    return None


def _extract_company_subject_from_phrase(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _canonical_subject(match.group(1))
    return None


def _looks_like_company_name(text: str) -> bool:
    folded = _fold_for_matching(text)
    return any(token in folded for token in ("s.a. de c.v", "sa de cv", "s de rl", "sociedad anonima"))


def _join_locators(segments: list[SourceSegment]) -> str:
    return ";".join(segment.source_locator for segment in segments)


def _join_excerpt(segments: list[SourceSegment]) -> str:
    return "\n\n".join(segment.text.strip() for segment in segments if segment.text.strip())


def _is_certification_enrichment_segment(text: str) -> bool:
    folded = _fold_for_matching(text)
    return any(
        phrase in folded
        for phrase in (
            "certificacion iso",
            "fue emitida por",
            "fue emitido por",
            "emitida por",
            "emitido por",
            "numero de certificado",
            "número de certificado",
            "fecha de emision",
            "valido hasta",
            "válido hasta",
            "vigente hasta",
            "validez hasta",
        )
    )


def _is_negated_certification(text: str) -> bool:
    folded = _fold_for_matching(text)
    return any(
        phrase in folded
        for phrase in (
            "no constituye una certificacion",
            "no constituye certificacion",
            "no es una certificacion",
            "sin certificacion",
        )
    )


def _certification_context_segments(segments: list[SourceSegment], index: int) -> list[SourceSegment]:
    current = segments[index]
    context_segments = [current]

    next_index = index + 1
    while next_index < len(segments) and len(context_segments) < 5:
        candidate = segments[next_index]
        if not _is_certification_enrichment_segment(candidate.text):
            break
        context_segments.append(candidate)
        next_index += 1

    if index > 0 and _looks_like_company_name(segments[index - 1].text):
        context_segments.insert(0, segments[index - 1])

    return context_segments


def _evidence_fingerprint(document: CompanyDocument, candidate: EvidenceCandidate) -> str:
    payload = {
        "company_document_id": document.id,
        "evidence_type": candidate.evidence_type,
        "subject_kind": candidate.subject_kind,
        "subject_name": _normalize_space(candidate.subject_name),
        "canonical_statement": _normalize_space(candidate.canonical_statement),
        "issuer": _normalize_space(candidate.issuer),
        "reference_number": _normalize_space(candidate.reference_number),
        "issued_on": candidate.issued_on.isoformat() if candidate.issued_on else None,
        "valid_from": candidate.valid_from.isoformat() if candidate.valid_from else None,
        "valid_until": candidate.valid_until.isoformat() if candidate.valid_until else None,
        "period_start": candidate.period_start.isoformat() if candidate.period_start else None,
        "period_end": candidate.period_end.isoformat() if candidate.period_end else None,
        "source_page": candidate.source_page,
        "source_locator": candidate.source_locator,
        "source_excerpt": _normalize_space(candidate.source_excerpt),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _review_freshness(review: CompanyEvidenceReview | None, current_fingerprint: str) -> str:
    if review is None:
        return FRESHNESS_NOT_REVIEWED
    if review.review_status == REVIEW_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not review.reviewed_fingerprint:
        return FRESHNESS_STALE
    if review.reviewed_fingerprint != current_fingerprint:
        return FRESHNESS_STALE
    return FRESHNESS_CURRENT


def _company_or_404(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _document_or_404(db: Session, company_id: str, document_id: str) -> CompanyDocument:
    document = db.get(CompanyDocument, document_id)
    if document is None or document.company_id != company_id:
        raise HTTPException(status_code=404, detail="Company document not found")
    return document


def _evidence_or_404(db: Session, company_id: str, evidence_id: str) -> CompanyEvidence:
    evidence = db.execute(
        select(CompanyEvidence)
        .where(CompanyEvidence.id == evidence_id)
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
    ).scalar_one_or_none()
    if evidence is None or evidence.company_id != company_id:
        raise HTTPException(status_code=404, detail="Company evidence not found")
    if evidence.source_document.company_id != company_id:
        raise HTTPException(status_code=400, detail="Company evidence owner mismatch")
    return evidence


def _data_root() -> Path:
    configured_root = Path(get_settings().licitia_data_dir)
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[1] / configured_root
    configured_root.mkdir(parents=True, exist_ok=True)
    return configured_root


def _resolve_document_file_path(stored_relative_path: str) -> Path:
    if not stored_relative_path or not stored_relative_path.strip():
        raise HTTPException(status_code=400, detail="Document storage path is missing")

    normalized_path = stored_relative_path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)
    if pure_path.is_absolute() or any(part in ("", ".", "..") for part in pure_path.parts):
        raise HTTPException(status_code=400, detail="Document storage path is invalid")

    data_root = _data_root().resolve()
    resolved_path = (data_root / pure_path).resolve()
    if not resolved_path.is_relative_to(data_root):
        raise HTTPException(status_code=400, detail="Document storage path escapes the local data directory")
    return resolved_path


def _extract_pdf_segments(file_path: Path) -> list[SourceSegment]:
    pdf_document = fitz.open(str(file_path))
    try:
        segments: list[SourceSegment] = []
        for page_index in range(pdf_document.page_count):
            page = pdf_document[page_index]
            text = page.get_text("text")
            if not _normalize_space(text):
                continue
            paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if _normalize_space(item)]
            if not paragraphs:
                paragraphs = [text]
            for paragraph_index, paragraph in enumerate(paragraphs, start=1):
                segments.append(
                    SourceSegment(
                        source_page=page_index + 1,
                        source_locator=f"page:{page_index + 1}:paragraph:{paragraph_index}",
                        text=paragraph.strip(),
                    )
                )
        return segments
    finally:
        pdf_document.close()


def _extract_text_segments(file_path: Path) -> list[SourceSegment]:
    raw_bytes = file_path.read_bytes()
    decoded_text: str | None = None
    for encoding in ("utf-8", "latin-1"):
        try:
            decoded_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded_text is None:
        decoded_text = raw_bytes.decode("utf-8", errors="ignore")

    lines = [line.rstrip() for line in decoded_text.splitlines()]
    segments: list[SourceSegment] = []
    buffer: list[str] = []
    start_line = 1

    for line_number, line in enumerate(lines, start=1):
        if not _normalize_space(line):
            if buffer:
                segments.append(
                    SourceSegment(
                        source_page=None,
                        source_locator=f"lines:{start_line}-{line_number - 1}",
                        text="\n".join(buffer).strip(),
                    )
                )
                buffer = []
            start_line = line_number + 1
            continue
        if not buffer:
            start_line = line_number
        buffer.append(line)

    if buffer:
        segments.append(
            SourceSegment(
                source_page=None,
                source_locator=f"lines:{start_line}-{len(lines)}",
                text="\n".join(buffer).strip(),
            )
        )
    return [segment for segment in segments if _normalize_space(segment.text)]


def _extract_document_segments(document: CompanyDocument) -> tuple[str, list[SourceSegment], list[str]]:
    file_path = _resolve_document_file_path(document.stored_relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")

    extension = file_path.suffix.lower()
    mime_type = (document.mime_type or "").lower()
    warnings: list[str] = []

    if "pdf" in mime_type or extension == ".pdf":
        segments = _extract_pdf_segments(file_path)
        if segments:
            return TEXT_STATUS_EXTRACTED, segments, warnings
        warnings.extend(["TEXT_UNAVAILABLE", "NATIVE_PDF_TEXT_NOT_FOUND", "OCR_NOT_ENABLED_IN_MVP_05_2"])
        return TEXT_STATUS_UNAVAILABLE, [], warnings

    if extension in {".txt", ".md", ".csv"} or mime_type.startswith("text/"):
        segments = _extract_text_segments(file_path)
        if segments:
            return TEXT_STATUS_EXTRACTED, segments, warnings
        warnings.append("TEXT_UNAVAILABLE")
        return TEXT_STATUS_UNAVAILABLE, [], warnings

    warnings.extend(["TEXT_UNAVAILABLE", "UNSUPPORTED_FILE_TYPE"])
    return TEXT_STATUS_UNAVAILABLE, [], warnings


def _candidate_from_segment(
    *,
    evidence_type: str,
    subject_kind: str,
    subject_name: str | None,
    canonical_statement: str,
    segment: SourceSegment,
    locator_suffix: str,
    issuer: str | None = None,
    reference_number: str | None = None,
    issued_on: date | None = None,
    valid_from: date | None = None,
    valid_until: date | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    analysis_status: str = CompanyEvidenceAnalysisStatus.DETERMINED.value,
    source_locator: str | None = None,
    source_excerpt: str | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_type=evidence_type,
        subject_kind=subject_kind,
        subject_name=_canonical_case(subject_name),
        canonical_statement=_canonical_case(canonical_statement) or canonical_statement.strip(),
        issuer=_canonical_case(issuer),
        reference_number=_canonical_case(reference_number),
        issued_on=issued_on,
        valid_from=valid_from,
        valid_until=valid_until,
        period_start=period_start,
        period_end=period_end,
        analysis_status=analysis_status,
        origin=CompanyEvidenceOrigin.DETERMINISTIC.value,
        extractor_version=COMPANY_EVIDENCE_EXTRACTOR_VERSION,
        source_page=segment.source_page,
        source_locator=source_locator or f"{segment.source_locator}|{locator_suffix}",
        source_excerpt=source_excerpt or segment.text.strip(),
    )


def _detect_corporate_existence(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    if not re.search(r"\b(se constituy[oó]|fue constituida|acta constitutiva|constituida el)\b", text, flags=re.IGNORECASE):
        return []
    subject = _extract_subject(text, ("raz[oó]n social", "sociedad", "empresa", "denominaci[oó]n"))
    if subject is None:
        match = re.search(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9\s,\.\-]{5,})\s+(?:se constituy[oó]|fue constituida)", text)
        subject = _canonical_subject(match.group(1)) if match else None
    constitution_date = _extract_date_from_label(
        text,
        ("fecha de constituci[oó]n", "constituida el", "se constituy[oó] el", "fecha"),
    )
    statement = f"{subject or 'La entidad'} acredita su existencia legal"
    if constitution_date:
        statement = f"{statement} desde {constitution_date.isoformat()}."
    else:
        statement = f"{statement}."
    return [
        _candidate_from_segment(
            evidence_type=CompanyEvidenceType.CORPORATE_EXISTENCE.value,
            subject_kind=CompanyEvidenceSubjectKind.COMPANY.value,
            subject_name=subject,
            canonical_statement=statement,
            segment=segment,
            locator_suffix="corporate-existence-1",
            issued_on=constitution_date,
        )
    ]


def _detect_tax_registration(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    if not re.search(r"\b(rfc|registro federal de contribuyentes)\b", text, flags=re.IGNORECASE):
        return []
    rfc_match = _RFC_PATTERN.search(text.upper())
    if rfc_match is None:
        return []
    subject = _extract_subject(text, ("raz[oó]n social", "contribuyente", "nombre", "empresa"))
    if subject is None:
        subject = _extract_company_subject_from_phrase(
            text,
            (
                r"la\s+empresa\s+(.+?)\s+se\s+encuentra\s+registrada",
                r"empresa\s+(.+?)\s+se\s+encuentra\s+registrada",
                r"(.+?)\s+se\s+encuentra\s+registrada",
            ),
        )
    rfc_value = rfc_match.group(1)
    subject_text = subject or "La entidad"
    return [
        _candidate_from_segment(
            evidence_type=CompanyEvidenceType.TAX_REGISTRATION.value,
            subject_kind=CompanyEvidenceSubjectKind.COMPANY.value,
            subject_name=subject,
            canonical_statement=f"{subject_text} est\u00e1 registrada con RFC {rfc_value}.",
            segment=segment,
            locator_suffix="tax-registration-1",
            reference_number=rfc_value,
        )
    ]


def _detect_tax_compliance(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    lowered = text.lower()
    if "opini" not in lowered and "cumplimiento" not in lowered:
        return []
    if not any(token in lowered for token in ("fiscal", "sat", "seguridad social", "imss", "infonavit")):
        return []

    subject = _extract_subject(text, ("contribuyente", "raz[oó]n social", "empresa", "nombre"))
    issuer = _extract_issuer(text)
    valid_until = _extract_date_from_label(text, ("vigencia hasta", "v[aá]lida hasta", "vigente hasta", "validez hasta"))
    statement = _canonical_case(text) or text.strip()
    evidence_type = CompanyEvidenceType.SOCIAL_SECURITY_COMPLIANCE.value if any(token in lowered for token in ("seguridad social", "imss", "infonavit")) else CompanyEvidenceType.TAX_COMPLIANCE.value
    return [
        _candidate_from_segment(
            evidence_type=evidence_type,
            subject_kind=CompanyEvidenceSubjectKind.COMPANY.value,
            subject_name=subject,
            canonical_statement=statement,
            segment=segment,
            locator_suffix="compliance-opinion-1",
            issuer=issuer,
            valid_until=valid_until,
        )
    ]


def _detect_certification(segments: list[SourceSegment], index: int) -> list[EvidenceCandidate]:
    segment = segments[index]
    text = segment.text
    if not re.search(r"\b(certificaci[oó]n|iso\s*\d{4,5})\b", text, flags=re.IGNORECASE):
        return []
    if _is_negated_certification(text):
        return []

    anchored_subject = _extract_subject(text, ("titular", "empresa", "organización", "otorgado a", "certifica que"))
    if anchored_subject is None:
        anchored_subject = _extract_company_subject_from_phrase(
            text,
            (
                r"la\s+empresa\s+(.+?)\s+cuenta\s+con\s+certificaci[oó]n",
                r"(.+?)\s+cuenta\s+con\s+certificaci[oó]n",
            ),
        )
    if anchored_subject is None and re.search(r"(?:fue\s+emitid[oa]\s+por|emitid[oa]\s+por|otorgad[oa]\s+por)", text, flags=re.IGNORECASE):
        return []

    context_segments = _certification_context_segments(segments, index)
    context_text = _join_excerpt(context_segments)

    subject = anchored_subject or _extract_subject(
        context_text,
        ("titular", "empresa", "organización", "otorgado a", "certifica que"),
    )

    issuer = _extract_issuer(context_text)
    reference_number = _extract_reference(context_text)
    issued_on = _extract_date_from_label(context_text, ("fecha de emisi[oó]n", "emitido el", "emisi[oó]n"))
    valid_until = _extract_date_from_label(context_text, ("vigente hasta", "v[aá]lido hasta", "validez hasta", "fecha de vencimiento"))
    if subject is None and not issuer and not reference_number:
        return []
    statement_subject = subject or "La entidad"
    statement = f"{statement_subject} acredita una certificaci\u00f3n documental"
    if issuer:
        statement = f"{statement} emitida por {issuer}"
    if valid_until:
        statement = f"{statement}, vigente hasta {valid_until.isoformat()}"
    statement = f"{statement}."
    return [
        _candidate_from_segment(
            evidence_type=CompanyEvidenceType.CERTIFICATION.value,
            subject_kind=CompanyEvidenceSubjectKind.COMPANY.value,
            subject_name=subject,
            canonical_statement=statement,
            segment=segment,
            locator_suffix="certification-1",
            issuer=issuer,
            reference_number=reference_number,
            issued_on=issued_on,
            valid_until=valid_until,
            source_locator=f"{_join_locators(context_segments)}|certification-1",
            source_excerpt=context_text,
        )
    ]


def _detect_personnel_qualification(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    candidates: list[EvidenceCandidate] = []
    subject = _extract_subject(text, ("nombre", "profesionista", "empleado", "persona"))

    degree_match = re.search(r"(?:grado|t[ií]tulo|profesi[oó]n)\s*[:\-]\s*([^\n\.]+)", text, flags=re.IGNORECASE)
    if degree_match and subject:
        degree = _canonical_case(degree_match.group(1))
        if degree:
            candidates.append(
                _candidate_from_segment(
                    evidence_type=CompanyEvidenceType.PERSONNEL_QUALIFICATION.value,
                    subject_kind=CompanyEvidenceSubjectKind.PERSON.value,
                    subject_name=subject,
                    canonical_statement=f"{subject} acredita la calificaci\u00f3n {degree}.",
                    segment=segment,
                    locator_suffix="personnel-degree-1",
                )
            )

    reference_number = _extract_reference(text)
    if reference_number and subject:
        candidates.append(
            _candidate_from_segment(
                evidence_type=CompanyEvidenceType.PERSONNEL_QUALIFICATION.value,
                subject_kind=CompanyEvidenceSubjectKind.PERSON.value,
                subject_name=subject,
                canonical_statement=f"{subject} cuenta con credencial o licencia {reference_number}.",
                segment=segment,
                locator_suffix="personnel-license-1",
                reference_number=reference_number,
            )
        )

    if re.search(r"\b(certificaci[oó]n|curso|diploma)\b", text, flags=re.IGNORECASE) and subject:
        issuer = _extract_issuer(text)
        valid_until = _extract_date_from_label(text, ("vigente hasta", "v[aá]lido hasta", "validez hasta"))
        candidates.append(
            _candidate_from_segment(
                evidence_type=CompanyEvidenceType.PERSONNEL_QUALIFICATION.value,
                subject_kind=CompanyEvidenceSubjectKind.PERSON.value,
                subject_name=subject,
                canonical_statement=f"{subject} acredita formaci\u00f3n o certificaci\u00f3n de personal.",
                segment=segment,
                locator_suffix="personnel-certification-1",
                issuer=issuer,
                valid_until=valid_until,
            )
        )

    return candidates


def _detect_experience(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    if not any(token in text.lower() for token in ("cliente", "servicio", "contrato", "experiencia", "contratante")):
        return []
    period_match = re.search(
        rf"del\s+{_DATE_CAPTURE_PATTERN}\s+al\s+{_DATE_CAPTURE_PATTERN}",
        text,
        flags=re.IGNORECASE,
    )
    client_name = _extract_subject(text, ("cliente", "contratante"))
    subject = _extract_subject(text, ("empresa", "contratista", "proveedor"))
    service_match = re.search(r"(?:servicio|objeto|alcance)\s*[:\-]\s*([^\n\.]+)", text, flags=re.IGNORECASE)
    service_description = _canonical_case(service_match.group(1)) if service_match else None
    period_start = _parse_date(period_match.group(1)) if period_match else None
    period_end = _parse_date(period_match.group(2)) if period_match else None
    if client_name is None and service_description is None and period_match is None:
        return []
    subject_text = subject or "La empresa"
    statement = f"{subject_text} acredita experiencia documental"
    if service_description:
        statement = f"{statement} en {service_description}"
    if client_name:
        statement = f"{statement} para {client_name}"
    if period_start and period_end:
        statement = f"{statement} del {period_start.isoformat()} al {period_end.isoformat()}"
    statement = f"{statement}."
    return [
        _candidate_from_segment(
            evidence_type=CompanyEvidenceType.EXPERIENCE.value,
            subject_kind=CompanyEvidenceSubjectKind.COMPANY.value,
            subject_name=subject,
            canonical_statement=statement,
            segment=segment,
            locator_suffix="experience-1",
            issuer=client_name,
            period_start=period_start,
            period_end=period_end,
        )
    ]


def _detect_legal_authority(segment: SourceSegment) -> list[EvidenceCandidate]:
    text = segment.text
    if not re.search(r"\b(poder|representante legal|apoderado|facultades)\b", text, flags=re.IGNORECASE):
        return []
    subject = _extract_subject(text, ("representante legal", "apoderado", "nombre"))
    issuer = _extract_issuer(text)
    statement_subject = subject or "La persona referida"
    return [
        _candidate_from_segment(
            evidence_type=CompanyEvidenceType.LEGAL_AUTHORITY.value,
            subject_kind=CompanyEvidenceSubjectKind.PERSON.value if subject else CompanyEvidenceSubjectKind.OTHER.value,
            subject_name=subject,
            canonical_statement=f"{statement_subject} acredita facultades o poder de representaci\u00f3n.",
            segment=segment,
            locator_suffix="legal-authority-1",
            issuer=issuer,
        )
    ]


def _derive_candidates(document: CompanyDocument, segments: list[SourceSegment]) -> list[EvidenceCandidate]:
    per_segment_detectors = (
        _detect_corporate_existence,
        _detect_tax_registration,
        _detect_tax_compliance,
        _detect_personnel_qualification,
        _detect_experience,
        _detect_legal_authority,
    )
    by_fingerprint: dict[str, EvidenceCandidate] = {}
    for index, segment in enumerate(segments):
        for detector in per_segment_detectors:
            for candidate in detector(segment):
                fingerprint = _evidence_fingerprint(document, candidate)
                by_fingerprint[fingerprint] = candidate
        for candidate in _detect_certification(segments, index):
            fingerprint = _evidence_fingerprint(document, candidate)
            by_fingerprint[fingerprint] = candidate
    return list(by_fingerprint.values())


def _reconcile_key(evidence_type: str, subject_kind: str, source_page: int | None, source_locator: str | None) -> str:
    payload = {
        "evidence_type": evidence_type,
        "subject_kind": subject_kind,
        "source_page": source_page,
        "source_locator": source_locator or "",
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _serialize_evidence_row(evidence: CompanyEvidence) -> dict[str, Any]:
    if evidence.source_document.company_id != evidence.company_id:
        raise HTTPException(status_code=400, detail="Company evidence owner mismatch")
    review = evidence.review
    freshness = _review_freshness(review, evidence.semantic_fingerprint)
    system_warnings: list[str] = []
    if evidence.analysis_status == CompanyEvidenceAnalysisStatus.REVIEW_REQUIRED.value:
        system_warnings.append("SYSTEM_REVIEW_REQUIRED")
    if evidence.source_document.archived_at is not None:
        system_warnings.append("SOURCE_DOCUMENT_ARCHIVED")
    if not evidence.source_document.is_current:
        system_warnings.append("SOURCE_DOCUMENT_NOT_CURRENT")

    return {
        "id": evidence.id,
        "company_id": evidence.company_id,
        "company_document_id": evidence.company_document_id,
        "evidence_type": evidence.evidence_type,
        "subject_kind": evidence.subject_kind,
        "subject_name": evidence.subject_name,
        "canonical_statement": evidence.canonical_statement,
        "issuer": evidence.issuer,
        "reference_number": evidence.reference_number,
        "issued_on": evidence.issued_on,
        "valid_from": evidence.valid_from,
        "valid_until": evidence.valid_until,
        "period_start": evidence.period_start,
        "period_end": evidence.period_end,
        "analysis_status": evidence.analysis_status,
        "origin": evidence.origin,
        "extractor_version": evidence.extractor_version,
        "source_page": evidence.source_page,
        "source_locator": evidence.source_locator,
        "source_excerpt": evidence.source_excerpt,
        "semantic_fingerprint": evidence.semantic_fingerprint,
        "system_warnings": system_warnings,
        "review_freshness": freshness,
        "created_at": evidence.created_at,
        "updated_at": evidence.updated_at,
        "source_document": {
            "id": evidence.source_document.id,
            "company_id": evidence.source_document.company_id,
            "original_filename": evidence.source_document.original_filename,
            "document_type": evidence.source_document.document_type,
            "label": evidence.source_document.label,
            "status": evidence.source_document.status,
            "archived_at": evidence.source_document.archived_at,
            "revision_number": evidence.source_document.revision_number,
            "is_current": evidence.source_document.is_current,
        },
        "review": None
        if review is None
        else {
            "id": review.id,
            "company_id": review.company_id,
            "company_evidence_id": review.company_evidence_id,
            "review_status": review.review_status,
            "review_note": review.review_note,
            "reviewed_fingerprint": review.reviewed_fingerprint,
            "reviewed_at": review.reviewed_at,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        },
    }


def _collection_payload(evidence_rows: list[CompanyEvidence]) -> dict[str, Any]:
    rows = [_serialize_evidence_row(item) for item in evidence_rows]
    return {
        "summary": {
            "evidence_count": len(rows),
            "determined_count": sum(1 for row in rows if row["analysis_status"] == CompanyEvidenceAnalysisStatus.DETERMINED.value),
            "review_required_count": sum(
                1 for row in rows if row["analysis_status"] == CompanyEvidenceAnalysisStatus.REVIEW_REQUIRED.value
            ),
            "validated_count": sum(
                1
                for row in rows
                if row["review"] is not None and row["review"]["review_status"] == CompanyEvidenceReviewStatus.APPROVED.value
            ),
            "pending_review_count": sum(
                1
                for row in rows
                if row["review"] is None or row["review"]["review_status"] == CompanyEvidenceReviewStatus.PENDING.value
            ),
            "rejected_count": sum(
                1
                for row in rows
                if row["review"] is not None and row["review"]["review_status"] == CompanyEvidenceReviewStatus.REJECTED.value
            ),
            "historical_source_count": sum(1 for row in rows if not row["source_document"]["is_current"]),
            "current_review_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_CURRENT),
            "stale_review_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_STALE),
            "not_reviewed_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_NOT_REVIEWED),
        },
        "evidence": rows,
    }


def analyze_company_document_evidence(db: Session, company_id: str, document_id: str) -> dict[str, Any]:
    _company_or_404(db, company_id)
    document = _document_or_404(db, company_id, document_id)

    text_status, segments, warnings = _extract_document_segments(document)
    extracted_candidates = _derive_candidates(document, segments) if text_status == TEXT_STATUS_EXTRACTED else []

    existing_rows = db.execute(
        select(CompanyEvidence)
        .where(
            CompanyEvidence.company_id == company_id,
            CompanyEvidence.company_document_id == document_id,
            CompanyEvidence.origin == CompanyEvidenceOrigin.DETERMINISTIC.value,
        )
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
        .order_by(CompanyEvidence.created_at.asc(), CompanyEvidence.id.asc())
    ).scalars().all()

    existing_by_key = {
        _reconcile_key(item.evidence_type, item.subject_kind, item.source_page, item.source_locator): item for item in existing_rows
    }

    for candidate in extracted_candidates:
        reconcile_key = _reconcile_key(candidate.evidence_type, candidate.subject_kind, candidate.source_page, candidate.source_locator)
        semantic_fingerprint = _evidence_fingerprint(document, candidate)
        evidence = existing_by_key.get(reconcile_key)
        if evidence is None:
            evidence = CompanyEvidence(
                company_id=company_id,
                company_document_id=document_id,
                evidence_type=candidate.evidence_type,
                subject_kind=candidate.subject_kind,
                subject_name=candidate.subject_name,
                canonical_statement=candidate.canonical_statement,
                issuer=candidate.issuer,
                reference_number=candidate.reference_number,
                issued_on=candidate.issued_on,
                valid_from=candidate.valid_from,
                valid_until=candidate.valid_until,
                period_start=candidate.period_start,
                period_end=candidate.period_end,
                analysis_status=candidate.analysis_status,
                origin=candidate.origin,
                extractor_version=candidate.extractor_version,
                source_page=candidate.source_page,
                source_locator=candidate.source_locator,
                source_excerpt=candidate.source_excerpt,
                semantic_fingerprint=semantic_fingerprint,
            )
            db.add(evidence)
        else:
            evidence.subject_name = candidate.subject_name
            evidence.canonical_statement = candidate.canonical_statement
            evidence.issuer = candidate.issuer
            evidence.reference_number = candidate.reference_number
            evidence.issued_on = candidate.issued_on
            evidence.valid_from = candidate.valid_from
            evidence.valid_until = candidate.valid_until
            evidence.period_start = candidate.period_start
            evidence.period_end = candidate.period_end
            evidence.analysis_status = candidate.analysis_status
            evidence.extractor_version = candidate.extractor_version
            evidence.source_page = candidate.source_page
            evidence.source_locator = candidate.source_locator
            evidence.source_excerpt = candidate.source_excerpt
            evidence.semantic_fingerprint = semantic_fingerprint

    db.commit()

    evidence_rows = db.execute(
        select(CompanyEvidence)
        .where(CompanyEvidence.company_id == company_id, CompanyEvidence.company_document_id == document_id)
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
        .order_by(CompanyEvidence.created_at.asc(), CompanyEvidence.id.asc())
    ).scalars().all()

    collection = _collection_payload(evidence_rows)
    return {
        "summary": {
            "document_id": document.id,
            "company_id": company_id,
            "text_extraction_status": text_status,
            "extractor_version": COMPANY_EVIDENCE_EXTRACTOR_VERSION,
            "warnings": warnings,
            **collection["summary"],
        },
        "evidence": collection["evidence"],
    }


def list_company_evidence(
    db: Session,
    company_id: str,
    *,
    document_id: str | None = None,
    evidence_type: str | None = None,
    subject_kind: str | None = None,
    review_status: str | None = None,
    current_source_only: bool = False,
    include_archived_sources: bool = False,
) -> dict[str, Any]:
    _company_or_404(db, company_id)

    statement = (
        select(CompanyEvidence)
        .join(CompanyEvidence.source_document)
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
        .where(CompanyEvidence.company_id == company_id)
    )
    if document_id:
        statement = statement.where(CompanyEvidence.company_document_id == document_id)
    if evidence_type:
        statement = statement.where(CompanyEvidence.evidence_type == evidence_type)
    if subject_kind:
        statement = statement.where(CompanyEvidence.subject_kind == subject_kind)
    if current_source_only:
        statement = statement.where(CompanyDocument.is_current.is_(True))
    if not include_archived_sources:
        statement = statement.where(CompanyDocument.archived_at.is_(None))

    evidence_rows = db.execute(statement.order_by(CompanyEvidence.created_at.asc(), CompanyEvidence.id.asc())).scalars().all()
    if review_status:
        evidence_rows = [
            item
            for item in evidence_rows
            if (item.review.review_status if item.review is not None else CompanyEvidenceReviewStatus.PENDING.value) == review_status
        ]
    return _collection_payload(evidence_rows)


def get_company_document_evidence(
    db: Session,
    company_id: str,
    document_id: str,
    *,
    include_archived_sources: bool = True,
) -> dict[str, Any]:
    _company_or_404(db, company_id)
    _document_or_404(db, company_id, document_id)
    return list_company_evidence(
        db,
        company_id,
        document_id=document_id,
        include_archived_sources=include_archived_sources,
    )


def review_company_evidence(
    db: Session,
    company_id: str,
    evidence_id: str,
    *,
    review_status: str,
    review_note: str | None,
) -> dict[str, Any]:
    if review_status not in {REVIEW_PENDING, REVIEW_APPROVED, REVIEW_NEEDS_REVIEW, REVIEW_REJECTED}:
        raise HTTPException(status_code=400, detail="Unsupported review status")
    if review_status == REVIEW_REJECTED and not _normalize_space(review_note):
        raise HTTPException(status_code=400, detail="Rejected evidence requires a review note")

    evidence = _evidence_or_404(db, company_id, evidence_id)
    review = evidence.review
    if review is None:
        review = CompanyEvidenceReview(company_id=company_id, company_evidence_id=evidence.id)
        db.add(review)

    review.company_id = company_id
    review.review_status = review_status
    review.review_note = _canonical_case(review_note)
    review.reviewed_at = datetime.now(timezone.utc)
    review.reviewed_fingerprint = evidence.semantic_fingerprint if review_status != REVIEW_PENDING else None

    db.commit()
    refreshed = _evidence_or_404(db, company_id, evidence_id)
    return _serialize_evidence_row(refreshed)


def create_manual_company_evidence(
    db: Session,
    company_id: str,
    document_id: str,
    *,
    evidence_type: str,
    subject_kind: str,
    canonical_statement: str,
    source_excerpt: str,
    subject_name: str | None = None,
    issuer: str | None = None,
    reference_number: str | None = None,
    issued_on: date | None = None,
    valid_from: date | None = None,
    valid_until: date | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    source_locator: str | None = None,
    source_page: int | None = None,
    review_note: str | None = None,
) -> dict[str, Any]:
    _company_or_404(db, company_id)
    document = _document_or_404(db, company_id, document_id)

    if evidence_type not in {item.value for item in CompanyEvidenceType}:
        raise HTTPException(status_code=400, detail="Unsupported evidence type")
    if subject_kind not in {item.value for item in CompanyEvidenceSubjectKind}:
        raise HTTPException(status_code=400, detail="Unsupported subject kind")
    normalized_statement = _canonical_case(canonical_statement)
    normalized_excerpt = _trim_preserve_lines(source_excerpt)
    if not normalized_statement:
        raise HTTPException(status_code=400, detail="canonical_statement is required")
    if not normalized_excerpt:
        raise HTTPException(status_code=400, detail="source_excerpt is required")

    candidate = EvidenceCandidate(
        evidence_type=evidence_type,
        subject_kind=subject_kind,
        subject_name=_canonical_subject(subject_name),
        canonical_statement=normalized_statement,
        issuer=_canonical_case(issuer),
        reference_number=_canonical_case(reference_number),
        issued_on=issued_on,
        valid_from=valid_from,
        valid_until=valid_until,
        period_start=period_start,
        period_end=period_end,
        analysis_status=CompanyEvidenceAnalysisStatus.DETERMINED.value,
        origin=CompanyEvidenceOrigin.HUMAN.value,
        extractor_version=MANUAL_EVIDENCE_EXTRACTOR_VERSION,
        source_page=source_page,
        source_locator=_canonical_case(source_locator) or "manual-entry",
        source_excerpt=normalized_excerpt,
    )
    evidence = CompanyEvidence(
        company_id=company_id,
        company_document_id=document.id,
        evidence_type=candidate.evidence_type,
        subject_kind=candidate.subject_kind,
        subject_name=candidate.subject_name,
        canonical_statement=candidate.canonical_statement,
        issuer=candidate.issuer,
        reference_number=candidate.reference_number,
        issued_on=candidate.issued_on,
        valid_from=candidate.valid_from,
        valid_until=candidate.valid_until,
        period_start=candidate.period_start,
        period_end=candidate.period_end,
        analysis_status=candidate.analysis_status,
        origin=candidate.origin,
        extractor_version=candidate.extractor_version,
        source_page=candidate.source_page,
        source_locator=candidate.source_locator,
        source_excerpt=candidate.source_excerpt,
        semantic_fingerprint=_evidence_fingerprint(document, candidate),
    )
    db.add(evidence)
    db.flush()

    review = CompanyEvidenceReview(
        company_id=company_id,
        company_evidence_id=evidence.id,
        review_status=CompanyEvidenceReviewStatus.APPROVED.value,
        review_note=_canonical_case(review_note),
        reviewed_fingerprint=evidence.semantic_fingerprint,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()

    refreshed = _evidence_or_404(db, company_id, evidence.id)
    return _serialize_evidence_row(refreshed)