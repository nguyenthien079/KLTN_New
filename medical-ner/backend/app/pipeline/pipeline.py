from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Article, Sentence, PipelineStatus, CrawlStatus
from app.pipeline.segmenter import SentenceSegmenter
from app.pipeline.normalizer import SentenceNormalizer
from app.pipeline.deduplicator import SemanticDeduplicator


class MedicalTextPipeline:
    """Main text processing pipeline: segment → normalize → deduplicate → save"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.segmenter = SentenceSegmenter()
        self.normalizer = SentenceNormalizer()
        self.deduplicator = SemanticDeduplicator()

    async def process_article(self, article_id: int) -> Dict:
        """Process a single article through the full pipeline"""
        result = await self.db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one()

        stats = {
            "article_id": article_id,
            "raw_text_length": len(article.clean_text or ""),
            "sentences_extracted": 0,
            "sentences_after_normalization": 0,
            "sentences_after_dedup": 0
        }

        if not article.clean_text:
            return stats

        # Step 1: Segmentation
        raw_sentences = self.segmenter.segment(article.clean_text)
        stats["sentences_extracted"] = len(raw_sentences)

        # Step 2: Normalization
        normalized_sentences = []
        for sent in raw_sentences:
            normalized = self.normalizer.normalize(sent)
            if normalized:
                normalized_sentences.append({"raw": sent, "normalized": normalized})
        stats["sentences_after_normalization"] = len(normalized_sentences)

        # Step 3: Semantic deduplication
        texts = [s["normalized"] for s in normalized_sentences]
        to_remove = self.deduplicator.find_duplicates(texts)

        final_sentences = [
            s for i, s in enumerate(normalized_sentences)
            if i not in to_remove
        ]
        stats["sentences_after_dedup"] = len(final_sentences)

        # Step 4: Save to database
        for sent_data in final_sentences:
            sentence = Sentence(
                article_id=article_id,
                raw_text=sent_data["raw"],
                normalized_text=sent_data["normalized"],
                char_count=len(sent_data["normalized"]),
                word_count=len(sent_data["normalized"].split()),
                pipeline_status=PipelineStatus.PROCESSED,
                is_medical=True
            )
            self.db.add(sentence)

        await self.db.commit()
        return stats

    async def process_all_articles(self) -> Dict:
        """Process all completed articles that have not been processed yet"""
        result = await self.db.execute(
            select(Article).where(Article.status == CrawlStatus.COMPLETED)
        )
        articles = result.scalars().all()

        total_stats = {"articles_processed": 0, "total_sentences": 0}

        for article in articles:
            stats = await self.process_article(article.id)
            total_stats["articles_processed"] += 1
            total_stats["total_sentences"] += stats["sentences_after_dedup"]
            print(f"Processed article {article.id}: {stats['sentences_after_dedup']} sentences")

        return total_stats
