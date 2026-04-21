import argparse
import json
import os
import sys
from collections import defaultdict

import torch
from seqeval.metrics import f1_score, precision_score, recall_score
from transformers import AutoModelForTokenClassification, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAX_LENGTH = 256


def _normalize_id2label(raw_id2label) -> dict:
    id2label = {}
    for key, value in raw_id2label.items():
        id2label[int(key)] = value
    return id2label


def predict(model, tokenizer, tokens: list, device, id2label: dict) -> list:
    encoding = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
        padding=False,
    )
    input_ids = encoding["input_ids"]

    word_ids = [None]
    for word_idx, word in enumerate(tokens):
        subwords = tokenizer.tokenize(word) or [tokenizer.unk_token]
        word_ids.extend([word_idx] * len(subwords))
    word_ids.append(None)

    word_ids = word_ids[:input_ids.shape[1]]
    while len(word_ids) < input_ids.shape[1]:
        word_ids.append(None)

    encoding = {key: value.to(device) for key, value in encoding.items()}
    with torch.no_grad():
        logits = model(**encoding).logits

    pred_ids = logits.argmax(dim=-1)[0].cpu().tolist()

    pred_tags = ["O"] * len(tokens)
    seen = set()
    for word_idx, pred_id in zip(word_ids, pred_ids):
        if word_idx is None or word_idx in seen:
            continue
        if word_idx < len(pred_tags):
            pred_tags[word_idx] = id2label.get(pred_id, "O")
            seen.add(word_idx)

    return pred_tags


def evaluate_by_source(model_path: str, test_data_path: str) -> None:
    with open(test_data_path, "r", encoding="utf-8") as file_obj:
        test_data = json.load(file_obj)

    if not test_data:
        raise ValueError(f"Empty test data: {test_data_path}")

    if not all("source" in sample for sample in test_data):
        raise ValueError("Missing 'source' field in test samples")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Test samples: {len(test_data)}")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForTokenClassification.from_pretrained(model_path).to(device)
    model.eval()

    id2label = _normalize_id2label(model.config.id2label)

    grouped_true = defaultdict(list)
    grouped_pred = defaultdict(list)

    for idx, item in enumerate(test_data, start=1):
        pred_tags = predict(model, tokenizer, item["tokens"], device, id2label)
        true_tags = item["tags"]

        pred_tags = pred_tags[:len(true_tags)]
        true_tags = true_tags[:len(pred_tags)]

        source = item["source"] or "unknown"
        grouped_true[source].append(true_tags)
        grouped_pred[source].append(pred_tags)

        if idx % 100 == 0:
            print(f"  Evaluated {idx}/{len(test_data)}...")

    overall_true = []
    overall_pred = []
    rows = []

    for source in sorted(grouped_true.keys()):
        true_labels = grouped_true[source]
        pred_labels = grouped_pred[source]
        overall_true.extend(true_labels)
        overall_pred.extend(pred_labels)

        rows.append(
            (
                source,
                len(true_labels),
                precision_score(true_labels, pred_labels),
                recall_score(true_labels, pred_labels),
                f1_score(true_labels, pred_labels),
            )
        )

    print("\n" + "=" * 90)
    print(f"{'Source':35} {'Samples':>8} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("=" * 90)
    for source, sample_count, precision, recall, f1 in sorted(rows, key=lambda row: row[0]):
        print(f"{source:35} {sample_count:8d} {precision:10.4f} {recall:10.4f} {f1:10.4f}")
    print("=" * 90)
    print(
        f"{'OVERALL':35} {len(overall_true):8d} "
        f"{precision_score(overall_true, overall_pred):10.4f} "
        f"{recall_score(overall_true, overall_pred):10.4f} "
        f"{f1_score(overall_true, overall_pred):10.4f}"
    )
    print("=" * 90)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate token-classification model grouped by source slug")
    parser.add_argument(
        "--model-path",
        type=str,
        default="models/phobert-medical/final_model",
        help="Path to trained model directory",
    )
    parser.add_argument(
        "--test-data",
        type=str,
        default="data/training/test.json",
        help="Path to test JSON data",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_by_source(model_path=args.model_path, test_data_path=args.test_data)
