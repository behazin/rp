# FILE: ./services/management-api/app/api/endpoints/management.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from common.database import get_db
from app.models import management as models
from app.schemas import management as schemas

router = APIRouter()

# --- مدیریت منابع (Sources) ---
@router.get("/sources", response_model=List[schemas.SourceInDB])
def get_all_sources(db: Session = Depends(get_db)):
    """لیست تمام منابع ثبت شده را برمی‌گرداند."""
    return db.query(models.Source).all()

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

# --- مدیریت مقصدها (Destinations) ---

@router.post("/destinations", response_model=schemas.DestinationInDB, status_code=201)
def create_destination(dest: schemas.DestinationCreate, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.name == dest.name).first()
    if db_dest:
        raise HTTPException(status_code=400, detail="Destination name already exists")
        
    new_dest = models.Destination(**dest.model_dump())
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

# --- مدیریت ارتباط بین منابع و مقصدها ---

@router.post("/sources/{source_id}/link/{destination_id}", response_model=schemas.SourceInDB)
def link_source_to_destination(source_id: int, destination_id: int, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    db_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    db_source.destinations.append(db_dest)
    db.commit()
    db.refresh(db_source)
    return db_source

# --- مدیریت پست‌ها (Posts) ---

@router.get("/posts/exists")
def post_exists(url: str, db: Session = Depends(get_db)):
    """بررسی می‌کند آیا پستی با URL مشخص شده وجود دارد یا خیر."""
    db_post = db.query(models.Post).filter(models.Post.url_original == url).first()
    return {"exists": db_post is not None}

@router.get("/posts/pending", response_model=List[schemas.PostInDB])
def get_pending_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """لیست پست‌های در انتظار تایید را برمی‌گرداند."""
    posts = db.query(models.Post).filter(models.Post.status == models.PostStatus.PENDING_APPROVAL).offset(skip).limit(limit).all()
    return posts

@router.post("/posts/{post_id}/approve", response_model=schemas.PostInDB)
def approve_post(post_id: int, db: Session = Depends(get_db)):
    """یک پست را تایید می‌کند و وضعیت آن را به 'approved' تغییر می‌دهد."""
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db_post.status = models.PostStatus.APPROVED
    db.commit()
    db.refresh(db_post)
    # TODO: در آینده، در اینجا یک پیام به RabbitMQ ارسال می‌شود
    return db_post