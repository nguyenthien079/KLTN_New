"""
Label all .txt files in backend/data/domain/<domain> using MedicalNERPipeline.

Output format (.pipe):
    <filename>.txt||<ENTITY_TYPE>||<start>||<end>

Usage:
    python scripts/label_domain_txt.py --list
    python scripts/label_domain_txt.py <domain>

Example:
    python scripts/label_domain_txt.py bachmai.hanoi.gov.vn
"""

import argparse
import sys
from pathlib import Path

# Make project root importable when running from backend/scripts
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.ensemble import MedicalNERPipeline


def list_domains(domain_root: Path) -> list[str]:
    if not domain_root.exists():
        return []
    return sorted([p.name for p in domain_root.iterdir() if p.is_dir()])


def write_pipe_file(txt_path: Path, lines: list[str]) -> Path:
    pipe_path = txt_path.with_suffix(".pipe")
    with pipe_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")
    return pipe_path


def label_domain(domain: str, domain_root: Path, min_confidence: float) -> None:
    domain_path = domain_root / domain
    if not domain_path.exists() or not domain_path.is_dir():
        print(f"Domain folder not found: {domain_path}")
        sys.exit(1)

    txt_files = sorted(domain_path.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in: {domain_path}")
        sys.exit(1)

    print(f"Loading NER pipeline (min_confidence={min_confidence})...")
    pipeline = MedicalNERPipeline(min_confidence=min_confidence)

    print(f"\nLabeling domain: {domain}")
    print(f"Found {len(txt_files)} text file(s) in {domain_path}\n")

    total_entities = 0
    for idx, txt_path in enumerate(txt_files, start=1):
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        entities = pipeline.extract(text)

        # Stable ordering in output file
        entities = sorted(entities, key=lambda e: (e.start, e.end, e.entity_type))

        lines = [
            f"{txt_path.name}||{e.entity_type}||{e.start}||{e.end}"
            for e in entities
        ]

        pipe_path = write_pipe_file(txt_path, lines)
        total_entities += len(entities)

        print(
            f"[{idx}/{len(txt_files)}] {txt_path.name} -> {pipe_path.name} "
            f"({len(entities)} entities)"
        )

    print("\nDone.")
    print(f"Total files labeled: {len(txt_files)}")
    print(f"Total entities: {total_entities}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Label all .txt files in a selected domain folder"
    )
    parser.add_argument(
        "domain",
        nargs="?",
        help="Domain folder name inside backend/data/domain (e.g. bachmai.hanoi.gov.vn)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available domain folders",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Minimum confidence threshold for ensemble output (default: 0.5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    domain_root = PROJECT_ROOT / "data" / "domain"

    if args.list:
        domains = list_domains(domain_root)
        if not domains:
            print(f"No domain folders found in: {domain_root}")
            return
        print("Available domains:")
        for domain in domains:
            txt_count = len(list((domain_root / domain).glob("*.txt")))
            print(f"  {domain} ({txt_count} txt)")
        return

    if not args.domain:
        print("Usage:")
        print("  python scripts/label_domain_txt.py --list")
        print("  python scripts/label_domain_txt.py <domain>")
        sys.exit(1)

    label_domain(args.domain, domain_root, args.min_confidence)


if __name__ == "__main__":
    main()
