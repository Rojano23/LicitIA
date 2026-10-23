"""Canonical Tender creation shared by manual API and explicit Discovery handoff."""
from fastapi import HTTPException
from app.models import Tender

def create_record(db,title,institution_profile=None,external_reference=None,*,commit=True):
    if not title.strip() or len(title.strip())>255:raise HTTPException(422,'VALID_TENDER_TITLE_REQUIRED')
    tender=Tender(title=title.strip(),institution_profile=institution_profile.strip() if institution_profile else None,
        external_reference=external_reference.strip() if external_reference else None,status='DRAFT')
    db.add(tender);db.flush()
    if commit:db.commit();db.refresh(tender)
    return tender
