import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer
from seqeval.metrics import classification_report

MAX_LENGTH = 256


def normalize_id2label(raw_id2label) -> dict:
    return {int(key): value for key, value in raw_id2label.items()}


def predict(model, tokenizer, tokens: list, device, id2label: dict) -> list:
    """Run NER on a token list, return BIO tag list of same length."""
    # Tokenize with word-level alignment
    encoding = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
        padding=False,
    )

    input_ids = encoding["input_ids"]

    # Build manual word_ids (PhoBERT has slow tokenizer)
    word_ids = [None]  # CLS
    for word_idx, word in enumerate(tokens):
        subwords = tokenizer.tokenize(word) or [tokenizer.unk_token]
        word_ids.extend([word_idx] * len(subwords))
    word_ids.append(None)  # SEP
    # Align to actual input_ids length after truncation
    word_ids = word_ids[:input_ids.shape[1]]
    while len(word_ids) < input_ids.shape[1]:
        word_ids.append(None)

    # Inference
    encoding = {k: v.to(device) for k, v in encoding.items()}
    with torch.no_grad():
        logits = model(**encoding).logits  # (1, seq_len, num_labels)

    pred_ids = logits.argmax(dim=-1)[0].cpu().tolist()

    # Map subword predictions back to word-level (first subword wins)
    pred_tags = ['O'] * len(tokens)
    seen = set()
    for pos, (w_idx, p_id) in enumerate(zip(word_ids, pred_ids)):
        if w_idx is None or w_idx in seen:
            continue
        if w_idx < len(pred_tags):
            pred_tags[w_idx] = id2label.get(p_id, 'O')
            seen.add(w_idx)

    return pred_tags


def evaluate(model_path: str, test_data_path: str):
    with open(test_data_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Test samples: {len(test_data)}\n")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForTokenClassification.from_pretrained(model_path).to(device)
    model.eval()
    id2label = normalize_id2label(model.config.id2label)

    true_labels, pred_labels = [], []
    errors = 0

    for i, item in enumerate(test_data):
        try:
            pred_tags = predict(model, tokenizer, item["tokens"], device, id2label)
            true_tags = item["tags"]

            # Truncate true tags to same length if needed
            pred_tags = pred_tags[:len(true_tags)]
            true_tags = true_tags[:len(pred_tags)]

            true_labels.append(true_tags)
            pred_labels.append(pred_tags)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"[SKIP] item {i}: {e}")

        if (i + 1) % 100 == 0:
            print(f"  Evaluated {i+1}/{len(test_data)}...")

    print(f"\nErrors skipped: {errors}")
    print("\n" + "=" * 60)
    print(classification_report(true_labels, pred_labels))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate token-classification model on test split")
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
        help="Path to test split json",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate(model_path=args.model_path, test_data_path=args.test_data)
