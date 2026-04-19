"""Quick smoke test — run: python -m app.ner.test_pipeline (from backend/)"""
from app.ner.pipeline import run

TEXT = (
    "Bệnh nhân nam, 45 tuổi, được chẩn đoán tăng huyết áp và đái tháo đường. "
    "Huyết áp: 140/90 mmHg. Glucose = 8.5 mmol/L. "
    "Đang dùng metformin 500mg, 2 viên/ngày. "
    "Bác sĩ chỉ định siêu âm bụng và xét nghiệm máu."
)

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    results = run(TEXT)
    print(f"Found {len(results)} entities:\n")
    for span in results:
        print(f"  [{span['label']:12s}] {span['text']!r:35s} ({span['start']}:{span['end']}) source={span['source']}")
