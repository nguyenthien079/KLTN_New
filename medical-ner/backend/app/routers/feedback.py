from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.correction import Correction

router = APIRouter()


# --- Schemas ---

class EntityItem(BaseModel):
    """Single entity item for correction"""
    text: str
    type: str
    start: int
    end: int
    confidence: float
    source: str


class CorrectionItem(BaseModel):
    """Single correction containing original and corrected entities"""
    original_text: str
    original_entities: List[EntityItem]
    corrected_entities: List[EntityItem]


class SubmitRequest(BaseModel):
    """Request to submit multiple corrections"""
    corrections: List[CorrectionItem]


class SubmitResponse(BaseModel):
    """Response after submitting corrections"""
    saved: int
    message: str


class StatsResponse(BaseModel):
    """Statistics about corrections"""
    total: int


class BIOToken(BaseModel):
    """BIO format export"""
    id: str
    text: str
    tokens: List[str]
    tags: List[str]


# --- Endpoints ---

@router.post("/submit", response_model=SubmitResponse)
async def submit_corrections(
    request: SubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save human corrections to database.
    Each correction contains original model predictions and human-corrected entities.
    """
    try:
        saved_count = 0
        
        for item in request.corrections:
            correction = Correction(
                original_text=item.original_text,
                original_entities=[e.model_dump() for e in item.original_entities],
                corrected_entities=[e.model_dump() for e in item.corrected_entities]
            )
            db.add(correction)
            saved_count += 1
        
        await db.commit()
        
        return SubmitResponse(
            saved=saved_count,
            message=f"Đã lưu {saved_count} câu vào hệ thống"
        )
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu corrections: {str(e)}")


@router.get("/export", response_model=List[BIOToken])
async def export_corrections(
    db: AsyncSession = Depends(get_db)
):
    """
    Export all corrections in BIO format for training.
    Converts entity annotations to BIO tags compatible with NER training.
    """
    try:
        result = await db.execute(select(Correction))
        corrections = result.scalars().all()
        
        bio_data = []
        
        for corr in corrections:
            # Convert corrected entities to BIO format
            bio_item = convert_to_bio(
                corr.id,
                corr.original_text,
                corr.corrected_entities
            )
            bio_data.append(bio_item)
        
        return bio_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi export: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get total number of corrections in database"""
    try:
        result = await db.execute(select(func.count(Correction.id)))
        total = result.scalar()
        
        return StatsResponse(total=total or 0)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy stats: {str(e)}")


# --- Helper Functions ---

def convert_to_bio(correction_id: str, text: str, entities: List[dict]) -> BIOToken:
    """
    Convert entity annotations to BIO format.
    
    Args:
        correction_id: Unique ID of correction
        text: Original sentence text
        entities: List of entity dictionaries with {text, type, start, end}
    
    Returns:
        BIOToken with tokens and BIO tags
    """
    # Simple tokenization by splitting on whitespace
    # In production, use proper Vietnamese tokenizer (underthesea)
    tokens = text.split()
    tags = ["O"] * len(tokens)
    
    # Calculate character position for each token
    char_positions = []
    current_pos = 0
    for token in tokens:
        start_pos = text.find(token, current_pos)
        end_pos = start_pos + len(token)
        char_positions.append((start_pos, end_pos))
        current_pos = end_pos
    
    # Assign BIO tags based on entity positions
    for entity in entities:
        entity_start = entity["start"]
        entity_end = entity["end"]
        entity_type = entity["type"]
        
        first_token = True
        for idx, (token_start, token_end) in enumerate(char_positions):
            # Check if token overlaps with entity
            if token_start < entity_end and token_end > entity_start:
                if first_token:
                    tags[idx] = f"B-{entity_type}"
                    first_token = False
                else:
                    tags[idx] = f"I-{entity_type}"
    
    return BIOToken(
        id=correction_id,
        text=text,
        tokens=tokens,
        tags=tags
    )
