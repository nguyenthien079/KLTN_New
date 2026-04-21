import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from import_from_new_data import convert_new_data

EXPECTED_LABELS = {
    "O",
    "B-DISEASE", "I-DISEASE",
    "B-DRUG", "I-DRUG",
    "B-SYMPTOM", "I-SYMPTOM",
    "B-TREATMENT", "I-TREATMENT",
    "B-BODY_PART", "I-BODY_PART",
    "B-TEST", "I-TEST",
    "B-VALUE", "I-VALUE",
    "B-DATE", "I-DATE",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert new labeled data and train PhoBERT NER")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("../../new/data"),
        help="Directory containing new labeled JSON files",
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=Path("data/training"),
        help="Directory to write train/val/test JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/phobert-medical"),
        help="Directory to write trained model",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for slug split")
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument(
        "--model-name",
        type=str,
        default="vinai/phobert-base",
        help="Base model name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only convert and validate data; skip training",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 70)
    print("Step 1/2: Convert labeled data from new/data")
    print("=" * 70)
    stats = convert_new_data(
        data_dir=args.data_dir,
        output_dir=args.training_dir,
        seed=args.seed,
    )

    print(f"Train / Val / Test samples: {stats['train_samples']} / {stats['val_samples']} / {stats['test_samples']}")
    print(f"Unique slugs (train/val/test): {stats['train_slugs']} / {stats['val_slugs']} / {stats['test_slugs']}")
    unknown_labels = set(stats["label_distribution"]) - EXPECTED_LABELS
    if unknown_labels:
        raise ValueError(f"Unknown labels generated: {sorted(unknown_labels)}")
    print(f"Generated labels verified: {len(EXPECTED_LABELS)} labels")

    if args.dry_run:
        print("\nDry-run complete: conversion and validation passed, training skipped.")
        return

    from app.ml.trainer import PhoBERTNERTrainer

    trainer = PhoBERTNERTrainer(model_name=args.model_name)
    assert trainer.num_labels == 17, f"Expected 17 labels, got {trainer.num_labels}"
    assert "B-VALUE" in trainer.label2id, "B-VALUE missing from trainer labels"
    assert "B-DATE" in trainer.label2id, "B-DATE missing from trainer labels"
    print(f"Trainer labels verified: {trainer.num_labels} labels")

    train_dataset = trainer.load_dataset(args.training_dir / "train.json")
    val_dataset = trainer.load_dataset(args.training_dir / "val.json")
    print(f"Loaded datasets: train={len(train_dataset)}, val={len(val_dataset)}")

    print("\n" + "=" * 70)
    print("Step 2/2: Train PhoBERT NER")
    print("=" * 70)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.train(
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
