from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import Tender
from app.schemas import TenderCreate, TenderRead

settings = get_settings()

app = FastAPI(title="LicitIA", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tenders", response_model=TenderRead, status_code=status.HTTP_201_CREATED)
def create_tender(payload: TenderCreate, db: Session = Depends(get_db)) -> Tender:
    cleaned_title = payload.title.strip()
    if not cleaned_title:
        raise HTTPException(status_code=400, detail="Tender title is required")

    tender = Tender(
        title=cleaned_title,
        institution_profile=(payload.institution_profile.strip() if payload.institution_profile else None),
        external_reference=(payload.external_reference.strip() if payload.external_reference else None),
        status="DRAFT",
    )

    db.add(tender)
    db.commit()
    db.refresh(tender)
    return tender


@app.get("/tenders", response_model=list[TenderRead])
def list_tenders(db: Session = Depends(get_db)) -> list[Tender]:
    statement = select(Tender).order_by(Tender.created_at.desc())
    return db.execute(statement).scalars().all()


@app.get("/tenders/{tender_id}", response_model=TenderRead)
def get_tender(tender_id: str, db: Session = Depends(get_db)) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender
