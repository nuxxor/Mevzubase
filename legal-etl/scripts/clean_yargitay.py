#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Yargıtay NDJSON temizleme ve opsiyonel chunk'lama aracı.

İşler:
- doc_id bazlı dedup
- Bozuk karakterleri charmap ile düzeltme + whitespace sadeleştirme
- Opsiyonel kısa kayıt filtresi
- Opsiyonel boilerplate kırpma
- İstenirse chunk üretimi (paragraf bazlı, karakter boyutuna göre)
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


# Sık görülen bozuk karakter/sequence düzeltmeleri
REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("Ç¬", "ü"),
    ("Ç¦", "ü"),
    ("Çõ", "ç"),
    ("Ç÷", "ç"),
    ("Çô", "ö"),
    ("Çó", "ö"),
    ("Ç£", "ö"),
    ("ÇÄ", "ı"),
    ("Å", "ç"),
    ("Åz", "ç"),
    ("ƒ?O", "Ş"),
    ("ƒ?Y", "ş"),
    ("Y", "ş"),
    ("?", "ğ"),
    ("Žø", "İ"),
    ("Žñ", "ı"),
    ("Ž", "ı"),
    ("�", ""),  # bilinemeyen karakterleri temizle
)

BOILERPLATE_PATTERNS = (
    re.compile(r"^\[KAYNAK:.*\]$", re.IGNORECASE),
    re.compile(r'^"?(İçtihat Metni)"?$', re.IGNORECASE),
)


def normalize_text(text: str, drop_boilerplate: bool = True) -> str:
    """Bozuk karakterleri düzelt, whitespace'i sadeleştir."""
    if not text:
        return ""

    t = text
    for src, dst in REPLACEMENTS:
        t = t.replace(src, dst)

    # UTF-8 NBSP vb.
    t = t.replace("\u00a0", " ")

    lines: List[str] = []
    for line in t.splitlines():
        line = re.sub(r"[ \t]+", " ", line.strip())
        if drop_boilerplate and any(p.match(line) for p in BOILERPLATE_PATTERNS):
            continue
        lines.append(line)

    t = "\n".join(lines)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def chunk_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """Paragraf bazlı chunk'lama."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for para in paras:
        plen = len(para) + 2  # \n\n hesabı
        if cur and cur_len + plen > max_chars:
            chunks.append("\n\n".join(cur))
            if overlap_chars > 0:
                tail: List[str] = []
                tail_len = 0
                for p in reversed(cur):
                    cand = len(p) + 2
                    if tail_len + cand > overlap_chars:
                        break
                    tail.append(p)
                    tail_len += cand
                tail.reverse()
                cur = tail
                cur_len = sum(len(p) + 2 for p in cur)
            else:
                cur = []
                cur_len = 0
        cur.append(para)
        cur_len += plen

    if cur:
        chunks.append("\n\n".join(cur))

    return chunks


def process_file(
    in_path: Path,
    out_dir: Path,
    chunk_dir: Path | None,
    min_chars: int,
    drop_boilerplate: bool,
    max_chars: int,
    overlap_chars: int,
) -> Dict[str, int]:
    stats = {
        "read": 0,
        "written": 0,
        "dedup_skipped": 0,
        "short_skipped": 0,
        "chunks_written": 0,
    }
    seen_ids = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{in_path.stem}_clean.ndjson"
    chunk_out = None
    if chunk_dir:
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_out = chunk_dir / f"{in_path.stem}_chunks.ndjson"

    with in_path.open("r", encoding="utf-8") as rf, out_path.open("w", encoding="utf-8") as wf:
        chunk_fh = chunk_out.open("w", encoding="utf-8") if chunk_out else None
        try:
            for line in rf:
                stats["read"] += 1
                obj = json.loads(line)
                doc_id = obj.get("doc_id")
                if doc_id in seen_ids:
                    stats["dedup_skipped"] += 1
                    continue
                seen_ids.add(doc_id)

                clean_txt = normalize_text(obj.get("text", ""), drop_boilerplate=drop_boilerplate)
                if min_chars and len(clean_txt) < min_chars:
                    stats["short_skipped"] += 1
                    continue

                obj["text"] = clean_txt
                wf.write(json.dumps(obj, ensure_ascii=False) + "\n")
                stats["written"] += 1

                if chunk_fh:
                    for idx, chunk in enumerate(chunk_text(clean_txt, max_chars=max_chars, overlap_chars=overlap_chars), 1):
                        chunk_obj = dict(obj)
                        chunk_obj["chunk_id"] = f"{doc_id}#chunk{idx}"
                        chunk_obj["text"] = chunk
                        chunk_fh.write(json.dumps(chunk_obj, ensure_ascii=False) + "\n")
                        stats["chunks_written"] += 1
        finally:
            if chunk_fh:
                chunk_fh.close()

    return stats


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Yargıtay NDJSON temizleme ve chunk üretimi")
    ap.add_argument(
        "--input-glob",
        default="legal-etl/yargitaydocs/yargitay_*.ndjson",
        help="Temizlenecek NDJSON glob deseni",
    )
    ap.add_argument(
        "--out-dir",
        default="legal-etl/cleaned",
        help="Temiz NDJSON çıkış klasörü",
    )
    ap.add_argument(
        "--chunk-dir",
        default=None,
        help="Chunk NDJSON çıkış klasörü (boş bırakılırsa chunk yazılmaz)",
    )
    ap.add_argument(
        "--min-chars",
        type=int,
        default=50,
        help="Bu uzunluktan kısa kayıtları at",
    )
    ap.add_argument(
        "--max-chars",
        type=int,
        default=2200,
        help="Chunk başına karakter sınırı (yaklaşık 400-500 token)",
    )
    ap.add_argument(
        "--overlap-chars",
        type=int,
        default=300,
        help="Chunk'lar arası karakter örtüşmesi",
    )
    ap.add_argument(
        "--keep-boilerplate",
        action="store_true",
        help="Boilerplate satırları tut (varsayılan: at)",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    input_paths = sorted(Path().glob(args.input_glob))
    if not input_paths:
        raise SystemExit(f"Girdi bulunamadı: {args.input_glob}")

    out_dir = Path(args.out_dir)
    chunk_dir = Path(args.chunk_dir) if args.chunk_dir else None
    drop_boilerplate = not args.keep_boilerplate

    print(f"Girdiler: {len(input_paths)} dosya")
    for p in input_paths:
        stats = process_file(
            p,
            out_dir=out_dir,
            chunk_dir=chunk_dir,
            min_chars=args.min_chars,
            drop_boilerplate=drop_boilerplate,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
        )
        print(
            f"{p.name}: okunan={stats['read']} yazılan={stats['written']} "
            f"dedup={stats['dedup_skipped']} kısa={stats['short_skipped']} "
            f"chunk={stats['chunks_written']}"
        )


if __name__ == "__main__":
    main()
