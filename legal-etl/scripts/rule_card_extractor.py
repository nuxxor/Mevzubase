"""
Pilot: Karar metinlerinden otomatik kural kartı çıkarma.

Çalıştırma (örnek):
  python -m scripts.rule_card_extractor --issue "satım/ayıp" --queries "ayıp ihbar süresi ekspertiz" --top-n 5

Not:
- Bu bir prototip iskelet. LLM çağrısı ve karar metni elde etme kısmı basit tutuldu.
- Map prompt: karar -> JSON (issue, facts_key, rule, exceptions, holding, citations, confidence)
- Reduce: şimdilik dedup (rule + issue metni aynıysa).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import os
import sys
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sentence_transformers import SentenceTransformer


MAP_PROMPT = """You are a legal assistant that extracts structured rules from a Turkish court decision.
Return ONLY a valid JSON object with these keys:
  "issue": short label of the legal issue (e.g. "satım/ayıp").
  "facts_key": list of key factors/conditions (e.g. ["ekspertiz", "açık ayıp", "ihbar süresi", "iğfal"]).
  "rule": concise legal rule/principle stated.
  "exceptions": list of exceptions/conditions (if any).
  "holding": outcome/holding in this case (brief).
  "citations": list of important citations (case nos or code articles).
  "confidence": number 0-1 for confidence in this extraction.
If a field is missing, leave it empty but KEEP the key.
Court Decision Text:
\"\"\"
{decision_text}
\"\"\"
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract rule cards (prototype).")
    ap.add_argument("--issue", required=True, help="Issue etiketi (örn. 'satım/ayıp')")
    ap.add_argument("--queries", nargs="+", help="Retrieval için query listesi (örn. 'ayıp ihbar ekspertiz')")
    ap.add_argument("--top-n", type=int, default=5, help="Kaç karar çekilecek")
    ap.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant URL")
    ap.add_argument("--collection", default="yargitay_chunks_local_v1", help="Karar chunk koleksiyonu")
    ap.add_argument("--model", default="BAAI/bge-m3", help="Embedding modeli (retrieval)")
    ap.add_argument("--device", default="cpu", help="cuda/cpu")
    ap.add_argument("--output", default="rule_cards.ndjson", help="Çıktı NDJSON dosyası")
    return ap.parse_args()


def retrieve_chunks(queries: List[str], top_n: int, model_name: str, collection: str, qdrant_url: str, device: str) -> List[Dict[str, Any]]:
    model = SentenceTransformer(model_name, device=device)
    client = QdrantClient(qdrant_url)
    points = []
    try:
        for q in queries:
            qvec = model.encode([q], normalize_embeddings=True)[0].tolist()
            res = client.query_points(collection_name=collection, query=qvec, limit=top_n, with_payload=True, with_vectors=False).points
            points.extend(res)
    except ResponseHandlingException as exc:
        raise SystemExit(f"Qdrant'a bağlanırken hata: {qdrant_url} ({exc}). Servis/URL'i kontrol edin.") from exc
    except UnexpectedResponse as exc:
        raise SystemExit(f"Qdrant hata döndürdü: {exc}. Koleksiyon adı/URL doğru mu?") from exc
    return points[:top_n]


_LLM_PROVIDER_ENV = "RULE_CARD_LLM_PROVIDER"
_LLM_MODEL_ENV = "RULE_CARD_LLM_MODEL"
_LLM_TEMPERATURE_ENV = "RULE_CARD_LLM_TEMPERATURE"


def _load_shared_llm() -> Any:
    """yargitay_search._call_llm fonksiyonunu import eder."""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    try:
        from yargitay_search import _call_llm as shared_call_llm  # type: ignore
    except Exception as exc:  # noqa: BLE001 - prototipte hızlı hata sinyali yeterli
        raise RuntimeError("yargitay_search._call_llm import edilemedi; LLM entegrasyonu gerekiyor.") from exc
    return shared_call_llm


_CALL_LLM = None


def call_llm(prompt: str) -> str:
    """
    Map aşamasında kullanılan ortak LLM kapısı (Ollama/OpenAI).
    Ortam değişkenleri:
      - RULE_CARD_LLM_PROVIDER: 'ollama' veya 'openai'
      - RULE_CARD_LLM_MODEL: seçilecek model adı
      - RULE_CARD_LLM_TEMPERATURE: varsayılan 0.0
    """
    global _CALL_LLM
    if _CALL_LLM is None:
        _CALL_LLM = _load_shared_llm()
    try:
        temperature = float(os.environ.get(_LLM_TEMPERATURE_ENV, "0.0"))
    except ValueError:
        temperature = 0.0
    return _CALL_LLM(
        prompt,
        provider=os.environ.get(_LLM_PROVIDER_ENV),
        model=os.environ.get(_LLM_MODEL_ENV),
        temperature=temperature,
    )


def extract_rule_card(decision_text: str, issue_label: str) -> Dict[str, Any]:
    prompt = MAP_PROMPT.format(decision_text=decision_text[:6000])  # uzun metinleri kısaltmak için
    try:
        raw = call_llm(prompt)
        data = json.loads(raw)
    except Exception:
        # Basit fallback: minimal kart
        data = {
            "issue": issue_label,
            "facts_key": [],
            "rule": "",
            "exceptions": [],
            "holding": "",
            "citations": [],
            "confidence": 0.0,
        }
    # issue boşsa doldur
    if not data.get("issue"):
        data["issue"] = issue_label
    return data


def dedup_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for c in cards:
        key = (c.get("issue", ""), c.get("rule", "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def main() -> None:
    args = parse_args()
    if not args.queries:
        raise SystemExit("En az bir --queries verilmeli (örn. 'ayıp ihbar ekspertiz').")
    chunks = retrieve_chunks(args.queries, args.top_n, args.model, args.collection, args.qdrant_url, args.device)
    cards = []
    for p in chunks:
        payload = p.payload or {}
        text = payload.get("text", "")
        if not text:
            continue
        card = extract_rule_card(text, issue_label=args.issue)
        cards.append(card)

    cards = dedup_cards(cards)
    out_path = Path(args.output)
    with out_path.open("w", encoding="utf-8") as fh:
        for c in cards:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(cards)} kural kartı yazıldı -> {out_path}")


if __name__ == "__main__":
    main()
