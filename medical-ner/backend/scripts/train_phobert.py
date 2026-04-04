import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.trainer import PhoBERTNERTrainer


def main():
    print("="*60)
    print("PhoBERT Medical NER Training")
    print("="*60 + "\n")

    trainer = PhoBERTNERTrainer(model_name="vinai/phobert-base")

    data_dir = Path("data/training")
    train_dataset = trainer.load_dataset(data_dir / "train.json")
    val_dataset = trainer.load_dataset(data_dir / "val.json")

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples:   {len(val_dataset)}\n")

    output_dir = Path("models/phobert-medical")
    output_dir.mkdir(parents=True, exist_ok=True)

    trainer.train(
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        output_dir=output_dir,
        num_epochs=5,
        learning_rate=2e-5,
        batch_size=16
    )

    print("\n" + "="*60)
    print("Training completed!")
    print("="*60)


if __name__ == "__main__":
    main()
