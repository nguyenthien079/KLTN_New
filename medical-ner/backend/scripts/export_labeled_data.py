"""
Export labeled annotations from database to CSV.

Usage:
    # Export all labeled files
    python scripts/export_labeled_data.py

    # Export specific file
    python scripts/export_labeled_data.py --filename yeu-sinh-ly-o-nu.txt

    # Export to specific output file
    python scripts/export_labeled_data.py --output labeled_data.csv

    # Export specific file to specific output
    python scripts/export_labeled_data.py --filename yeu-sinh-ly-o-nu.txt --output yeu-sinh-ly-o-nu.csv

Format:
    filename,text,label,start,end
    yeu-sinh-ly-o-nu.txt,nữ,BODY_PART,109,111
    yeu-sinh-ly-o-nu.txt,yếu sinh lý,DISEASE,236,247
"""

import argparse
import asyncio
import csv
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models.label_submission import LabelSubmission
from app.models.label_annotation import LabelAnnotation
from app.models.article import Article


class AnnotationExporter:
    """Export labeled annotations to CSV"""

    def __init__(self):
        self.rows: List[Dict] = []

    async def load_annotations(self, filename: Optional[str] = None) -> None:
        """
        Load annotations from database.
        
        Args:
            filename: Optional filename to filter by. If None, load all.
        """
        async with AsyncSessionLocal() as db:
            # Query with eager loading of article and annotations
            query = select(LabelSubmission).options(
                selectinload(LabelSubmission.article),
                selectinload(LabelSubmission.annotations)
            )

            result = await db.execute(query)
            submissions = result.scalars().all()

            for submission in submissions:
                # Get filename from article
                filename_value = self._get_filename_from_article(submission.article)

                # Skip if filtering by filename
                if filename and filename_value != filename:
                    continue

                # Export each annotation
                for annotation in submission.annotations:
                    row = {
                        'filename': filename_value,
                        'text': annotation.surface_text or '',
                        'label': annotation.entity_type,
                        'start': annotation.start_offset,
                        'end': annotation.end_offset,
                    }
                    self.rows.append(row)

    def _get_filename_from_article(self, article) -> str:
        """
        Extract filename from article.
        Use article title as filename.
        
        Args:
            article: Article object
        
        Returns:
            Filename with .txt extension
        """
        if not article:
            return "unknown.txt"

        # Use article title if available
        if article.title:
            # Convert title to filename (sanitize: remove special chars)
            safe_title = "".join(
                c if c.isalnum() or c in ('-', '_', ' ') else '-'
                for c in article.title
            ).strip().replace(' ', '_')
            
            # Remove leading/trailing dashes
            safe_title = safe_title.strip('-').lower()
            
            if safe_title:
                return f"{safe_title}.txt"
        
        # Fallback: use article id
        return f"article_{article.id}.txt"

    def export_to_csv(self, output_file: Optional[str] = None) -> str:
        """
        Export annotations to CSV file.
        
        Args:
            output_file: Output CSV file path. If None, print to stdout.
        
        Returns:
            Path to output file or "stdout"
        """
        if not self.rows:
            print("No annotations found to export.", file=sys.stderr)
            return ""

        # Sort by filename, then by start position
        self.rows.sort(key=lambda x: (x['filename'], x['start']))

        # Prepare output
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = None

        # Write CSV
        fieldnames = ['filename', 'text', 'label', 'start', 'end']

        if output_path:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.rows)
            print(f"✓ Exported {len(self.rows)} annotations to: {output_path}")
            return str(output_path)
        else:
            # Print to stdout
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)
            return "stdout"

    def print_stats(self) -> None:
        """Print export statistics"""
        if not self.rows:
            return

        print("\n" + "="*60)
        print("EXPORT STATISTICS")
        print("="*60)
        print(f"Total annotations: {len(self.rows)}")

        # Count by filename
        filenames = {}
        for row in self.rows:
            fn = row['filename']
            filenames[fn] = filenames.get(fn, 0) + 1

        print(f"\nFiles: {len(filenames)}")
        for fn in sorted(filenames.keys()):
            print(f"  {fn}: {filenames[fn]} annotations")

        # Count by label
        labels = {}
        for row in self.rows:
            label = row['label']
            labels[label] = labels.get(label, 0) + 1

        print(f"\nEntity types:")
        for label in sorted(labels.keys()):
            print(f"  {label}: {labels[label]}")

        print("="*60 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description='Export labeled annotations from database to CSV'
    )
    parser.add_argument(
        '--filename',
        type=str,
        default=None,
        help='Specific filename to export (e.g., yeu-sinh-ly-o-nu.txt). If omitted, export all.'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV file path. Default: data/csv/labeled_annotations.csv'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics after export'
    )

    args = parser.parse_args()

    exporter = AnnotationExporter()

    # Load annotations
    print("Loading annotations from database...")
    await exporter.load_annotations(filename=args.filename)

    if not exporter.rows:
        print("No annotations found.", file=sys.stderr)
        sys.exit(1)

    # Print stats if requested
    if args.stats:
        exporter.print_stats()

    # Determine output path
    output_path = args.output
    if not output_path:
        # Default output to data/csv/ folder
        csv_dir = Path(__file__).parent.parent / "data" / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename based on export type
        if args.filename:
            # If exporting specific file, use its name
            base_name = Path(args.filename).stem
            output_path = csv_dir / f"{base_name}.csv"
        else:
            # If exporting all, use timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = csv_dir / f"labeled_annotations_{timestamp}.csv"

    # Export to CSV
    exporter.export_to_csv(output_file=output_path)


if __name__ == "__main__":
    asyncio.run(main())
