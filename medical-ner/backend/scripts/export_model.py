"""
Export trained PhoBERT NER model to:
  - pytorch_model.pt     (TorchScript / state dict)
  - tokenizer.pkl        (tokenizer object)
  - label_map.json       (id2label / label2id)
  - model_info.json      (metadata)
"""
import sys
import os
import json
import pickle
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

# ── Paths ──────────────────────────────────────────────────────────────────────
MODEL_DIR  = Path("models/phobert-medical/final_model")
EXPORT_DIR = Path("models/phobert-medical/exported")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def _normalize_id2label(raw_id2label):
    return {int(key): value for key, value in raw_id2label.items()}


def export():
    print("=" * 60)
    print("Exporting PhoBERT Medical NER Model")
    print("=" * 60)

    if not MODEL_DIR.exists():
        print(f"[ERROR] Model not found at {MODEL_DIR}")
        print("        Run train_from_new_data.py first.")
        sys.exit(1)

    # ── 1. Load model & tokenizer ───────────────────────────────────────────────
    print("\n[1/4] Loading model and tokenizer...")
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model.eval()
    print(f"      Parameters: {sum(p.numel() for p in model.parameters()):,}")

    id2label = _normalize_id2label(model.config.id2label)
    if not id2label and model.config.label2id:
        id2label = {int(label_id): label for label, label_id in model.config.label2id.items()}
    if not id2label:
        raise ValueError("Model config does not contain id2label/label2id mapping")

    label2id = {label: label_id for label_id, label in id2label.items()}
    labels = [id2label[label_id] for label_id in sorted(id2label.keys())]
    print(f"      Labels: {len(labels)}")

    # ── 2. Export state dict (.pt) ──────────────────────────────────────────────
    print("\n[2/4] Exporting state dict → pytorch_model.pt ...")
    pt_path = EXPORT_DIR / "pytorch_model.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "model_config": model.config.to_dict(),
        "label2id": label2id,
        "id2label": id2label,
        "num_labels": len(labels),
    }, pt_path)
    size_mb = pt_path.stat().st_size / 1024 / 1024
    print(f"      Saved: {pt_path}  ({size_mb:.1f} MB)")

    # ── 3. Export tokenizer (.pkl) ──────────────────────────────────────────────
    print("\n[3/4] Exporting tokenizer → tokenizer.pkl ...")
    pkl_path = EXPORT_DIR / "tokenizer.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(tokenizer, f)
    size_kb = pkl_path.stat().st_size / 1024
    print(f"      Saved: {pkl_path}  ({size_kb:.1f} KB)")

    # ── 4. Export label map + metadata ─────────────────────────────────────────
    print("\n[4/4] Exporting label_map.json + model_info.json ...")

    with open(EXPORT_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f, indent=2, ensure_ascii=False)

    with open(EXPORT_DIR / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({
            "base_model": "vinai/phobert-base",
            "task": "token-classification",
            "language": "vi",
            "entity_types": list(set(label.split("-")[1] for label in labels if "-" in label)),
            "num_labels": len(labels),
            "labels": labels,
            "frozen_layers": "8/12",
            "source_model_dir": str(MODEL_DIR),
        }, f, indent=2, ensure_ascii=False)

    # ── Summary ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    for f in sorted(EXPORT_DIR.iterdir()):
        size = f.stat().st_size
        unit = "MB" if size > 1_000_000 else "KB"
        val  = size / 1_000_000 if size > 1_000_000 else size / 1024
        print(f"  {f.name:<30} {val:>7.1f} {unit}")
    print(f"\nOutput dir: {EXPORT_DIR.resolve()}")


if __name__ == "__main__":
    export()
