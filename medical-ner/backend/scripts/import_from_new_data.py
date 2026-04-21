import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from underthesea import sent_tokenize, word_tokenize

TIMESTAMPED_FILE_PATTERN = re.compile(r"^(?P<slug>.+?)_(?P<stamp>\d{8}_\d{6})$")

LABEL_MAP: Dict[str, Optional[str]] = {
    "DISEASE": "DISEASE",
    "SYMPTOM": "SYMPTOM",
    "BODY_PART": "BODY_PART",
    "TREATMENT": "TREATMENT",
    "TEST": "TEST",
    "MEDICATION": "DRUG",
    "SUBSTANCE": "DRUG",
    "VALUE": "VALUE",
    "DATE": "DATE",
    "DOCTOR": None,
    "PATIENT": None,
    "LOCATION": None,
    "Không có": None,
    "Không có thực thể y tế cụ thể, bỏ qua": None,
}


def _extract_slug_and_stamp(path: Path) -> Tuple[str, str]:
    match = TIMESTAMPED_FILE_PATTERN.match(path.stem)
    if match:
        return match.group("slug"), match.group("stamp")
    return path.stem, ""


def select_latest_files(data_dir: Path) -> Dict[str, Path]:
    selected: Dict[str, Tuple[str, Path]] = {}
    for file_path in sorted(data_dir.glob("*.json")):
        slug, stamp = _extract_slug_and_stamp(file_path)
        if slug not in selected:
            selected[slug] = (stamp, file_path)
            continue

        current_stamp, _ = selected[slug]
        if stamp and (not current_stamp or stamp > current_stamp):
            selected[slug] = (stamp, file_path)

    return {slug: info[1] for slug, info in selected.items()}


def char_to_token_indices(
    text: str,
    tokens: List[str],
    start_char: int,
    end_char: int,
) -> Tuple[Optional[int], Optional[int]]:
    current_pos = 0
    start_token = None
    end_token = None

    for idx, token in enumerate(tokens):
        token_start = text.find(token, current_pos)
        if token_start == -1:
            continue

        token_end = token_start + len(token)
        if start_token is None and token_start <= start_char < token_end:
            start_token = idx
        if token_start < end_char <= token_end:
            end_token = idx

        if start_token is not None and end_token is not None:
            break

        current_pos = token_end

    return start_token, end_token


def span_to_bio(
    text: str,
    entities: List[Dict],
    label_map: Dict[str, Optional[str]],
) -> Tuple[List[str], List[str]]:
    raw_tokens = word_tokenize(text)
    tokens = [token.replace("_", " ") for token in raw_tokens]
    tags = ["O"] * len(tokens)

    valid_entities = [entity for entity in entities if label_map.get(entity["label"]) is not None]
    valid_entities.sort(key=lambda entity: entity["end"] - entity["start"], reverse=True)

    for entity in valid_entities:
        mapped_label = label_map[entity["label"]]
        start_token, end_token = char_to_token_indices(
            text=text,
            tokens=tokens,
            start_char=entity["start"],
            end_char=entity["end"],
        )
        if start_token is None or end_token is None:
            continue
        if end_token < start_token:
            continue

        if any(tags[token_idx] != "O" for token_idx in range(start_token, end_token + 1)):
            continue

        tags[start_token] = f"B-{mapped_label}"
        for token_idx in range(start_token + 1, end_token + 1):
            tags[token_idx] = f"I-{mapped_label}"

    return tokens, tags


def _build_sentence_ranges(text: str) -> List[Tuple[int, int, str]]:
    ranges: List[Tuple[int, int, str]] = []
    cursor = 0

    for sentence in sent_tokenize(text):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue

        start = text.find(sentence_text, cursor)
        if start == -1:
            start = text.find(sentence_text)
        if start == -1:
            continue

        end = start + len(sentence_text)
        ranges.append((start, end, sentence_text))
        cursor = end

    return ranges


def split_article_to_samples(
    text: str,
    entities: List[Dict],
    source: str,
    label_map: Dict[str, Optional[str]],
) -> List[Dict]:
    samples: List[Dict] = []
    sentence_ranges = _build_sentence_ranges(text)

    for sentence_start, sentence_end, sentence_text in sentence_ranges:
        sentence_entities: List[Dict] = []
        for entity in entities:
            start_char = entity.get("start")
            end_char = entity.get("end")
            if not isinstance(start_char, int) or not isinstance(end_char, int):
                continue
            if sentence_start <= start_char and end_char <= sentence_end:
                sentence_entities.append(
                    {
                        "text": entity.get("text", ""),
                        "label": entity.get("label", ""),
                        "start": start_char - sentence_start,
                        "end": end_char - sentence_start,
                    }
                )

        tokens, tags = span_to_bio(sentence_text, sentence_entities, label_map)
        if not tokens:
            continue
        if all(tag == "O" for tag in tags):
            continue

        samples.append(
            {
                "source": source,
                "text": sentence_text,
                "tokens": tokens,
                "tags": tags,
            }
        )

    return samples


def split_slugs(slugs: List[str], seed: int) -> Tuple[set, set, set]:
    shuffled_slugs = list(slugs)
    random.Random(seed).shuffle(shuffled_slugs)
    slug_count = len(shuffled_slugs)

    if slug_count == 0:
        return set(), set(), set()
    if slug_count == 1:
        return {shuffled_slugs[0]}, set(), set()
    if slug_count == 2:
        return {shuffled_slugs[0]}, {shuffled_slugs[1]}, set()

    train_end = max(1, int(slug_count * 0.8))
    val_end = max(train_end + 1, int(slug_count * 0.9))
    val_end = min(val_end, slug_count - 1)

    train_slugs = set(shuffled_slugs[:train_end])
    val_slugs = set(shuffled_slugs[train_end:val_end])
    test_slugs = set(shuffled_slugs[val_end:])
    return train_slugs, val_slugs, test_slugs


def convert_new_data(
    data_dir: Path,
    output_dir: Path,
    seed: int = 42,
) -> Dict:
    selected_files = select_latest_files(data_dir)
    if not selected_files:
        raise ValueError(f"No JSON files found in {data_dir}")

    samples_by_slug: Dict[str, List[Dict]] = defaultdict(list)
    unknown_labels = Counter()
    dropped_labels = Counter()
    sentence_sample_count = 0

    for slug, file_path in sorted(selected_files.items()):
        with open(file_path, "r", encoding="utf-8") as file_obj:
            article = json.load(file_obj)

        text = article.get("text", "")
        if not text or not text.strip():
            continue

        entities = article.get("entities", [])
        for entity in entities:
            label = entity.get("label", "")
            if label not in LABEL_MAP:
                unknown_labels[label] += 1
            elif LABEL_MAP[label] is None:
                dropped_labels[label] += 1

        article_samples = split_article_to_samples(
            text=text,
            entities=entities,
            source=slug,
            label_map=LABEL_MAP,
        )
        sentence_sample_count += len(article_samples)
        samples_by_slug[slug].extend(article_samples)

    train_slugs, val_slugs, test_slugs = split_slugs(list(samples_by_slug.keys()), seed=seed)

    train_data: List[Dict] = []
    val_data: List[Dict] = []
    test_data: List[Dict] = []

    for slug, samples in samples_by_slug.items():
        if slug in train_slugs:
            train_data.extend(samples)
        elif slug in val_slugs:
            val_data.extend(samples)
        elif slug in test_slugs:
            test_data.extend(samples)

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "train.json", "w", encoding="utf-8") as file_obj:
        json.dump(train_data, file_obj, ensure_ascii=False, indent=2)
    with open(output_dir / "val.json", "w", encoding="utf-8") as file_obj:
        json.dump(val_data, file_obj, ensure_ascii=False, indent=2)
    with open(output_dir / "test.json", "w", encoding="utf-8") as file_obj:
        json.dump(test_data, file_obj, ensure_ascii=False, indent=2)

    label_distribution = Counter()
    for sample in train_data + val_data + test_data:
        label_distribution.update(sample["tags"])

    stats = {
        "selected_file_count": len(selected_files),
        "slug_count": len(samples_by_slug),
        "sentence_sample_count": sentence_sample_count,
        "train_samples": len(train_data),
        "val_samples": len(val_data),
        "test_samples": len(test_data),
        "train_slugs": len(train_slugs),
        "val_slugs": len(val_slugs),
        "test_slugs": len(test_slugs),
        "unknown_labels": dict(unknown_labels),
        "dropped_labels": dict(dropped_labels),
        "label_distribution": dict(label_distribution),
    }
    return stats


def _print_stats(stats: Dict, output_dir: Path) -> None:
    print("=" * 70)
    print("Imported new labeled data")
    print("=" * 70)
    print(f"Selected files (after dedup): {stats['selected_file_count']}")
    print(f"Unique disease slugs:          {stats['slug_count']}")
    print(f"Sentence samples:              {stats['sentence_sample_count']}")
    print(f"Train / Val / Test samples:    {stats['train_samples']} / {stats['val_samples']} / {stats['test_samples']}")
    print(f"Train / Val / Test slugs:      {stats['train_slugs']} / {stats['val_slugs']} / {stats['test_slugs']}")
    print(f"Output directory:              {output_dir.resolve()}")

    if stats["unknown_labels"]:
        print("\nUnknown labels in source data:")
        for label, count in sorted(stats["unknown_labels"].items(), key=lambda item: item[0]):
            print(f"  - {label}: {count}")

    if stats["dropped_labels"]:
        print("\nDropped labels (mapped to None):")
        for label, count in sorted(stats["dropped_labels"].items(), key=lambda item: item[0]):
            print(f"  - {label}: {count}")

    print("\nLabel distribution (top 20):")
    distribution = Counter(stats["label_distribution"])
    for label, count in distribution.most_common(20):
        print(f"  - {label}: {count}")
    print("=" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert new labeled JSON data to training split files")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("../../new/data"),
        help="Directory containing *.json labeled files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/training"),
        help="Output directory for train/val/test JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for slug split",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = convert_new_data(data_dir=args.data_dir, output_dir=args.output_dir, seed=args.seed)
    _print_stats(stats, args.output_dir)


if __name__ == "__main__":
    main()
