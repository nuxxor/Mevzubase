#!/usr/bin/env python
"""
Basit RAG eval script'i:
- tests/legal_eval_set.json içindeki soruları çalıştırır
- Hit/MRR yokluğu durumunda placeholder (retrieval skoru okunacaksa kod genişletilebilir)
- Çıktı: ndjson (sonuçlar), json (özet)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Repo kökünü PYTHONPATH'e ekle
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from yargitay_search import run_llm_pipeline  # type: ignore


def load_eval_set(path: str = "tests/legal_eval_set.json") -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Eval set bulunamadı: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    eval_items = load_eval_set()
    results: List[Dict[str, Any]] = []

    for item in eval_items:
        qid = item.get("id")
        question = item.get("question")
        expected_tags = item.get("expected_tags", [])
        print(f"[{qid}] {question[:80]}...")
        try:
            res = run_llm_pipeline(
                question=question,
                limit=80,
                years_back=15,
                sources=None,
                output_base_dir="tests/docs",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ Hata: {exc}")
            results.append({"id": qid, "question": question, "status": "error", "error": str(exc)})
            continue

        verdict = (res.get("verified_answer") or {}).get("verdict")
        used_cases = res.get("verified_answer", {}).get("cases_used") or []
        used_ids = [c.get("id") for c in used_cases if c.get("id")]

        # Basit metrikler: verdict ve ID sayısı
        results.append(
            {
                "id": qid,
                "question": question,
                "verdict": verdict,
                "cases_used": used_ids,
                "expected_tags": expected_tags,
                "status": "ok",
            }
        )

    out_dir = Path("tests/eval_runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = out_dir / "eval_results.ndjson"
    with ndjson_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary_path = out_dir / "eval_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEval tamamlandı. NDJSON: {ndjson_path} | Özet: {summary_path}")


if __name__ == "__main__":
    main()
