#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
op-yargitay-dict-2005: 2005 Yargıtay karar korpusu için CPU tabanlı frekans /
co-occurrence sözlüğü çıkarımı.

Özellikler:
- Giriş: NDJSON / JSONL / JSON (liste) / CSV (default utf-8) dosyaları veya bu
  dosyaları içeren bir klasör.
- Çıktı: data/keyword_hints.json, data/typo_map.json, data/stop_terms.json
  (varsayılan çıkış klasörü değiştirilebilir).
- GPU kullanılmaz; sadece standart kütüphaneler.

Not: Giriş şemasını bilmiyorsanız, en azından aşağıdaki alanlardan birini
bulundurun: ["tam_metin", "icerik", "content", "ozet", "summary", "html"].
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Set


LAW_PATTERN = re.compile(r"\b(?:TCK|CMK|HMK|TMK|BK|TTK|TBK|İİK|İYUK)\s*\d+(?:/\d+)?\b", re.I)
TOKEN_PATTERN = re.compile(r"[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]+", re.UNICODE)

# Suç / usul çekirdek listeleri (yargitay_search.py içindeki setlerin sade hali)
CRIME_SEEDS = {
    "yağma", "nitelikli yağma", "hırsızlık", "dolandırıcılık", "zimmet",
    "irtikap", "rüşvet", "kasten yaralama", "taksirle yaralama",
    "cinsel saldırı", "cinsel istismar", "kasten öldürme", "adam öldürme",
    "tehdit", "hakaret", "şantaj", "güveni kötüye kullanma",
}
PROCEDURE_SEEDS = {
    "takipsizlik", "beraat", "mahkumiyet", "temyiz", "istinaf",
    "bozma", "onanma", "kyok", "yhgk", "duruşma", "delil",
}

# Basit Türkçe stop kelime listesi (genel kelimeler)
STOPWORDS = {
    "ve", "veya", "ile", "de", "da", "bu", "bir", "için", "olarak", "olarak",
    "göre", "olan", "olanlar", "ile", "karar", "mahkeme", "dair", "husus",
    "hakkında", "edilen", "ancak", "fakat", "çünkü", "veya", "ile",
}


def _html_to_text(raw: str) -> str:
    """Basit HTML temizleyici."""
    txt = raw
    txt = re.sub(r"<\s*br\s*/?\s*>", "\n", txt, flags=re.I)
    txt = re.sub(r"</p\s*>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n\s*", "\n", txt)
    return txt.strip()


def ascii_fold(s: str) -> str:
    return (
        s.replace("ş", "s").replace("Ş", "S")
        .replace("ç", "c").replace("Ç", "C")
        .replace("ğ", "g").replace("Ğ", "G")
        .replace("ı", "i").replace("İ", "i")
        .replace("ö", "o").replace("Ö", "O")
        .replace("ü", "u").replace("Ü", "U")
    )


def tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in TOKEN_PATTERN.finditer(text)]


def extract_articles(text: str) -> List[str]:
    articles: List[str] = []
    for m in LAW_PATTERN.finditer(text):
        art = m.group(0).strip()
        if art not in articles:
            articles.append(art)
    return articles


def iter_texts(path: Path) -> Iterable[str]:
    """Path dosya ise onu, klasör ise içindeki .ndjson/.json/.jsonl/.csv dosyalarını okur."""
    files: List[Path] = []
    if path.is_file():
        files = [path]
    else:
        for ext in ("*.ndjson", "*.jsonl", "*.json", "*.csv"):
            files.extend(path.rglob(ext))

    for file in files:
        suffix = file.suffix.lower()
        if suffix in {".ndjson", ".jsonl"}:
            with file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        txt = _extract_text_from_obj(obj)
                        if txt:
                            yield txt
                    except Exception:
                        continue
        elif suffix == ".json":
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                for obj in data:
                    if not isinstance(obj, dict):
                        continue
                    txt = _extract_text_from_obj(obj)
                    if txt:
                        yield txt
        elif suffix == ".csv":
            with file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    txt = _extract_text_from_obj(row)
                    if txt:
                        yield txt


def _extract_text_from_obj(obj: Dict) -> str:
    candidates = [
        obj.get("tam_metin"), obj.get("icerik"), obj.get("content"),
        obj.get("html"), obj.get("ozet"), obj.get("summary"),
    ]
    for cand in candidates:
        if isinstance(cand, str) and cand.strip():
            return _html_to_text(cand)
    return ""


def build_stats(texts: Iterable[str], top_n: int = 20) -> Tuple[Dict[str, List[Tuple[str, int]]],
                                                                 Dict[str, List[Tuple[str, int]]],
                                                                 Dict[str, int]]:
    article_co: Dict[str, Counter] = defaultdict(Counter)
    crime_co: Dict[str, Counter] = defaultdict(Counter)
    procedure_co: Dict[str, Counter] = defaultdict(Counter)
    token_freq: Counter = Counter()
    typo_candidates: Counter = Counter()

    for txt in texts:
        tokens = tokenize(txt)
        if not tokens:
            continue
        token_freq.update(tokens)

        articles = extract_articles(txt)
        if articles:
            for art in articles:
                article_co[art].update(tokens)

        for c in CRIME_SEEDS:
            if c in txt.lower():
                crime_co[c].update(tokens)

        for p in PROCEDURE_SEEDS:
            if p in txt.lower():
                procedure_co[p].update(tokens)

        for t in tokens:
            folded = ascii_fold(t)
            if folded != t:
                typo_candidates[folded] += 1

    article_top = {art: _top_filtered(counter, top_n) for art, counter in article_co.items()}
    crime_top = {c: _top_filtered(counter, top_n) for c, counter in crime_co.items()}
    procedure_top = {p: _top_filtered(counter, top_n) for p, counter in procedure_co.items()}

    typo_map = _build_typo_map(token_freq, min_freq=5)
    stop_terms = _build_stop_terms(token_freq, top_k=100)

    hints = {
        "articles": article_top,
        "crimes": crime_top,
        "procedures": procedure_top,
    }
    return hints, typo_map, stop_terms


def _top_filtered(counter: Counter, top_n: int) -> List[Tuple[str, int]]:
    items: List[Tuple[str, int]] = []
    for token, freq in counter.most_common():
        if token in STOPWORDS:
            continue
        if len(token) < 3:
            continue
        items.append((token, freq))
        if len(items) >= top_n:
            break
    return items


def _build_typo_map(token_freq: Counter, min_freq: int = 5) -> Dict[str, str]:
    folded_groups: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for token, freq in token_freq.items():
        if freq < min_freq:
            continue
        folded = ascii_fold(token)
        folded_groups[folded].append((token, freq))

    typo_map: Dict[str, str] = {}
    for folded, variants in folded_groups.items():
        if len(variants) <= 1:
            continue
        # En sık görüleni kanonik kabul et
        variants.sort(key=lambda x: x[1], reverse=True)
        canonical = variants[0][0]
        for variant, _ in variants[1:]:
            if variant != canonical:
                typo_map[variant] = canonical
    return typo_map


def _build_stop_terms(token_freq: Counter, top_k: int = 100) -> Dict[str, int]:
    # Çok sık geçen genel kelimelerden stop listesi çıkar
    stop: Dict[str, int] = {}
    for token, freq in token_freq.most_common(top_k):
        stop[token] = freq
    return stop


def main() -> None:
    parser = argparse.ArgumentParser(description="Yargıtay 2005 sözlük çıkarımı (CPU).")
    parser.add_argument("--input", required=True, help="Girdi dosyası veya klasörü (ndjson/json/jsonl/csv).")
    parser.add_argument("--output-dir", default="data", help="Çıktı klasörü (varsayılan: data)")
    parser.add_argument("--top-n", type=int, default=20, help="Her madde/suç/usul için tutulacak en fazla kavram sayısı.")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    texts = list(iter_texts(input_path))
    hints, typo_map, stop_terms = build_stats(texts, top_n=args.top_n)

    (out_dir / "keyword_hints.json").write_text(json.dumps(hints, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "typo_map.json").write_text(json.dumps(typo_map, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "stop_terms.json").write_text(json.dumps(stop_terms, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Toplam doküman: {len(texts)}")
    print(f"Çıktılar: {out_dir / 'keyword_hints.json'}, {out_dir / 'typo_map.json'}, {out_dir / 'stop_terms.json'}")


if __name__ == "__main__":
    main()
