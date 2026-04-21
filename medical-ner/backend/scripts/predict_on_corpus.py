"""
predict_on_corpus.py

Run the trained PhoBERT NER model on Corpus_Redone/*.txt files and output
predicted annotations in the same format as new/data/*.json, ready for
human review / labeling UI import.

Outputs (--output-dir):
  <slug>.json      one per file — format matches new/data
  _priority.json   sorted list: unlabeled-first, rare-entity-first
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer
from underthesea import sent_tokenize, word_tokenize

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

RARE_LABELS = {"DATE", "DRUG", "VALUE", "TEST", "TREATMENT"}
CONFIDENCE_THRESHOLD = 0.70
MAX_LENGTH = 256
STAMP_PATTERN = re.compile(r"^(?P<slug>.+?)_\d{8}_\d{6}$")


def _get_slug(stem: str) -> str:
    m = STAMP_PATTERN.match(stem)
    return m.group("slug") if m else stem


def _load_labeled_slugs(labeled_dir: Path) -> set:
    return {_get_slug(p.stem) for p in labeled_dir.glob("*.json")}


def _tokens_to_char_offsets(text: str, tokens: List[str]) -> List[Tuple[int, int]]:
    offsets: List[Tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = text.find(token, cursor)
        if start == -1:
            start = max(0, cursor)
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def _extract_entities(
    tokens: List[str],
    tags: List[str],
    token_offsets: List[Tuple[int, int]],
    word_probs: List[List[float]],
    label_names: List[str],
    sentence_text: str,
    sentence_offset: int,
) -> List[Dict]:
    entities: List[Dict] = []
    i = 0
    while i < len(tags):
        tag = tags[i]
        if not tag.startswith("B-"):
            i += 1
            continue

        label = tag[2:]
        span_end = i
        b_label_id = label_names.index(tag)
        conf_values = [word_probs[i][b_label_id]]

        i_tag = f"I-{label}"
        while span_end + 1 < len(tags) and tags[span_end + 1] == i_tag:
            span_end += 1
            i_label_id = label_names.index(i_tag)
            conf_values.append(word_probs[span_end][i_label_id])

        char_start = token_offsets[i][0] + sentence_offset
        char_end = token_offsets[span_end][1] + sentence_offset
        entity_text = sentence_text[token_offsets[i][0]:token_offsets[span_end][1]]

        entities.append({
            "text": entity_text,
            "label": label,
            "start": char_start,
            "end": char_end,
            "confidence": sum(conf_values) / len(conf_values),
        })
        i = span_end + 1

    return entities


def _predict_article(
    text: str,
    model: AutoModelForTokenClassification,
    tokenizer: AutoTokenizer,
    label_names: List[str],
    device: torch.device,
) -> List[Dict]:
    all_entities: List[Dict] = []
    cursor = 0
    num_labels = len(label_names)
    uniform = [1.0 / num_labels] * num_labels

    for sentence in sent_tokenize(text):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue

        sentence_start = text.find(sentence_text, cursor)
        if sentence_start == -1:
            sentence_start = text.find(sentence_text)
        if sentence_start == -1:
            continue
        cursor = sentence_start + len(sentence_text)

        raw_tokens = word_tokenize(sentence_text)
        tokens = [t.replace("_", " ") for t in raw_tokens]
        if not tokens:
            continue

        encoding = tokenizer(
            tokens,
            is_split_into_words=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
            padding=False,
        )
        input_ids = encoding["input_ids"]

        # Build word_ids manually — PhoBERT uses a slow tokenizer
        word_ids: List[Optional[int]] = [None]  # CLS
        for word_idx, word in enumerate(tokens):
            subwords = tokenizer.tokenize(word) or [tokenizer.unk_token]
            word_ids.extend([word_idx] * len(subwords))
        word_ids.append(None)  # SEP
        word_ids = word_ids[: input_ids.shape[1]]
        while len(word_ids) < input_ids.shape[1]:
            word_ids.append(None)

        encoding = {k: v.to(device) for k, v in encoding.items()}
        with torch.no_grad():
            logits = model(**encoding).logits  # (1, seq_len, num_labels)

        # Softmax probabilities per subword position
        seq_probs: List[List[float]] = torch.softmax(logits, dim=-1)[0].cpu().tolist()

        # First subword wins for each word
        word_probs: List[Optional[List[float]]] = [None] * len(tokens)
        seen: set = set()
        for pos, w_idx in enumerate(word_ids):
            if w_idx is None or w_idx in seen or w_idx >= len(tokens):
                continue
            word_probs[w_idx] = seq_probs[pos]
            seen.add(w_idx)
        word_probs_clean = [p if p is not None else uniform for p in word_probs]

        pred_tags = [
            label_names[max(range(num_labels), key=lambda j, p=p: p[j])]
            for p in word_probs_clean
        ]
        token_offsets = _tokens_to_char_offsets(sentence_text, tokens)

        entities = _extract_entities(
            tokens=tokens,
            tags=pred_tags,
            token_offsets=token_offsets,
            word_probs=word_probs_clean,
            label_names=label_names,
            sentence_text=sentence_text,
            sentence_offset=sentence_start,
        )
        all_entities.extend(entities)

    return all_entities


def _priority_stats(entities: List[Dict]) -> Dict:
    rare_count = sum(1 for e in entities if e["label"] in RARE_LABELS)
    low_conf_count = sum(1 for e in entities if e["confidence"] < CONFIDENCE_THRESHOLD)
    return {
        "entity_count": len(entities),
        "rare_entity_count": rare_count,
        "low_conf_count": low_conf_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict NER on raw Corpus_Redone files → annotation candidates"
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("../../new/Corpus_Redone"),
        help="Directory of raw .txt files",
    )
    parser.add_argument(
        "--labeled-dir",
        type=Path,
        default=Path("../../new/data"),
        help="Directory of already-labeled .json files (flags overlap)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("models/phobert-medical/final_model"),
        help="Trained model directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../../new/predictions"),
        help="Output directory for predicted JSON files",
    )
    parser.add_argument(
        "--skip-labeled",
        action="store_true",
        help="Skip files that already have gold labels in --labeled-dir",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N files (0 = all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_path))
    model = AutoModelForTokenClassification.from_pretrained(str(args.model_path)).to(device)
    model.eval()

    id2label = {int(k): v for k, v in model.config.id2label.items()}
    label_names = [id2label[i] for i in range(len(id2label))]
    print(f"Labels ({len(label_names)}): {label_names}\n")

    labeled_slugs = _load_labeled_slugs(args.labeled_dir)
    corpus_files = sorted(args.corpus_dir.glob("*.txt"))
    if args.limit:
        corpus_files = corpus_files[: args.limit]

    priority_list: List[Dict] = []
    processed = 0
    skipped = 0
    total = len(corpus_files)

    for txt_path in corpus_files:
        slug = txt_path.stem
        has_gold = slug in labeled_slugs

        if args.skip_labeled and has_gold:
            skipped += 1
            continue

        out_path = args.output_dir / f"{slug}.json"

        # Resume: load existing output for priority list
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            stats = _priority_stats(existing.get("entities", []))
            priority_list.append({"slug": slug, "has_gold": has_gold, **stats})
            continue

        text = txt_path.read_text(encoding="utf-8")
        entities = _predict_article(text, model, tokenizer, label_names, device)
        stats = _priority_stats(entities)

        out_obj = {
            "filename": txt_path.name,
            "text": text,
            "entities": entities,
            "predicted": True,
            "has_gold": has_gold,
            **stats,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)

        priority_list.append({"slug": slug, "has_gold": has_gold, **stats})
        processed += 1
        if processed % 25 == 0:
            print(f"  {processed}/{total - skipped} processed...")

    # Sort: unlabeled first, then rare entity count descending
    priority_list.sort(key=lambda x: (x["has_gold"], -x["rare_entity_count"], -x["low_conf_count"]))
    priority_path = args.output_dir / "_priority.json"
    with open(priority_path, "w", encoding="utf-8") as f:
        json.dump(priority_list, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Processed: {processed}, Skipped (already labeled): {skipped}")
    print(f"Priority list → {priority_path}")
    print(f"Output → {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
