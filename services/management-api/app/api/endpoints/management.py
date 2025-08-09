from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from common.database import get_db
from app.models import management as models
from app.schemas import management as schemas

router = APIRouter()

@router.post("/sources", response_model=schemas.SourceInDB, status_code=201)
def create_source(source: schemas.SourceCreate, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.url == str(source.url)).first()
    if db_source:
        raise HTTPException(status_code=400, detail="Source URL already registered")
    
    new_source = models.Source(name=source.name, url=str(source.url))
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source

@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(db_source)
    db.commit()
    return

@router.post("/destinations", response_model=schemas.DestinationInDB, status_code=201)
def create_destination(dest: schemas.DestinationCreate, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.name == dest.name).first()
    if db_dest:
        raise HTTPException(status_code=400, detail="Destination name already exists")
        
    new_dest = models.Destination(**dest.model_dump()) # Use .model_dump() for Pydantic v2
    db.add(new_dest)
    db.commit()
    db.refresh(new_dest)
    return new_dest

@router.delete("/destinations/{destination_id}", status_code=204)
def delete_destination(destination_id: int, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destination not found")
        
    db.delete(db_dest)
    db.commit()
    return