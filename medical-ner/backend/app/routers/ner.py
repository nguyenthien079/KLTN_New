import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Global instances — initialized at startup via app lifespan
_ner_pipeline = None
_segmenter = None
_executor = ThreadPoolExecutor(max_workers=2)


def get_ner_pipeline():
    global _ner_pipeline
    if _ner_pipeline is None:
        from app.ml.ensemble import MedicalNERPipeline
        _ner_pipeline = MedicalNERPipeline(
            use_phobert=True,
            use_dictionary=True,
            use_rule_based=True,
            min_confidence=0.4
        )
    return _ner_pipeline


def get_segmenter():
    global _segmenter
    if _segmenter is None:
        from app.pipeline.segmenter import SentenceSegmenter
        _segmenter = SentenceSegmenter()
    return _segmenter


# --- Schemas ---

class TextAnalysisRequest(BaseModel):
    text: str


class URLAnalysisRequest(BaseModel):
    url: str


class EntityResponse(BaseModel):
    text: str
    type: str
    start: int
    end: int
    confidence: float
    source: str


class SentenceAnalysis(BaseModel):
    sentence: str
    entities: List[EntityResponse]


class AnalysisResponse(BaseModel):
    source: str
    text: str
    sentences: List[SentenceAnalysis]
    stats: Dict
    processing_time_ms: float


# --- Helpers ---

async def _analyze_sentences(text: str) -> tuple[List[SentenceAnalysis], Dict]:
    loop = asyncio.get_event_loop()
    segmenter = get_segmenter()
    pipeline = get_ner_pipeline()

    sentences = await loop.run_in_executor(_executor, segmenter.segment, text)

    results = []
    entity_counts: Dict[str, int] = {}

    for sentence in sentences:
        entities = await loop.run_in_executor(_executor, pipeline.extract, sentence)
        entity_responses = []
        for e in entities:
            entity_responses.append(EntityResponse(
                text=e.text,
                type=e.entity_type,
                start=e.start,
                end=e.end,
                confidence=round(e.confidence, 4),
                source=e.source
            ))
            entity_counts[e.entity_type] = entity_counts.get(e.entity_type, 0) + 1

        results.append(SentenceAnalysis(sentence=sentence, entities=entity_responses))

    stats = {
        "total_sentences": len(sentences),
        "total_entities": sum(entity_counts.values()),
        "by_type": entity_counts
    }
    return results, stats


# --- Endpoints ---

@router.post("/analyze-text", response_model=AnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    if not request.text or len(request.text) < 10:
        raise HTTPException(status_code=400, detail="Text too short (min 10 chars)")

    t0 = time.time()
    sentences, stats = await _analyze_sentences(request.text)
    elapsed = round((time.time() - t0) * 1000, 2)

    return AnalysisResponse(
        source="text",
        text=request.text,
        sentences=sentences,
        stats=stats,
        processing_time_ms=elapsed
    )


@router.post("/analyze-url", response_model=AnalysisResponse)
async def analyze_url(request: URLAnalysisRequest):
    from app.crawler.extractor import HTMLExtractor

    t0 = time.time()
    extractor = HTMLExtractor()
    html = await extractor.fetch_html(request.url)

    if not html:
        raise HTTPException(status_code=400, detail="Could not fetch URL")

    extracted = extractor.extract_clean_text(html)
    text = extracted["clean_text"]

    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Extracted text too short")

    sentences, stats = await _analyze_sentences(text)
    stats["url"] = request.url
    stats["title"] = extracted.get("title", "")

    elapsed = round((time.time() - t0) * 1000, 2)
    preview = text[:500] + "..." if len(text) > 500 else text

    return AnalysisResponse(
        source="url",
        text=preview,
        sentences=sentences,
        stats=stats,
        processing_time_ms=elapsed
    )
