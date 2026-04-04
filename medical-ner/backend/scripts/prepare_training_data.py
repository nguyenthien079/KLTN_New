import asyncio
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Sentence
from app.ml.data_preparation import DataPreparator


async def main():
    dict_dir = Path("data/dicts")
    preparator = DataPreparator(dict_dir)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Sentence)
            .where(Sentence.is_medical == True)
            .where(Sentence.is_duplicate == False)
        )
        sentences = result.scalars().all()

    print(f"Loaded {len(sentences)} sentences from database")

    sentence_texts = [s.normalized_text for s in sentences if s.normalized_text]
    dataset = preparator.create_dataset(sentence_texts)

    print(f"Created {len(dataset)} labeled samples")

    train, val, test = preparator.split_dataset(dataset)

    print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")

    output_dir = Path("data/training")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "train.json", 'w', encoding='utf-8') as f:
        json.dump(train, f, ensure_ascii=False, indent=2)

    with open(output_dir / "val.json", 'w', encoding='utf-8') as f:
        json.dump(val, f, ensure_ascii=False, indent=2)

    with open(output_dir / "test.json", 'w', encoding='utf-8') as f:
        json.dump(test, f, ensure_ascii=False, indent=2)

    print("\nTraining data saved to data/training/")


if __name__ == "__main__":
    asyncio.run(main())
