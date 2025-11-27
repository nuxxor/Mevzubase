#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Yargıtay Karar Arama ve LLM Analiz Sistemi v3.2
Hakim, savcı ve avukatlar için Yargıtay/İstinaf kararlarını otomatik arayan ve analiz eden sistem.

CHANGELOG v3.2:
1. Multi-query retrieval mekanizması: drop-one ve add-one varyantlar
2. build_query_buckets akıllı varyant üretici olarak güncellendi
3. MAX_BROAD_VARIANTS config parametresi eklendi
4. extra_terms parametresi ile literal terimlerin broad sorgulara dahil edilmesi
"""
import argparse
import base64
import json
import os
import time
import requests
from requests.adapters import HTTPAdapter
import re
import html
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import platform
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from urllib.parse import quote
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

import logging
try:
    from opensearchpy import OpenSearch  # type: ignore
    HAS_OPENSEARCH = True
except Exception:
    HAS_OPENSEARCH = False
try:
    from logging.handlers import RotatingFileHandler
    HAS_ROTATING_HANDLER = True
except ImportError:
    HAS_ROTATING_HANDLER = False

try:
    import tenacity
    from tenacity import retry, stop_after_attempt, wait_exponential
    HAS_TENACITY = True
except ImportError:
    tenacity = None
    HAS_TENACITY = False

try:
    from urllib3.util.retry import Retry  # type: ignore
except Exception:
    Retry = None

# ============================================================================
# CONFIGURATION
# ============================================================================

SEARCH_URL = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
DOC_URL = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"
VIEW_URL = "https://mevzuat.adalet.gov.tr/ictihat/{id}"

SEARCH_TIMEOUT_SEC = float(os.environ.get("SEARCH_TIMEOUT_SEC", "45"))
SEARCH_RETRY_COUNT = int(os.environ.get("SEARCH_RETRY_COUNT", "2"))
CONNECT_TIMEOUT_SEC = float(os.environ.get("CONNECT_TIMEOUT_SEC", "10"))
DOC_TIMEOUT_SEC = float(os.environ.get("DOC_TIMEOUT_SEC", "180"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:32b-instruct")
CHAT_GPT_API_KEY = os.environ.get("CHAT_GPT_API_KEY")
CHAT_GPT_MODEL = os.environ.get("CHAT_GPT_MODEL", "gpt-4o-mini")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
PARALLEL_API_KEY = os.environ.get("PARALLEL_API_KEY")
RERANK_PROVIDER = os.environ.get("RERANK_PROVIDER", "local").lower()  # none|local|cohere|parallel|auto
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_FALLBACK_MODEL = os.environ.get("RERANK_FALLBACK_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
RERANK_TRUST_REMOTE_CODE = os.environ.get("RERANK_TRUST_REMOTE_CODE", "true").lower() in {"1", "true", "yes", "on"}
COHERE_RERANK_MODEL = os.environ.get("COHERE_RERANK_MODEL", "rerank-v3.5")
RERANK_TOP_N = int(os.environ.get("RERANK_TOP_N", "50"))
# Local öncelik, Cohere isteğe bağlı fallback
COHERE_FALLBACK_ENABLED = os.environ.get("COHERE_FALLBACK_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
RULE_CARD_COLLECTION = os.environ.get("RULE_CARD_COLLECTION", "rule_cards")
RULE_CARD_MODEL = os.environ.get("RULE_CARD_MODEL", "BAAI/bge-m3")
RULE_CARD_DEVICE = os.environ.get("RULE_CARD_DEVICE", "cuda")
RULE_CARD_QDRANT_URL = os.environ.get("RULE_CARD_QDRANT_URL", "http://localhost:6333")
RULE_CARD_TOP_K = int(os.environ.get("RULE_CARD_TOP_K", "5"))

# BM25/Hibrit ayarları
BM25_ENABLED = os.environ.get("BM25_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
BM25_URL = os.environ.get("BM25_URL", "http://admin:admin@localhost:9200")
BM25_INDEX = os.environ.get("BM25_INDEX", "legal_chunks_bm25")
BM25_LIMIT = int(os.environ.get("BM25_LIMIT", "60"))

MIN_TERMS = 3
ACCEPTED_ITEM_TYPES = {"YARGITAYKARAR", "YARGITAYKARARI", "YARGITAY", "ISTINAFHUKUK", "ISTINAFCEZA"}

# Multi-query retrieval config
MAX_BROAD_VARIANTS = 6  # en fazla kaç farklı varyant üreteceğiz

SOURCE_CONFIG = {
    "yargitay": {"label": "Yargıtay", "item_types": ["YARGITAYKARARI"]},
    "istinaf": {"label": "Bölge Adliye Mahkemesi (İstinaf)", "item_types": ["ISTINAFHUKUK"]},
}
DEFAULT_SOURCES = ["yargitay", "istinaf"]

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "adaletapplicationname": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}

def _build_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(BASE_HEADERS)
    if Retry is not None:
        try:
            retries = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=1.5,
                status_forcelist=(502, 503, 504),
                allowed_methods=frozenset(["GET", "POST"]),
            )
        except TypeError:
            retries = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=1.5,
                status_forcelist=(502, 503, 504),
                method_whitelist=frozenset(["GET", "POST"]),
            )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
    return sess

SESSION = _build_session()

# Madde 3: Türkçe karakter normalizasyon sözlüğü
TURKISH_TYPO_CORRECTIONS = {
    "yagma": "yağma",
    "nitelikli yagma": "nitelikli yağma",
    "hirsizlik": "hırsızlık",
    "rusvet": "rüşvet",
    "sikayet": "şikayet",
    "magdur": "mağdur",
    "dolandiricilik": "dolandırıcılık",
    "sahtecilik": "sahtecilik",
    "oldurmek": "öldürmek",
    "oldurme": "öldürme",
    "hurriyetin tahdidi": "hürriyetin tahdidi",
    "taksirle": "taksirle",
    "tufe": "tüfe",
    "tuketici": "tüketici",
    "yiu-fe": "yi-üfe",
    "yi-ufe": "yi-üfe",
}

# Hakaret / literal ifadeler için basit seed sözlük.
# 9.5M korpustan üreteceğin büyük sözlüğü ileride buraya bağlayabilirsin.
INSULT_SEED_WORDS = {
    "ibne",
    "ibnesin",
    "şerefsiz",
    "orospu",
    "puşt",
}

STOP_CONCEPTS = {
    "yasal",
    "sozlesme",
    "sözlesme",
    "sözleşme",
    "zam",
    "durum",
    "dava",
    "mahkeme",
    "genel",
}

CONCEPT_TO_ARTICLE_HINTS = {
    "kira artış oranı": ["TBK 344"],
    "kira tespit": ["TBK 344"],
    "kira sözleşmesi": ["TBK 344"],
    "nafaka": ["TMK 175"],
    "yoksulluk nafakası": ["TMK 175"],
    "iştirak nafakası": ["TMK 329"],
    "participation allowance": ["TMK 329"],
}

# Tırnak içi ifadeleri yakalamak için desenler
QUOTED_PHRASE_PATTERNS = [
    r'"([^"\n]{1,80})"',   # straight double quotes
    r"'([^'\n]{1,80})'",   # straight single quotes
    r'“([^”\n]{1,80})”',   # smart double quotes
    r'‘([^’\n]{1,80})’',   # smart single quotes
]

# Kanun maddesi pattern (tam eşleşme, capturing group yok)
LAW_PATTERN = re.compile(
    r'\b(?:TCK|CMK|HMK|TMK|BK|TTK|TBK|İİK)\s*\d+(?:/\d+)?\b',
    re.I
)

# Global LLM provider selection
SELECTED_LLM_PROVIDER = None

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

if HAS_ROTATING_HANDLER:
    handlers = [
        RotatingFileHandler(
            'yargitay_search.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
else:
    handlers = [
        logging.FileHandler('yargitay_search.log', encoding='utf-8'),
        logging.StreamHandler()
    ]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_print(text):
    """Windows CMD'de emoji sorunlarını önler."""
    if platform.system() == "Windows" and sys.stdout.encoding != "utf-8":
        replacements = {
            "🔍": "[ARAMA]", "✓": "[OK]", "⚠️": "[UYARI]",
            "🔧": "[AYAR]", "📝": "[SORU]", "🤖": "[LLM]",
            "🌐": "[API]", "📊": "[SONUC]", "📖": "[ANALIZ]",
            "💾": "[KAYIT]", "📄": "[DOSYA]", "✅": "[TAMAM]",
            "❌": "[HATA]", "🔄": "[ITER]", "✨": "[BASARI]",
            "📌": "[NOT]", "ℹ️": "[BILGI]", "⏭️": "[SKIP]"
        }
        for emoji, replacement in replacements.items():
            text = text.replace(emoji, replacement)
    print(text)

def _ascii_fold(s: str) -> str:
    return (
        s.replace("ş", "s").replace("Ş", "S")
         .replace("ç", "c").replace("Ç", "C")
         .replace("ğ", "g").replace("Ğ", "G")
         .replace("ı", "i").replace("İ", "i")
         .replace("ö", "o").replace("Ö", "O")
         .replace("ü", "u").replace("Ü", "U")
    )


def _lexical_overlap_score(query: str, text: str) -> float:
    """Basit kelime kesişim skoru (ascii-fold + lower)."""
    if not query or not text:
        return 0.0
    q_tokens = set(re.findall(r"[a-z0-9çğıöşü]+", _ascii_fold(query.lower())))
    t_tokens = set(re.findall(r"[a-z0-9çğıöşü]+", _ascii_fold(text.lower())))
    if not q_tokens or not t_tokens:
        return 0.0
    inter = len(q_tokens & t_tokens)
    return inter / max(1, len(q_tokens))

def _has_kira_domain(keywords: List[Dict[str, Any]]) -> bool:
    blob = " ".join(kw.get("text", "").lower() for kw in keywords)
    folded = _ascii_fold(blob)
    signals = ["kira artış", "kira bedel", "kira sözleş", "kira tespit"]
    ascii_signals = ["kira artis", "kira bedel", "kira sozles", "kira tespit"]
    return any(sig in blob for sig in signals) or any(sig in folded for sig in ascii_signals)


def _has_tufe_signal(text_blob: str) -> bool:
    """TBK 344 / TÜFE / 12 aylık ortalama sinyali var mı."""
    t = _ascii_fold(text_blob.lower())
    return any(
        key in t
        for key in [
            "tbk 344",
            "tufe",
            "12 aylik ortalama",
            "tuketici fiyat endeksi",
            "tüfe",
            "on iki aylik ortalama",
        ]
    )


def _extract_percent_values(text: str) -> List[int]:
    """Metindeki yüzde değerlerini (%, yüzde) yakalar."""
    if not text:
        return []
    vals: List[int] = []
    patterns = [
        r"%\s*(\d{1,3})",
        r"y[uü]zde\s*(\d{1,3})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            try:
                vals.append(int(m.group(1)))
            except Exception:
                continue
    return vals

def add_domain_seeds(question: str, keywords: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Kira/konut bağlamında deterministik TBK 344 / TÜFE sinyallerini ekler."""
    ql = (question or "").lower()
    seeds: List[str] = []
    # Kira / konut
    if any(t in ql for t in ["kira", "kiracı", "kiralayan", "işyeri", "is yeri", "konut"]):
        seeds += [
            "TBK 344",
            "TÜFE",
            "12 aylik ortalama",
            "tüketici fiyat endeksi",
            "tuketici fiyat endeksi",
            "kira tespiti",
        ]
    # Nafaka
    if any(t in ql for t in ["nafaka", "yoksulluk nafakası", "iştirak nafakası"]):
        seeds += [
            "TMK 175",
            "TMK 329",
            "TÜFE",
            "12 aylik ortalama",
            "tüketici fiyat endeksi",
            "tuketici fiyat endeksi",
        ]
    have = {kw["text"].lower() for kw in keywords if kw.get("text")}
    for s in seeds:
        if s.lower() in have:
            continue
        keywords.append(
            create_keyword_object(
                s,
                llm_confidence=0.95,
                source="domain_seed",
                keyword_type=("article" if s.upper().startswith("TBK") else None),
            )
        )
        have.add(s.lower())
    return keywords

def _item_type(item: dict) -> str:
    """Karar item type'ını döndürür."""
    if not isinstance(item, dict):
        return ""
    typ = item.get("itemType") or {}
    return (typ.get("name") or "").upper()

def _is_metadata_error(parsed) -> bool:
    """API yanıtında metadata error kontrolü."""
    meta = None
    if isinstance(parsed, dict):
        meta = parsed.get("metadata")
    if meta and isinstance(meta, dict):
        return (meta.get("FMTY") or "").upper() == "ERROR"
    return False

def _is_supported_item(item: dict) -> bool:
    """Karar tipinin desteklenip desteklenmediğini kontrol eder."""
    name = _item_type(item)
    if name in ACCEPTED_ITEM_TYPES:
        return True
    return "YARGITAY" in name or "ISTINAF" in name

def _decode_html(value: str) -> str:
    """Base64 veya düz HTML stringi çözer."""
    if not isinstance(value, str):
        return ""
    txt = value.strip()
    if "<html" in txt.lower() or "<body" in txt.lower():
        return txt
    try:
        missing = len(txt) % 4
        if missing:
            txt += "=" * (4 - missing)
        decoded = base64.b64decode(txt, validate=False)
        html_content = decoded.decode("utf-8", errors="ignore")
        return html_content
    except Exception:
        return value

def _extract_html(node) -> str:
    """JSON içinde ilk HTML/base64 içeriğini bul ve çözüp döndür."""
    if isinstance(node, str):
        return _decode_html(node)
    if isinstance(node, dict):
        for key in ("content", "data", "icerik", "html"):
            if key in node:
                found = _extract_html(node[key])
                if found:
                    return found
    if isinstance(node, list):
        for item in node:
            found = _extract_html(item)
            if found:
                return found
    return ""

def _try_parse_json(val):
    """String JSON ise dict'e çevir; değilse aynen döndür."""
    if not isinstance(val, str):
        return val
    txt = val.strip()
    if not (txt.startswith("{") or txt.startswith("[")):
        return val
    try:
        return json.loads(txt)
    except Exception:
        return val

def _html_to_text(raw: str) -> str:
    """Basit HTML temizleyici: <br>/<p> -> yeni satır, etiketleri kaldır."""
    if not isinstance(raw, str):
        return ""
    txt = raw
    txt = re.sub(r"<\s*br\s*/?\s*>", "\n", txt, flags=re.I)
    txt = re.sub(r"</p\s*>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n\s*", "\n", txt)
    return txt.strip()

def _format_search_term(term: str) -> str:
    """Arama terimi formatlar: +\"term\" şeklinde."""
    if not isinstance(term, str):
        return ""
    cleaned = term.strip().strip('"')
    if not cleaned:
        return ""
    return f'+"{cleaned}"'

def _kira_focus_queries() -> List[str]:
    anchors = [
        "TBK 344", "TBK m.344", "TBK m. 344", "Türk Borçlar Kanunu 344",
        "TÜFE", "tüfe", "tuketici fiyat endeksi",
        "12 aylik ortalama", "on iki aylik ortalama",
    ]
    cores = ["kira artış", "kira artış oranı", "kira tespit"]
    qs: List[str] = []
    for a in anchors:
        for c in cores[:2]:
            qs.append(f"{_format_search_term(c)} {_format_search_term(a)}")
    seen: set[str] = set()
    out: List[str] = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= 6:
            break
    return out


def _nafaka_focus_queries() -> List[str]:
    anchors = [
        "TÜFE", "tüfe", "tuketici fiyat endeksi",
        "12 aylik ortalama", "on iki aylik ortalama",
        "TMK 175", "TMK 329",
    ]
    cores = ["nafaka", "yoksulluk nafakası", "iştirak nafakası"]
    qs: List[str] = []
    for a in anchors:
        for c in cores:
            qs.append(f"{_format_search_term(c)} {_format_search_term(a)}")
    seen: set[str] = set()
    out: List[str] = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= 6:
            break
    return out

def extract_quoted_phrases(text: str) -> List[str]:
    """\"...\", '...' vb. tırnak içi ifadeleri çıkarır."""
    if not isinstance(text, str):
        return []
    phrases: List[str] = []
    for pat in QUOTED_PHRASE_PATTERNS:
        for m in re.finditer(pat, text):
            phrase = m.group(1).strip()
            if phrase:
                phrases.append(phrase)
    # uniq (case-insensitive)
    seen = set()
    uniq_phrases: List[str] = []
    for p in phrases:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            uniq_phrases.append(p)
    return uniq_phrases

def extract_literal_keywords_from_question(text: str) -> List[str]:
    """
    Sorudaki tırnak içi ifadeler ve basit hakaret kalıplarından
    literal anahtar kelimeler çıkarır (LLM'den bağımsız).
    """
    if not isinstance(text, str):
        return []

    candidates: List[str] = []

    # 1) Tırnak içi her şey
    candidates.extend(extract_quoted_phrases(text))

    lowered = text.lower()

    # 2) "bana X dedi / diyor / demiş / hakaret etti" gibi kalıplar
    pattern_simple_speech = re.compile(
        r"bana\s+([^\s,.;!?]{1,30})\s+(?:dedi|diyor|demiş|hitap\s+etti|hakaret\s+etti)",
        flags=re.IGNORECASE,
    )
    for m in pattern_simple_speech.finditer(lowered):
        token = m.group(1).strip()
        if token:
            candidates.append(token)

    # 3) Seed hakaret sözlüğü
    for insult in INSULT_SEED_WORDS:
        if re.search(rf"\b{re.escape(insult)}\b", lowered):
            candidates.append(insult)

    # uniq
    seen = set()
    uniq_candidates: List[str] = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            uniq_candidates.append(c)
    return uniq_candidates

# ============================================================================
# MADDE 3: TÜRKÇE KARAKTER NORMALİZASYONU
# ============================================================================

def normalize_legal_term(term: str) -> str:
    """
    LLM'den gelen anahtar kelimeyi düzeltir (Türkçe karakter hatalarını giderir).
    """
    if not term:
        return term
    
    term_lower = term.lower()
    
    # Sözlükte varsa direkt düzelt
    if term_lower in TURKISH_TYPO_CORRECTIONS:
        return TURKISH_TYPO_CORRECTIONS[term_lower]
    
    # Kanun maddeleri dokunulmaz
    if LAW_PATTERN.search(term):
        return term
    
    return term

# ============================================================================
# MADDE 2: ANAHTAR KELİME TİPLENDİRME
# ============================================================================

def classify_keyword_type(keyword: str) -> str:
    """
    Anahtar kelimeyi tiplerine göre sınıflandırır:
    - article: Kanun maddesi (TCK 150/1)
    - crime: Suç adı (nitelikli yağma)
    - procedure: Usul kavramı (takipsizlik, beraat)
    - concept: Hukuki kavram (hukuki alacağın tahsili)
    - literal: Hakaret/tehdit ifadeleri
    - other: Diğer
    """
    if LAW_PATTERN.search(keyword):
        return "article"
    
    keyword_lower = keyword.lower()
    
    # Literal / hakaret ifadeleri
    if keyword_lower in INSULT_SEED_WORDS:
        return "literal"
    
    # Suç adları
    crimes = {
        "yağma", "nitelikli yağma", "hırsızlık", "dolandırıcılık", "zimmet",
        "irtikap", "rüşvet", "kasten yaralama", "taksirle yaralama",
        "cinsel saldırı", "cinsel istismar", "kasten öldürme", "adam öldürme",
        "tehdit", "hakaret", "şantaj", "güveni kötüye kullanma"
    }
    
    # Usul kavramları (tamamı lowercase)
    procedures = {
        "takipsizlik", "beraat", "mahkumiyet", "temyiz", "istinaf",
        "bozma", "onanma", "kyok", "yhgk", "duruşma", "delil"
    }
    
    # Hukuki kavramlar (genişletilmiş)
    concepts = {
        "hukuki alacağın tahsili", "hukuki ilişkiye dayanan alacak",
        "alacak borç ilişkisi", "hukuken korunan alacak", "meşru hak",
        "kira", "kira sözleşmesi", "kira artış oranı", "kira bedeli",
        "maddi tazminat", "manevi tazminat", "tazminat"
    }
    
    if any(crime in keyword_lower for crime in crimes):
        return "crime"
    
    if any(proc in keyword_lower for proc in procedures):
        return "procedure"
    
    if any(concept in keyword_lower for concept in concepts):
        return "concept"
    
    return "other"


def generate_diacritic_variants(term: str, max_variants: int = 6) -> List[str]:
    """Diyakritik ve kısaltma varyantları üretir (örn. TÜFE -> tufe/TUFE)."""
    if not term:
        return []
    base = term.strip()
    variants: List[str] = [base]
    asciiish = _ascii_fold(base)
    if asciiish != base:
        variants.append(asciiish)
    lower = base.lower()

    if lower in {"tüfe", "tufe"} or "tüketici fiyat endeksi" in lower:
        variants += ["TÜFE", "tüfe", "TUFE", "tufe", "tuketici fiyat endeksi"]

    if lower in {"üfe", "ufe", "yi-üfe", "yi-ufe", "yi üfe", "yı-üfe"} or "üretici fiyat endeksi" in lower:
        variants += ["ÜFE", "üfe", "UFE", "ufe", "Yİ-ÜFE", "YI-UFE", "yi-üfe", "yi-ufe", "üretici fiyat endeksi"]

    if "tbk 344" in lower:
        variants += ["TBK 344", "TBK m.344", "TBK m. 344", "Türk Borçlar Kanunu 344"]

    out: List[str] = []
    for v in variants:
        if v and v not in out:
            out.append(v)
        if len(out) >= max_variants:
            break
    return out


def expand_law_article(article: str) -> List[str]:
    """TBK 344 gibi maddeleri ek varyantlarla genişletir."""
    if not article:
        return []
    core = re.sub(r"\s+", " ", article).strip()
    expansions = [core]
    lowered = core.lower()
    if "tbk" in lowered and "344" in lowered:
        expansions.extend(
            [
                "TBK 344",
                "TBK m.344",
                "TBK m. 344",
                "Turk Borclar Kanunu 344",
                "on iki aylik ortalama",
                "tufe",
                "tuketici fiyat endeksi",
            ]
        )
    return expansions


def rrf_merge(ranklists: List[List[str]], k: int = 60) -> List[str]:
    """Reciprocal Rank Fusion: ranklist listelerinden tekleştirilmiş sıra üretir."""
    scores: Dict[str, float] = {}
    for rl in ranklists:
        for rank, doc_id in enumerate(rl):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc for doc, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def search_bm25(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """OpenSearch BM25 sonuçlarını döndürür (opsiyonel hibrit)."""
    if not BM25_ENABLED or not HAS_OPENSEARCH:
        return []
    try:
        client = OpenSearch(BM25_URL, verify_certs=False, timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"BM25 bağlantı hatası: {exc}")
        return []
    body = {
        "size": limit,
        "query": {
            "match": {
                "content": {
                    "query": query,
                    "operator": "and",
                }
            }
        },
    }
    try:
        res = client.search(index=BM25_INDEX, body=body)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"BM25 arama hatası: {exc}")
        return []
    hits = res.get("hits", {}).get("hits", [])
    docs: List[Dict[str, Any]] = []
    for h in hits:
        src = h.get("_source") or {}
        doc_id = src.get("doc_id") or h.get("_id")
        content = src.get("content") or ""
        docs.append(
            {
                "document_id": doc_id,
                "tam_metin": content,
                "ozet": content[:500],
                "kaynak": "BM25",
                "item_type": src.get("doc_type"),
                "bucket": "bm25",
                "query_signature": "bm25",
                "bm25_score": h.get("_score"),
                "chamber": src.get("chamber"),
                "decision_date": src.get("decision_date"),
                "view_url": src.get("url"),
            }
        )
    return docs


def dedup_documents(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """document_id'ye göre deduplikasyon yapar, ilk gördüğünü korur."""
    seen = set()
    out = []
    for d in docs:
        did = d.get("document_id")
        if did and did in seen:
            continue
        if did:
            seen.add(did)
        out.append(d)
    return out

def create_keyword_object(
    text: str,
    llm_confidence: float = 0.8,
    keyword_type: Optional[str] = None,
    *,
    source: str = "llm",
    mandatory: bool = False,
) -> Dict[str, Any]:
    """
    Anahtar kelime objesi oluşturur.

    keyword_type verilmezse classify_keyword_type ile atanır.
    source: "llm", "law_article", "literal", "question_text" vb.
    mandatory: strict sorguda mutlaka yer alması gereken terimler (ör. hakaret kelimesi).
    """
    normalized = normalize_legal_term(text)
    if keyword_type is None:
        keyword_type = classify_keyword_type(normalized)

    return {
        "text": normalized,
        "type": keyword_type,
        "source": source,
        "llm_confidence": llm_confidence,
        "mandatory": mandatory,
    }


# ============================================================================
# RERANKER PROVIDERS
# ============================================================================

class BaseReranker:
    def rerank(self, query: str, docs: List[str], top_n: int) -> List[int]:
        raise NotImplementedError


class LocalHFReranker(BaseReranker):
    def __init__(self, model_name: str = RERANK_MODEL, device: Optional[str] = None, trust_remote_code: Optional[bool] = None):
        self.model_name = model_name
        self.device = device or ("cuda" if self._has_cuda() else "cpu")
        self.trust_remote_code = RERANK_TRUST_REMOTE_CODE if trust_remote_code is None else trust_remote_code
        self.available = False
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
            import torch  # type: ignore
        except ImportError:
            logger.warning("Local reranker için transformers/torch bulunamadı.")
            return
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=self.trust_remote_code)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name, trust_remote_code=self.trust_remote_code)
            self.model.to(self.device)
            self.model.eval()
            self.torch = __import__("torch")
            self.available = True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Local reranker modeli yüklenemedi: {exc}")

    def _has_cuda(self) -> bool:
        try:
            import torch  # type: ignore
            return torch.cuda.is_available()
        except Exception:
            return False

    def rerank(self, query: str, docs: List[str], top_n: int) -> List[int]:
        if not self.available:
            return []
        try:
            inputs = self.tokenizer(
                [query] * len(docs),
                docs,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with self.torch.inference_mode():  # type: ignore[attr-defined]
                scores = self.model(**inputs).logits.squeeze(-1).tolist()
            order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
            return order[:top_n]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Local reranker hata verdi: {exc}")
            return []


class CohereReranker(BaseReranker):
    def __init__(self, api_key: Optional[str] = COHERE_API_KEY, model: str = COHERE_RERANK_MODEL):
        self.api_key = api_key
        self.model = model
        try:
            import cohere  # type: ignore
            self.client = cohere.ClientV2(api_key=api_key) if api_key else None
        except Exception:
            self.client = None

    def rerank(self, query: str, docs: List[str], top_n: int) -> List[int]:
        if not self.client or not self.api_key:
            return []
        try:
            res = self.client.rerank(model=self.model, query=query, documents=docs, top_n=top_n)
            order = [r.index for r in res.results]
            return order
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Cohere rerank çağrısı başarısız: {exc}")
            return []


class ParallelReranker(BaseReranker):
    def __init__(self, api_key: Optional[str] = PARALLEL_API_KEY):
        self.api_key = api_key

    def rerank(self, query: str, docs: List[str], top_n: int) -> List[int]:
        # Placeholder: Parallel.ai entegrasyonu için API istemcisi burada eklenebilir.
        return []


def pick_reranker() -> Optional[BaseReranker]:
    choice = RERANK_PROVIDER
    if choice == "none":
        return None
    if choice == "local":
        return LocalHFReranker()
    if choice == "cohere":
        return CohereReranker()
    if choice == "parallel":
        return ParallelReranker()
    if choice == "auto":
        for candidate in (LocalHFReranker(), CohereReranker(), ParallelReranker()):
            if isinstance(candidate, LocalHFReranker) and not candidate.available:
                continue
            return candidate
    return None


def rerank_docs(query: str, docs: List[Dict[str, Any]], top_n: int = RERANK_TOP_N) -> List[Dict[str, Any]]:
    if not docs:
        return docs
    reranker = pick_reranker()
    # Lexical fallback: basit overlap skoruyla sırala
    if reranker is None:
        texts = []
        for d in docs:
            texts.append(d.get("ozet") or (d.get("tam_metin") or "")[:800])
        scored = [
            (idx, _lexical_overlap_score(query, text))
            for idx, text in enumerate(texts)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        order = [idx for idx, score in scored if score > 0][:min(top_n, len(docs))]
        if not order:
            return docs
        ordered = [docs[i] for i in order if i < len(docs)]
        seen_idx = set(order)
        for idx, doc in enumerate(docs):
            if idx not in seen_idx:
                ordered.append(doc)
        return ordered
    texts = []
    for d in docs:
        text = d.get("ozet") or (d.get("tam_metin") or "")[:800]
        texts.append(text)
    order = reranker.rerank(query, texts, min(top_n, len(docs)))
    if not order and COHERE_FALLBACK_ENABLED and COHERE_API_KEY:
        logger.info("rerank.cohere_fallback")
        try:
            co_reranker = CohereReranker(api_key=COHERE_API_KEY, model=COHERE_RERANK_MODEL)
            order = co_reranker.rerank(query, texts, min(top_n, len(docs)))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Cohere fallback başarısız: {exc}")
    if not order:
        return docs
    ordered = [docs[i] for i in order if i < len(docs)]
    # eklenmeyenleri eski sırayla sona koy
    seen_idx = set(order)
    for idx, doc in enumerate(docs):
        if idx not in seen_idx:
            ordered.append(doc)
    return ordered

# ============================================================================
# MADDE 1: SORGU OPTİMİZASYONU (MULTI-QUERY RETRIEVAL)
# ============================================================================

def build_query_buckets(
    keywords: List[Dict[str, Any]],
    extra_terms: Optional[List[str]] = None,
    max_broad_variants: int = MAX_BROAD_VARIANTS,
    paraphrase_count: int = 3,
    llm_for_paraphrase: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Anahtar kelimelerden:
      - strict_query: en güçlü kombinasyon
      - broad_queries: strict'ten en az bir kelimesi farklı 2–6 varyant
    üretir.

    extra_terms: (opsiyonel) soru metninden gelen literal terimler vb.
    max_broad_variants: en fazla kaç broad varyant üreteceğiz
    """
    # 1) Tiplerine göre ayır
    articles   = [kw for kw in keywords if kw.get("type") == "article"]
    crimes     = [kw for kw in keywords if kw.get("type") == "crime"]
    procedures = [kw for kw in keywords if kw.get("type") == "procedure"]
    concepts   = [kw for kw in keywords if kw.get("type") == "concept"]
    literals   = [kw for kw in keywords if kw.get("type") == "literal"]
    mandatory  = [kw for kw in keywords if kw.get("mandatory")]
    kira_domain = _has_kira_domain(keywords)

    # 2) Strict için güçlü terimler
    strict_terms: List[str] = []
    strict_terms.extend([kw["text"] for kw in articles])
    strict_terms.extend([kw["text"] for kw in crimes])
    strict_terms.extend([kw["text"] for kw in literals])

    # Mandatory flag'i olanları her durumda ekle
    for kw in mandatory:
        strict_terms.append(kw["text"])

    # Kritik usul kavramları
    for proc in procedures:
        if proc.get("llm_confidence", 0) >= 0.7:
            strict_terms.append(proc["text"])

    # Kritik kavramlar (örn. kira, maddi tazminat)
    for concept in concepts:
        if concept.get("llm_confidence", 0) >= 0.7:
            strict_terms.append(concept["text"])

    # Fallback: hala boşsa, tüm keyword'lerden ilk 3–4'ü kullan
    if not strict_terms:
        logger.warning("Strict query boş, tüm anahtar kelimelerden fallback kullanılıyor")
        strict_terms = [kw["text"] for kw in keywords[:4] if kw.get("text")]

    # Aynı terimi tekrar etme
    seen = set()
    strict_terms_dedup = []
    for t in strict_terms:
        if t and t not in seen:
            seen.add(t)
            strict_terms_dedup.append(t)
    strict_terms = strict_terms_dedup

    # Genel kavramları strict'ten temizle
    filtered_terms = []
    for t in strict_terms:
        if _ascii_fold(t).lower() in STOP_CONCEPTS:
            continue
        filtered_terms.append(t)
    if filtered_terms:
        strict_terms = filtered_terms

    # Tek güçlü terim varsa, en az bir 'other' kelimeyi strict'e yükselt
    if len(strict_terms) == 1:
        for kw in keywords:
            t = kw.get("text")
            if kw.get("type") == "other" and t and _ascii_fold(t).lower() not in STOP_CONCEPTS and t not in strict_terms:
                strict_terms.append(t)
                break

    if kira_domain:
        if not any("tbk 344" in t.lower() for t in strict_terms):
            strict_terms.append("TBK 344")
        if not any(_ascii_fold(t).lower() in {"tufe", "tuketici fiyat endeksi"} for t in strict_terms):
            strict_terms.append("tüfe")

    strict_query = " ".join(_format_search_term(t) for t in strict_terms if t)

    # 3) Broad varyantlar için other_terms
    strong_terms = strict_terms[:]  # referans
    other_terms: List[str] = []

    for kw in keywords:
        t = kw["text"]
        if not t:
            continue
        if t in strong_terms:
            continue
        other_terms.append(t)

    # Soru metninden gelen ekstra literal terimleri de ekle (opsiyonel)
    if extra_terms:
        for t in extra_terms:
            if t and t not in strong_terms and t not in other_terms:
                other_terms.append(t)

    # Kanun maddesi varyantlarını broad'a ekle
    for art in articles:
        for variant in expand_law_article(art.get("text", "")):
            if variant and variant not in strong_terms and variant not in other_terms:
                other_terms.append(variant)

    # Diyakritik/kısaltma varyantlarını broad'a ekle
    diacritic_candidates = list(other_terms)
    for candidate in diacritic_candidates:
        for variant in generate_diacritic_variants(candidate):
            if variant and variant not in strong_terms and variant not in other_terms:
                other_terms.append(variant)

    # TBK 344 sinyalini öne çek (TÜFE / on iki aylık ortalama)
    has_tbk_344 = any("344" in (a.get("text", "").lower()) and "tbk" in (a.get("text", "").lower()) for a in articles)
    if has_tbk_344:
        tbk_terms = ["on iki aylik ortalama", "12 aylik ortalama", "tufe", "tuketici fiyat endeksi"]
        for term in reversed(tbk_terms):
            if term not in strong_terms and term not in other_terms:
                other_terms.insert(0, term)

    # Kira bazlı sorularda broad varyantlara ufak synonym katmanı ekle
    if kira_domain:
        kira_synonyms = [
            "tufe",
            "tüfe",
            "TÜFE",
            "tuketici fiyat endeksi",
            "12 aylik ortalama",
            "on iki aylik ortalama",
            "TBK 344",
        ]
        for syn in kira_synonyms:
            if syn not in strong_terms and syn not in other_terms:
                other_terms.append(syn)

    # Domain pivot (en güçlü tek kavram + TBK 344 / TÜFE sinyali) varyantları
    strong_single = None
    for kw in (concepts + articles + crimes + procedures + literals):
        t = (kw.get("text") or "").strip()
        if t:
            strong_single = t
            break
    if strong_single is None and strict_terms:
        strong_single = strict_terms[0]

    domain_pivots = [
        t for t in other_terms
        if t and t.lower() in {"tbk 344", "tüfe", "tufe", "12 aylik ortalama", "tuketici fiyat endeksi"}
    ]
    domain_pivot_queries: List[str] = []
    if strong_single and domain_pivots:
        for dp in domain_pivots:
            q = " ".join([_format_search_term(strong_single), _format_search_term(dp)])
            domain_pivot_queries.append(q)

    variant_queries: List[str] = list(domain_pivot_queries)

    # (a) Drop-one: strong_terms'ten birini eksilterek varyant üret (min 2 terim şartı)
    if len(strong_terms) >= 2:
        for i in range(len(strong_terms)):
            subset = [t for j, t in enumerate(strong_terms) if j != i]
            if len(subset) < 2:
                continue
            q = " ".join(_format_search_term(t) for t in subset if t)
            if q:
                variant_queries.append(q)

    # (b) Add-one: strict_query + her other_terms elemanı (min 2 terim şartı)
    for t in other_terms:
        parts = [st for st in strict_terms if st]
        if t:
            parts.append(t)
        if len(parts) < 2:
            continue
        q = " ".join(_format_search_term(p) for p in parts)
        variant_queries.append(q)

    # (d) Paraphrase üretimi (opsiyonel, LLM ile)
    if paraphrase_count > 0:
        try:
            prompt = (
                "Verilen hukuk sorgusunu 3-5 farklı biçimde Türkçe olarak yeniden yaz. "
                "Her satıra bir varyant koy, hukuki terimleri koru, yeni terim icat etme, spam üretme.\n"
                f"Sorgu: {strict_query}\n"
                "Varyantlar:"
            )
            para_raw = _call_llm(prompt, model=llm_for_paraphrase, temperature=0.4, provider=None)
            for line in para_raw.splitlines():
                cand = line.strip().strip("-•")
                if not cand:
                    continue
                if cand in variant_queries or cand == strict_query:
                    continue
                variant_queries.append(cand)
                if len(variant_queries) >= (paraphrase_count + len(domain_pivot_queries)):
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Paraphrase üretilemedi: {exc}")

    # (c) İstersen eski article+crime, article+concept varyantlarını da
    # buraya ekleyebilirsin; ama yukarıdaki genel mantık çoğu durumu kapsıyor.

    # 4) Dedup + sınır
    seen_q = set()
    broad_queries: List[str] = []
    for q in variant_queries:
        if not q or q == strict_query:
            continue
        if q in seen_q:
            continue
        if q.count('+"') < 2:
            continue
        seen_q.add(q)
        broad_queries.append(q)
        if len(broad_queries) >= max_broad_variants:
            break

    focus_queries = _kira_focus_queries() if kira_domain else []

    return {
        "strict_query": strict_query,
        "broad_queries": broad_queries,
        "focus_queries": focus_queries,
        "keywords": keywords,
    }

# ============================================================================
# API FUNCTIONS
# ============================================================================

# Override fetch_html with retryable implementation (min 2 keyword kuralı sonrası)
def _fetch_html_impl(doc_id: str) -> str:
    payload = {"data": {"documentId": str(doc_id)}, "applicationName": "UyapMevzuat"}
    resp = SESSION.post(DOC_URL, json=payload, timeout=(CONNECT_TIMEOUT_SEC, DOC_TIMEOUT_SEC))
    resp.raise_for_status()
    text = resp.text
    try:
        data = resp.json()
        return _extract_html(data) or text
    except Exception:
        return text

if HAS_TENACITY:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_html(doc_id: str) -> str:
        return _fetch_html_impl(doc_id)
else:
    def fetch_html(doc_id: str) -> str:
        try:
            return _fetch_html_impl(doc_id)
        except requests.exceptions.Timeout as exc:
            logger.error(f"Doküman {doc_id} zaman aşımı: {exc}")
            return ""
        except requests.exceptions.RequestException as exc:
            logger.error(f"Doküman {doc_id} çekilemedi: {exc}")
            return ""

def search_yargitay(
    query: str,
    limit: int = 5,
    years_back: Optional[int] = None,
    fetch_content: bool = True,
    item_types: Optional[List[str]] = None,
    source_label: str = "Yargıtay",
    bucket: str = "unknown",
    query_signature: str = ""
):
    """Yargıtay API üzerinde arama yapar ve kararları döndürür."""
    per_page = min(limit, 100)
    
    def _build_data_block(include_item_types: bool, page_number: int):
        block = {
            "pageSize": per_page,
            "pageNumber": page_number,
            "phrase": query,
            "orderByList": [
                {"field": "kararTarihi", "order": "DESC"},
                {"field": "documentId", "order": "DESC"},
            ],
        }
        block["itemTypeList"] = item_types or ["YARGITAYKARARI"]
        if years_back:
            end_ts = time.time()
            end_date = time.strftime("%Y-%m-%dT23:59:59.000Z", time.gmtime(end_ts))
            start_ts = end_ts - years_back * 365 * 24 * 3600
            start_date = time.strftime("%Y-%m-%dT00:00:00.000Z", time.gmtime(start_ts))
            block["kararTarihiStart"] = start_date
            block["kararTarihiEnd"] = end_date
        return block

    def _extract_rows(blob):
        rows = []
        total = None
        if isinstance(blob, dict):
            data = blob.get("data")
            if isinstance(data, dict):
                if isinstance(data.get("emsalKararList"), list):
                    rows = [r for r in data["emsalKararList"] if isinstance(r, dict)]
                elif isinstance(data.get("data"), list):
                    rows = [r for r in data["data"] if isinstance(r, dict)]
                elif isinstance(data.get("results"), list):
                    rows = [r for r in data["results"] if isinstance(r, dict)]
                total = (
                    data.get("recordsTotal")
                    or data.get("totalElements")
                    or data.get("total")
                    or data.get("totalCount")
                    or data.get("recordCount")
                )
            elif isinstance(data, list):
                rows = [r for r in data if isinstance(r, dict)]
            if total is None:
                total = (
                    blob.get("recordsTotal")
                    or blob.get("totalElements")
                    or blob.get("total")
                    or blob.get("totalCount")
                )
        if isinstance(total, str) and total.isdigit():
            total = int(total)
        if total is not None and not isinstance(total, int):
            total = None
        return rows, total

    def _fetch_page(include_item_types: bool, page_number: int):
        block = _build_data_block(include_item_types, page_number=page_number)
        payload = {"applicationName": "UyapMevzuat", "paging": True, "data": block}
        for attempt in range(SEARCH_RETRY_COUNT + 1):
            try:
                resp = SESSION.post(SEARCH_URL, json=payload, timeout=(CONNECT_TIMEOUT_SEC, SEARCH_TIMEOUT_SEC), headers=BASE_HEADERS)
                resp.raise_for_status()
                blob = resp.json()
                return _extract_rows(blob)
            except requests.exceptions.ReadTimeout as exc:
                if attempt < SEARCH_RETRY_COUNT:
                    backoff = 2 ** attempt
                    logger.warning(f"Arama zaman aşımı, {attempt + 1}/{SEARCH_RETRY_COUNT} yeniden deneme {backoff}s içinde (sayfa {page_number})")
                    time.sleep(backoff)
                    continue
                logger.error(f"Arama zaman aşımı (page {page_number}) deneme bitti: {exc}")
                raise
            except Exception as exc:
                if attempt < SEARCH_RETRY_COUNT:
                    backoff = 2 ** attempt
                    logger.warning(f"Arama hatası, {attempt + 1}/{SEARCH_RETRY_COUNT} yeniden deneme {backoff}s içinde (sayfa {page_number}): {exc}")
                    time.sleep(backoff)
                    continue
                raise

    def _run(include_item_types: bool):
        collected = []
        page = 1
        total_available = None
        while len(collected) < limit:
            items, total = _fetch_page(include_item_types, page_number=page)
            page_used = page
            if page == 1 and not items and total:
                retry_items, retry_total = _fetch_page(include_item_types, page_number=0)
                if retry_items:
                    items = retry_items
                    page_used = 0
                if total is None and retry_total is not None:
                    total = retry_total
            if not items:
                logger.debug(f"Sonuç bulunamadı veya bitti (Sayfa {page_used}).")
                break
            logger.debug(f"{len(items)} karar bulundu (sayfa={page_used}, limit={per_page})")
            if total_available is None and total is not None:
                total_available = total
            for item in items:
                if not _is_supported_item(item):
                    continue
                doc_id = item.get("documentId") or item.get("id")
                if fetch_content and doc_id:
                    full_text = fetch_html(doc_id)
                    parsed = _try_parse_json(full_text)
                    if _is_metadata_error(parsed):
                        continue
                    normalized = _extract_html(parsed) or full_text
                    normalized = _html_to_text(normalized)
                else:
                    normalized = ""
                
                collected.append({
                    "esas_no": item.get("esasNo"),
                    "karar_no": item.get("kararNo"),
                    "tarih": item.get("kararTarihiStr") or item.get("kararTarihi"),
                    "daire": item.get("daireAdi") or item.get("birimAdi"),
                    "ozet": item.get("ozet"),
                    "tam_metin": normalized,
                    "kaynak": source_label,
                    "item_type": _item_type(item),
                    "document_id": doc_id,
                    "bucket": bucket,
                    "query_signature": query_signature,
                    "view_url": (VIEW_URL.format(id=doc_id) if doc_id else "") + (
                        f"?query={quote(query_signature)}" if query_signature and doc_id else ""
                    ),
                })
                if len(collected) >= limit:
                    break
            if total_available is not None and len(collected) >= min(limit, total_available):
                break
            if len(items) < per_page:
                break
            page += 1
        return collected

    logger.info(f"Arama yapılıyor: {query} ({source_label}, bucket={bucket})")
    return _run(include_item_types=True)


def enrich_full_texts(docs: List[Dict[str, Any]], limit: int, max_workers: Optional[int] = None) -> List[Dict[str, Any]]:
    """Metadata listesine göre tam metinleri yeniden çeker (paralel)."""
    if max_workers is None:
        max_workers = int(os.environ.get("FULLTEXT_WORKERS", "12"))
    targets = docs[:limit]
    results: List[Optional[Dict[str, Any]]] = [None] * len(targets)

    def _fetch(idx_doc: Tuple[int, Dict[str, Any]]):
        idx, doc = idx_doc
        did = doc.get("document_id")
        if not did:
            return idx, doc
        full_text = fetch_html(did)
        parsed = _try_parse_json(full_text)
        if _is_metadata_error(parsed):
            return idx, doc
        normalized = _extract_html(parsed) or full_text
        normalized = _html_to_text(normalized)
        doc_copy = dict(doc)
        doc_copy["tam_metin"] = normalized
        return idx, doc_copy

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch, (i, d)) for i, d in enumerate(targets)]
        for future in as_completed(futures):
            idx, updated_doc = future.result()
            results[idx] = updated_doc

    enriched: List[Dict[str, Any]] = []
    for i, doc in enumerate(targets):
        enriched.append(results[i] if results[i] is not None else doc)
    return enriched


# Basit async varyant: paralel meta ve fulltext çekmek için httpx.AsyncClient kullanımı
async def async_search_yargitay(client, query: str, *, limit: int, years_back: Optional[int], item_types: List[str],
                                source_label: str, bucket: str, query_signature: str, fetch_content: bool):
    """httpx.AsyncClient ile arama (fetch_content True ise yavaş olur)."""
    per_page = min(limit, 100)

    async def _build_data_block(include_item_types: bool, page_number: int):
        block = {
            "pageSize": per_page,
            "pageNumber": page_number,
            "phrase": query,
            "orderByList": [
                {"field": "kararTarihi", "order": "DESC"},
                {"field": "documentId", "order": "DESC"},
            ],
        }
        block["itemTypeList"] = item_types or ["YARGITAYKARARI"]
        if years_back:
            end_ts = time.time()
            end_date = time.strftime("%Y-%m-%dT23:59:59.000Z", time.gmtime(end_ts))
            start_ts = end_ts - years_back * 365 * 24 * 3600
            start_date = time.strftime("%Y-%m-%dT00:00:00.000Z", time.gmtime(start_ts))
            block["kararTarihiStart"] = start_date
            block["kararTarihiEnd"] = end_date
        return block

    async def _extract_rows_async(blob: dict) -> Tuple[list, Optional[int]]:
        total = None
        rows = []
        data = blob.get("data") or blob
        if isinstance(data, dict):
            if isinstance(data.get("emsalKararList"), list):
                rows = [r for r in data["emsalKararList"] if isinstance(r, dict)]
            elif isinstance(data.get("data"), list):
                rows = [r for r in data["data"] if isinstance(r, dict)]
            elif isinstance(data.get("results"), list):
                rows = [r for r in data["results"] if isinstance(r, dict)]
            else:
                items = data.get("list") or data.get("content") or data.get("items") or []
                rows = [r for r in items if isinstance(r, dict)]
            total = (
                data.get("recordsTotal")
                or data.get("totalElements")
                or data.get("total")
                or data.get("totalCount")
                or data.get("recordCount")
            )
        elif isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        if isinstance(total, str) and total.isdigit():
            total = int(total)
        if total is not None and not isinstance(total, int):
            total = None
        return rows, total

    async def _fetch_page(page_number: int):
        block = await _build_data_block(True, page_number=page_number)
        payload = {"applicationName": "UyapMevzuat", "paging": True, "data": block}
        resp = await client.post(SEARCH_URL, json=payload, timeout=20)
        resp.raise_for_status()
        blob = resp.json()
        return await _extract_rows_async(blob)

    collected = []
    page = 1
    total_available = None
    while len(collected) < limit:
        items, total = await _fetch_page(page_number=page)
        if not items:
            break
        if total_available is None and total is not None:
            total_available = total
        for item in items:
            if not _is_supported_item(item):
                continue
            doc_id = item.get("documentId") or item.get("id")
            normalized = ""
            if fetch_content and doc_id:
                full_text = fetch_html(doc_id)
                parsed = _try_parse_json(full_text)
                if _is_metadata_error(parsed):
                    continue
                normalized = _extract_html(parsed) or full_text
                normalized = _html_to_text(normalized)

            collected.append({
                "esas_no": item.get("esasNo"),
                "karar_no": item.get("kararNo"),
                "tarih": item.get("kararTarihiStr") or item.get("kararTarihi"),
                "daire": item.get("daireAdi") or item.get("birimAdi"),
                "ozet": item.get("ozet"),
                "tam_metin": normalized,
                "kaynak": source_label,
                "item_type": _item_type(item),
                "document_id": doc_id,
                "bucket": bucket,
                "query_signature": query_signature,
                "view_url": (VIEW_URL.format(id=doc_id) if doc_id else "") + (
                    f"?query={quote(query_signature)}" if query_signature and doc_id else ""
                ),
            })
            if len(collected) >= limit:
                break
        if total_available is not None and len(collected) >= min(limit, total_available):
            break
        if len(items) < per_page:
            break
        page += 1
    return collected

# ============================================================================
# MADDE 4: KARARI JSON'A PARSE ETME VE PASSAGE'LARA BÖLME
# ============================================================================

def parse_decision(raw_text: str, doc_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Yargıtay kararını JSON'a parse eder ve passage'lara böler.
    """
    if not raw_text:
        return {
            "id": doc_id,
            "court": metadata.get("daire", ""),
            "date": metadata.get("tarih", ""),
            "case_no": metadata.get("esas_no", ""),
            "decision_no": metadata.get("karar_no", ""),
            "sections": [],
            "passages": [],
            "metadata": metadata
        }
    
    sections: List[Dict[str, Any]] = []
    passages: List[Dict[str, Any]] = []
    
    # Pattern bazlı bölme
    patterns = {
        "head": r"^(.*?)(?=(?:GEREĞİ DÜŞÜNÜLDÜ|Oluş ve dosya|KARAR))",
        "facts": r"(?:Oluş ve dosya içeriğine göre|GEREĞİ DÜŞÜNÜLDÜ)[:\s]*(.*?)(?=(?:SONUÇ|KARAR|Açıklanan|Yerel mahkeme))",
        "reasoning": r"(?:Yerel mahkeme kararının|incelenmesinde)[:\s]*(.*?)(?=(?:SONUÇ|KARAR|Bu itibarla))",
        "disposition": r"(?:SONUÇ|KARAR)[:\s]*(.*?)$"
    }
    
    for section_name, pattern in patterns.items():
        match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else match.group(0).strip()
            if text:
                # Basit token sayımı (kelime bazlı)
                token_count = len(text.split())
                sections.append({
                    "name": section_name,
                    "text": text,
                    "token_count": token_count
                })
                # 300-400 kelimelik pasajlar üret
                words = text.split()
                chunk_size = 350
                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i+chunk_size]
                    if not chunk_words:
                        continue
                    start = i
                    end = i + len(chunk_words)
                    passages.append({
                        "name": section_name,
                        "start": start,
                        "end": end,
                        "text": " ".join(chunk_words),
                    })
    
    # Pattern tutmadıysa fallback: Her ~600 kelimede bir böl
    if not sections:
        words = raw_text.split()
        chunk_size = 600
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            sections.append({
                "name": f"chunk_{i//chunk_size}",
                "text": chunk,
                "token_count": len(chunk.split())
            })
            # fallback pasajlar
            passages.append({
                "name": f"chunk_{i//chunk_size}",
                "start": 0,
                "end": len(chunk.split()),
                "text": chunk,
            })
    
    return {
        "id": doc_id,
        "court": metadata.get("daire", ""),
        "date": metadata.get("tarih", ""),
        "case_no": metadata.get("esas_no", ""),
        "decision_no": metadata.get("karar_no", ""),
        "sections": sections,
        "passages": passages,
        "metadata": metadata
    }

# ============================================================================
# LLM FUNCTIONS
# ============================================================================

def _call_ollama(prompt: str, model: str = OLLAMA_MODEL, temperature: float = 0.2, timeout: int = 120) -> str:
    """Ollama API çağrısı."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or data.get("data") or "").strip()
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        return ""

def _call_chatgpt(prompt: str, model: str = CHAT_GPT_MODEL, temperature: float = 0.2, timeout: int = 120) -> str:
    """OpenAI ChatGPT API çağrısı."""
    if not CHAT_GPT_API_KEY:
        return ""
    headers = {
        "Authorization": f"Bearer {CHAT_GPT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "top_p": 0.1,
        "presence_penalty": 0,
        "messages": [
            {"role": "system", "content": "You are a helpful Turkish legal research assistant."},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        resp = requests.post(OPENAI_CHAT_URL, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if choices:
            return (choices[0].get("message", {}).get("content") or "").strip()
    except Exception as e:
        logger.error(f"OpenAI ChatGPT API error: {e}")
        return ""
    return ""

def _call_llm(prompt: str, model: Optional[str] = None, temperature: float = 0.2, 
              timeout: int = 120, provider: Optional[str] = None) -> str:
    """Seçili LLM sağlayıcısını kullanarak prompt için cevap alır (varsayılan Ollama)."""
    if provider is None:
        provider = SELECTED_LLM_PROVIDER or "ollama"
    if model is None:
        model = CHAT_GPT_MODEL if provider == "openai" else OLLAMA_MODEL
    logger.info(f"LLM provider={provider}, model={model}")
    if provider == "openai":
        return _call_chatgpt(prompt, model=model, temperature=temperature, timeout=timeout)
    else:
        return _call_ollama(prompt, model=model, temperature=temperature, timeout=timeout)


def _strip_json_markers(text: str) -> str:
    """```, ```json gibi blok işaretlerini temizler."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r'^```(?:json)?\s*', '', t)
        t = re.sub(r'\s*```$', '', t)
    return t.strip()


def _safe_json_loads(raw: str):
    """JSON yüklemeyi dener; başarısız olursa None döner."""
    try:
        return json.loads(raw)
    except Exception:
        return None


def _repair_json_with_llm(raw_response: str, schema_hint: str, temperature: float = 0.0) -> Optional[dict]:
    """
    İlk parse başarısız olduğunda, LLM'den sadece geçerli JSON üretmesini ister.
    schema_hint: Beklenen alanları anlatan kısa metin.
    """
    repair_prompt = (
        "Aşağıda hatalı veya eksik JSON var. Sadece geçerli JSON döndür.\n"
        f"Şema ipucu: {schema_hint}\n"
        "Kod bloğu veya açıklama yazma, direkt JSON ile yanıtla.\n\n"
        f"Hatalı JSON:\n{raw_response}\n\n"
        "Geçerli JSON:"
    )
    fixed = _call_llm(repair_prompt, temperature=temperature)
    fixed = _strip_json_markers(fixed)
    return _safe_json_loads(fixed)

def extract_law_articles_from_text(text: str) -> List[str]:
    """
    Metinden deterministik olarak kanun maddelerini çıkarır (LLM'den bağımsız).
    Ör: "TCK 150/1", "CMK 223" vb.
    """
    matches = LAW_PATTERN.findall(text)
    articles: List[str] = []
    seen = set()
    for article in matches:
        art = article.strip()
        key = art.lower()
        if art and key not in seen:
            articles.append(art)
            seen.add(key)
    return articles

def _extract_keywords_with_llm(description: str) -> List[str]:
    """
    LLM ile metinden kritik 3-4 hukuki anahtar kavramı çıkarır.
    """
    prompt = (
        "Türkçe bir hukuki soru/veri verilecektir. Görevlerin:\n"
        "1) En kritik 3 veya 4 hukuki anahtar kavramı seçmek.\n"
        "2) Soru içinde yer alan spesifik hakaret/tehdit/alıntı ifadeleri (örn. 'ibne') de anahtar kelime olarak eklemek.\n\n"
        "ÖNCELİK SIRASI:\n"
        "- Suç isimleri (örn: nitelikli yağma, hakaret, dolandırıcılık)\n"
        "- Usul terimleri (örn: takipsizlik, temyiz, istinaf)\n"
        "- Hukuki kavramlar ve talepler (örn: hukuki alacağın tahsili, kira artış oranı, maddi tazminat, manevi tazminat)\n"
        "- Soru içinde geçen spesifik hakaret/tehdit kelimeleri (örn: 'ibne', 'şerefsiz')\n\n"
        "SPESİFİK KAVRAM KURALI:\n"
        "- Mümkün olduğunca 2-3 kelimelik spesifik kavramlar seç.\n"
        "- GENEL kelimeleri mümkünse seçme: 'yasal', 'zam', 'durum', 'dava', 'mahkeme' gibi.\n"
        "- ÖRNEK YANLIŞ: ['kira', 'zam', 'yasal']\n"
        "- ÖRNEK DOĞRU: ['kira artış oranı', 'işyeri kira sözleşmesi']\n\n"
        "LITERAL İFADE KURALI:\n"
        "- Soru hakaret içeriyorsa, hakaret kelimesini AYNEN listeye ekle.\n"
        "- Örnek: 'Bana ibne dedi, hakaret olur mu?' → anahtar kelimelerden biri mutlaka 'ibne' olmalıdır.\n"
        "- Tırnak içinde verilen kısa ifadeleri de (\"...\") anahtar kelime olarak düşünebilirsin.\n\n"
        "NOT:\n"
        "- Kanun maddelerini (TCK 150/1 gibi) ekleme, bunlar ayrı bir katmanda tespit edilecek.\n"
        "- Türkçe karakterleri düzeltme, metindeki doğru haliyle yaz.\n\n"
        "ÇIKTI FORMATI:\n"
        "- Sadece JSON dizisi döndür: [\"kelime1\", \"kelime2\", \"kelime3\"]\n"
        "- Başka açıklama veya metin yazma.\n\n"
        f"METİN:\n{description.strip()}\n\n"
        "ÇIKTI:"
    )
    response = _call_llm(prompt, temperature=0.0)
    return _parse_keyword_array(response)

def _parse_keyword_array(raw: str) -> List[str]:
    """LLM çıktısından JSON array parse eder."""
    if not isinstance(raw, str):
        return []
    txt = raw.strip()
    try:
        arr = json.loads(txt)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if x]
    except Exception:
        pass
    match = re.search(r"\[(.*?)\]", txt, flags=re.S)
    if not match:
        return []
    try:
        arr = json.loads(f"[{match.group(1)}]")
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if x]
    except Exception:
        return []
    return []

# ============================================================================
# EMSAL SEÇİCİ KATMAN (Deterministik)
# ============================================================================

def pick_nearest_cases(decision_cards: List[Dict[str, Any]], max_cases: int = 3) -> List[Dict[str, Any]]:
    """
    Decision cards'tan en yakın emsalleri deterministik olarak seçer.
    LLM hiç emsal döndürmese bile, mutlaka birkaç yakın karar gösterilir.
    """
    # 1) Önce gerçekten "ilgili" işaretlenen kartlar
    relevant = [c for c in decision_cards if c.get("is_relevant_to_question")]
    
    # 2) Hiç yoksa, TCK 150/1 içeren kartlardan birkaçını seç
    if not relevant:
        candidates = []
        for c in decision_cards:
            text_blob = (c.get("facts_short", "") + " " + 
                         c.get("reasoning_short", "") + " " + 
                         " ".join(c.get("key_points", [])))
            if "150/1" in text_blob or "TCK 150/1" in text_blob:
                candidates.append(c)
        relevant = candidates
    
    # 3) Yine de boşsa, ilk N kartı al (son çare)
    if not relevant:
        relevant = decision_cards[:max_cases]
    
    # 4) Max cases'e kadar sınırla
    relevant = relevant[:max_cases]
    
    # 5) cases_used formatına çevir
    cases_used = []
    for c in relevant:
        reasoning = c.get("reasoning_short", "")[:200] or "Soru ile ilgili yakın emsal"
        cases_used.append({
            "id": c["id"],
            "citation": c["citation"],
            "key_role": reasoning,
            "view_url": c.get("view_url")
        })
    
    return cases_used

def compute_verdict_from_cards(decision_cards: List[Dict[str, Any]]) -> str:
    """
    Decision cards'taki result_for_question değerlerinden oy mantığıyla verdict hesaplar.
    """
    yes = no = 0
    for c in decision_cards:
        if not c.get("is_relevant_to_question"):
            continue
        res = c.get("result_for_question")
        if res == "supports_yes":
            yes += 1
        elif res == "supports_no":
            no += 1
    
    if yes == 0 and no == 0:
        return "belirsiz"
    if yes > 0 and no == 0:
        return "uygulanabilir"
    if no > 0 and yes == 0:
        return "uygulanamaz"
    # Çelişkili durum
    return "belirsiz"

# ============================================================================
# MADDE 5: İKİ AŞAMALI (MAP-REDUCE) LLM ANALİZİ
# ============================================================================

def summarize_decision(decision_json: Dict[str, Any], question: str) -> Dict[str, Any]:
    """
    Tek bir kararı özetler (MAP aşaması).
    
    Örnek çıktı:
    {
      "id": "...",
      "citation": "Yargıtay 6. CD, 20.12.2017, 2014/12186 E., 2017/6207 K.",
      "is_relevant_to_question": true,
      "result_for_question": "supports_yes" | "supports_no" | "unclear" | "not_relevant",
      "facts_short": "...",
      "reasoning_short": "...",
      "key_points": ["...", "..."]
    }
    """
    # Facts ve reasoning bölümlerini al
    # Pasaj seçimi: mevcut reranker ile en iyi 2 pasajı al, yoksa sections fallback
    passages = decision_json.get("passages") or []
    selected_passages: List[str] = []
    fallback_facts = ""
    fallback_reasoning = ""
    if passages:
        texts = [p.get("text", "")[:800] for p in passages]
        # Reranker varsa onu kullan; yoksa lexical fallback zaten rerank_docs içinde
        ordered_docs = rerank_docs(question, [{"tam_metin": t} for t in texts], top_n=min(2, len(texts)))
        ranked_texts = [doc.get("tam_metin", "") for doc in ordered_docs]
        selected_passages = [t for t in ranked_texts if t][:2]
        # Eğer hala boşsa lexical fallback ile manuel seç
        if not selected_passages:
            scored = sorted(passages, key=lambda p: _lexical_overlap_score(question, p.get("text", "")), reverse=True)
            selected_passages = [p.get("text", "") for p in scored[:2] if p.get("text")]
    if not selected_passages:
        for section in decision_json.get("sections", []):
            if section["name"] == "facts":
                fallback_facts = section["text"][:1000]  # İlk 1000 karakter
            elif section["name"] == "reasoning":
                fallback_reasoning = section["text"][:1500]  # İlk 1500 karakter
        
        # Eğer pattern tutmadıysa ilk chunk'ı kullan
        sections = decision_json.get("sections") or []
        if not fallback_facts and not fallback_reasoning:
            first_section = sections[0] if sections else {"text": ""}
            fallback_facts = first_section.get("text", "")[:2000]
        selected_passages = [fallback_facts, fallback_reasoning]
    
    context = "\n\n".join(p for p in selected_passages if p)
    
    prompt = (
        "Aşağıda bir Yargıtay kararının bir kısmı verilmiştir.\n"
        "Sadece bu kararın metnine dayanarak aşağıdaki JSON formatını doldur.\n\n"
        "KURALLAR:\n"
        "- Yalnızca bu kararın metnindeki bilgileri kullan, dış bilgi ekleme.\n"
        "- Karar soruyla ilgili değilse is_relevant_to_question = false olarak işaretle.\n"
        "- result_for_question alanı: supports_yes/supports_no/unclear/not_relevant seçeneklerinden biri olmalı.\n"
        "- key_points: Bu karardan çıkan 2-3 önemli hukuki sonucu yaz.\n"
        "- evidence: metinden bire bir alıntı yap ve char_start/char_end pozisyonunu kelime indeksine göre ver.\n\n"
        "ÇOK ÖNEMLİ - ÇIKTI FORMATI:\n"
        "- SADECE JSON döndür, başka hiçbir metin ekleme\n"
        "- Markdown code block (```) kullanma\n"
        "- Açıklama ekleme, direkt JSON ile başla\n\n"
        f"SORU: {question}\n\n"
        f"KARAR METNİ:\n{context}\n\n"
        "ÇIKTI ŞU FORMATTA OLMALI (SADECE BU JSON):\n"
        "{\n"
        '  "is_relevant_to_question": true,\n'
        '  "result_for_question": "supports_yes",\n'
        '  "facts_short": "...",\n'
        '  "reasoning_short": "...",\n'
        '  "key_points": ["...", "..."],\n'
        '  "evidence": [{"quote": "...", "char_start": 10, "char_end": 40}]\n'
        "}\n"
    )
    
    response = _call_llm(prompt, temperature=0.1, timeout=60)
    
    # JSON parse + onarım
    result = None
    response_clean = _strip_json_markers(response)
    parsed = _safe_json_loads(response_clean)
    if isinstance(parsed, dict):
        result = parsed
    else:
        repaired = _repair_json_with_llm(
            response,
            schema_hint="is_relevant_to_question (bool), result_for_question, facts_short, reasoning_short, key_points (list), evidence (list of {quote,char_start,char_end})",
            temperature=0.0,
        )
        if isinstance(repaired, dict):
            result = repaired
    
    if not isinstance(result, dict):
        logger.error("summarize_decision JSON parse başarısız, fallback kullanılıyor")
        result = {
            "is_relevant_to_question": False,
            "result_for_question": "unclear",
            "facts_short": (fallback_facts or (selected_passages[0] if selected_passages else ""))[:200],
            "reasoning_short": (fallback_reasoning or (selected_passages[1] if len(selected_passages) > 1 else ""))[:200],
            "key_points": [],
            "evidence": []
        }
    
    # ID ve citation ekle
    decision_id = decision_json["id"]
    court = decision_json.get("court", "Bilinmeyen Daire")
    date = decision_json.get("date", "")
    case_no = decision_json.get("case_no", "")
    decision_no = decision_json.get("decision_no", "")
    
    citation = f"Yargıtay {court}, {date}, {case_no} E., {decision_no} K."
    
    result["id"] = decision_id
    result["citation"] = citation
    # Evidence default
    if "evidence" not in result or not isinstance(result.get("evidence"), list):
        result["evidence"] = []
    # LLM'ye verilen context'i karta ekle (evidence doğrulaması için)
    result["context_text"] = context
    # Link ve bucket bilgisi ekle
    meta = decision_json.get("metadata") or {}
    if meta.get("view_url"):
        result["view_url"] = meta.get("view_url")
    if meta.get("bucket"):
        result["bucket"] = meta.get("bucket")
    
    return result

def fetch_rule_cards(query: str, top_k: int = RULE_CARD_TOP_K) -> List[Dict[str, Any]]:
    """
    rule_cards koleksiyonundan semantik olarak en yakın kartları çeker.
    rule alanı boş olan kartlar filtrelenir.
    """
    try:
        model = SentenceTransformer(RULE_CARD_MODEL, device=RULE_CARD_DEVICE)
        client = QdrantClient(RULE_CARD_QDRANT_URL)
        vec = model.encode([query], normalize_embeddings=True)[0].tolist()
        res = client.query_points(
            collection_name=RULE_CARD_COLLECTION,
            query=vec,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        ).points
    except Exception as e:  # noqa: BLE001
        logger.error(f"Rule card fetch hatası: {e}")
        return []

    cards: List[Dict[str, Any]] = []
    for p in res:
        payload = p.payload or {}
        rule_text = (payload.get("rule") or "").strip()
        if not rule_text:
            continue
        card = dict(payload)
        card["card_id"] = str(p.id)
        card["score"] = p.score
        cards.append(card)
    return cards

def aggregate_decisions(decision_cards: List[Dict[str, Any]], question: str, rule_cards: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Karar kartlarını birleştirerek final cevabı üretir (REDUCE aşaması).
    SADECE is_relevant_to_question=true kartları kullanır.
    
    Çıktı formatı (Madde 6: Kaynak-iddia eşleştirmesi):
    {
      "verdict": "uygulanabilir" | "uygulanamaz" | "belirsiz",
      "reasoning": [
        {
          "text": "...",
          "supporting_cases": ["YARGITAY-6CD-2014-12186-2017-6207"]
        }
      ],
      "cases_used": [...]
    }
    """
    # YENİ: Önce sadece ilgili kartları al
    relevant_cards = [c for c in decision_cards if c.get("is_relevant_to_question")]
    
    # Hiç ilgili kart yoksa LLM'yi konuşturup saçmalatmaya gerek yok
    if not relevant_cards:
        return {
            "verdict": "belirsiz",
            "reasoning": [],
            "cases_used": []
        }
    
    # Eski behaviour: ama artık bütün kartlar yerine sadece relevant_cards
    cards_summary = json.dumps(relevant_cards, ensure_ascii=False, indent=2)
    rule_cards = rule_cards or []
    rule_cards_summary = json.dumps(rule_cards, ensure_ascii=False, indent=2)
    
    prompt = (
        "Aşağıda bir hukuki soru, İLGİLİ Yargıtay kararlarının özetleri ve aynı issue için rule_cards koleksiyonundan çekilmiş kural kartları verilmiştir.\n"
        "Sadece bu kararlara ve kural kartlarına dayanarak soruya net bir cevap ver.\n\n"
        
        "KURALLAR:\n"
        "- SADECE verilen karar ve kural kartlarındaki bilgilere dayan; dış bilgi ekleme.\n"
        "- Soruya net bir sonuç ver: uygulanabilir / uygulanamaz / belirsiz.\n"
        "- Karar özetlerindeki result_for_question değerlerine bakarak çoğunluğu hesapla:\n"
        "  * supports_yes çoğunlukta → uygulanabilir\n"
        "  * supports_no çoğunlukta → uygulanamaz\n"
        "  * Eşit veya belirsiz → belirsiz\n"
        "- Kural kartlarını (issue, rule, exceptions, citations) dikkate al; gerekçe maddesinde en az bir kural kartı referansı (card_id veya citation) ve buna karşılık gelen karar id'lerini birlikte ver.\n"
        "- Her gerekçe maddesi için en az bir supporting_cases ID'si vermek ZORUNLU (boş olamaz).\n"
        "- Kartlarda olmayan yeni iddia veya kaynak üretme; sadece mevcut kart id'lerini kullan.\n\n"
        
        "ÇOK ÖNEMLİ - ÇIKTI FORMATI:\n"
        "- SADECE JSON döndür, başka hiçbir metin ekleme; Markdown code block (```) kullanma.\n"
        "- reasoning maddelerinde kural kartı referansını (card_id veya citation) metne dahil et ve hangi karar id'leriyle desteklendiğini yaz.\n\n"
        
        f"SORU:\n{question}\n\n"
        f"İLGİLİ KARAR ÖZETLERİ ({len(relevant_cards)} karar):\n{cards_summary}\n\n"
        f"KURAL KARTLARI ({len(rule_cards)} adet, rule_cards koleksiyonundan):\n{rule_cards_summary}\n\n"
        
        "ÇIKTI ŞU FORMATTA OLMALI (SADECE BU JSON, BAŞKA HİÇBİR ŞEY):\n"
        "{\n"
        '  "verdict": "uygulanabilir",\n'
        '  "reasoning": [\n'
        '    {\n'
        '      "text": "... kural kartı referansı (card_id veya citation) + karar id\'leri ...",\n'
        '      "supporting_cases": ["karar_id_1", "karar_id_2"]\n'
        '    }\n'
        '  ],\n'
        '  "cases_used": [\n'
        '    {\n'
        '      "id": "karar_id_1",\n'
        '      "citation": "...",\n'
        '      "key_role": "..."\n'
        '    }\n'
        '  ]\n'
        "}\n"
    )
    
    response = _call_llm(prompt, temperature=0.1, timeout=90)
    
    # JSON parse + onarım
    response_clean = _strip_json_markers(response)
    result = _safe_json_loads(response_clean)
    if not isinstance(result, dict):
        repaired = _repair_json_with_llm(
            response,
            schema_hint='verdict (uygulanabilir|uygulanamaz|belirsiz), reasoning:[{text,supporting_cases}], cases_used:[{id,citation,key_role}]',
            temperature=0.0,
        )
        if isinstance(repaired, dict):
            result = repaired
    
    if not isinstance(result, dict):
        logger.error("aggregate_decisions JSON parse hatası, fallback kullanılıyor")
        logger.error(f"LLM response: {response[:500]}")
        result = {
            "verdict": "belirsiz",
            "reasoning": [{
                "text": "LLM yanıtı parse edilemedi.",
                "supporting_cases": []
            }],
            "cases_used": []
        }
    
    return result

# ============================================================================
# MADDE 7: AYRI BİR LLM ÇAĞRISIYLA HALÜSİNASYON KONTROLÜ
# ============================================================================

def verify_answer(question: str, decision_cards: List[Dict[str, Any]], 
                  draft_final_answer: Dict[str, Any]) -> Dict[str, Any]:
    """
    Draft final answer'ı doğrular, halüsinasyon içeren kısımları temizler.
    SADECE is_relevant_to_question=true kartları kullanır.
    """
    relevant_cards = [c for c in decision_cards if c.get("is_relevant_to_question")]
    cards_for_verify = relevant_cards or decision_cards  # hiç ilgili yoksa tüm listeyi kullan
    
    cards_summary = json.dumps(cards_for_verify, ensure_ascii=False, indent=2)
    draft_summary = json.dumps(draft_final_answer, ensure_ascii=False, indent=2)
    
    prompt = (
        "Bir hukuki soruya verilen taslak cevabı doğrulayacaksın.\n"
        "Taslak cevaptaki her gerekçe maddesinin, KARAR ÖZETLERİ içinde açık bir dayanağı olup olmadığını kontrol et.\n\n"
        
        "GÖREV:\n"
        "- Dayanağı olmayan gerekçe maddelerini çıkar veya işaretle\n"
        "- supporting_cases ID'lerinin karar özetleri içinde gerçekten var olduğunu kontrol et\n"
        "- is_relevant_to_question = false olan kartları supporting_cases listesinden çıkar\n"
        "- Kartlarda olmayan yeni iddia veya kaynak üretme\n"
        "- Çıktıyı aynı JSON formatında döndür\n\n"
        
        "ÇOK ÖNEMLİ - ÇIKTI FORMATI:\n"
        "- SADECE JSON döndür, başka hiçbir metin ekleme\n"
        "- Markdown code block (```) kullanma\n"
        "- Açıklama ekleme, direkt JSON ile başla\n\n"
        
        f"SORU:\n{question}\n\n"
        f"İLGİLİ KARAR ÖZETLERİ:\n{cards_summary}\n\n"
        f"TASLAK CEVAP:\n{draft_summary}\n\n"
        
        "ÇIKTI (doğrulanmış JSON, SADECE BU):\n"
    )
    
    response = _call_llm(prompt, temperature=0.0, timeout=60)
    
    # JSON parse + onarım
    response_clean = _strip_json_markers(response)
    result = _safe_json_loads(response_clean)
    if not isinstance(result, dict):
        repaired = _repair_json_with_llm(
            response,
            schema_hint='verdict, reasoning (list), cases_used (list), supporting_cases id\'leri',
            temperature=0.0,
        )
        if isinstance(repaired, dict):
            result = repaired
    
    if not isinstance(result, dict):
        logger.error("verify_answer JSON parse hatası, fallback (draft) kullanılıyor")
        logger.error(f"LLM response: {response[:500]}")
        # Fallback: draft'ı aynen döndür
        result = draft_final_answer
    
    # Evidence doğrulaması: her karar kartındaki alıntı LLM'ye verilen context'te geçiyor mu?
    for card in decision_cards:
        evidences = card.get("evidence") or []
        ctx = card.get("context_text") or ""
        if not ctx:
            passages = card.get("passages") or []
            ctx = " ".join(p.get("text", "") for p in passages)
        if not ctx:
            ctx = (card.get("facts_short", "") + " " + card.get("reasoning_short", ""))
        valid_evidence = []
        for ev in evidences:
            quote_text = ev.get("quote") or ""
            start = ev.get("char_start") if ev.get("char_start") is not None else ev.get("start")
            end = ev.get("char_end") if ev.get("char_end") is not None else ev.get("end")
            if not quote_text:
                continue
            if isinstance(start, int) and isinstance(end, int) and start >= 0 and end > start and end <= len(ctx):
                span_text = ctx[start:end]
                if quote_text in span_text:
                    valid_evidence.append(ev)
                    continue
            if quote_text in ctx:
                valid_evidence.append(ev)
        card["evidence"] = valid_evidence
    return result

# ============================================================================
# MADDE 8: CLI/API ÇIKTI FORMATI STANDARDİZASYONU
# ============================================================================

def format_legal_output(verified_answer: Dict[str, Any], question: str) -> str:
    """
    Doğrulanmış cevabı hukukçunun akışına göre formatlar.
    
    Bölümler:
    1. Sonuç
    2. Gerekçe
    3. Dayanak Kararlar
    4. Notlar / Sınırlar
    """
    output_lines = []
    
    # 1. Sonuç
    verdict = verified_answer.get("verdict", "belirsiz")
    verdict_text = {
        "uygulanabilir": "olumlu",
        "uygulanamaz": "olumsuz",
        "belirsiz": "belirsiz"
    }.get(verdict, "belirsiz")
    
    # Sorudan ilk 100 karakteri al (özet için)
    question_short = question[:100] + "..." if len(question) > 100 else question
    
    output_lines.append("=" * 70)
    output_lines.append("SONUÇ")
    output_lines.append("=" * 70)
    output_lines.append(f"Soru: {question_short}")
    output_lines.append(f"\nSomut olayda mevcut kararlara göre sorudaki hukuki sonuç {verdict_text} görünmektedir.")
    output_lines.append("")
    
    # 2. Gerekçe
    output_lines.append("=" * 70)
    output_lines.append("GEREKÇE")
    output_lines.append("=" * 70)
    
    reasoning = verified_answer.get("reasoning", [])
    if not reasoning:
        output_lines.append("Destekleyen gerekçe bulunamadı; yeterli kaynak yok.")
        output_lines.append("")
    for i, item in enumerate(reasoning, 1):
        text = item.get("text", "")
        cases = item.get("supporting_cases", [])
        cases_str = ", ".join(cases) if cases else "[Kaynak belirtilmemiş]"
        output_lines.append(f"{i}. {text}")
        output_lines.append(f"   Dayanak: {cases_str}")
        output_lines.append("")
    
    # 3. Dayanak Kararlar
    output_lines.append("=" * 70)
    output_lines.append("DAYANAK KARARLAR")
    output_lines.append("=" * 70)
    
    cases_used = verified_answer.get("cases_used", [])
    if not cases_used:
        output_lines.append("Hiç karar kaynağı bulunamadı; lütfen farklı ifadelerle tekrar deneyin.")
        output_lines.append("")
    for case in cases_used:
        citation = case.get("citation", "")
        key_role = case.get("key_role", "")
        url = case.get("url") or case.get("view_url") or ""
        bucket = case.get("bucket")
        bucket_tag = f" [{bucket}]" if bucket else ""
        output_lines.append(f"• {citation}{bucket_tag}")
        if url:
            output_lines.append(f"  Link: {url}")
        output_lines.append(f"  Rolü: {key_role}")
        output_lines.append("")
    
    # 4. Notlar / Sınırlar
    output_lines.append("=" * 70)
    output_lines.append("NOTLAR / SINIRLAR")
    output_lines.append("=" * 70)
    
    # Verdict'e göre not ekle
    if verdict == "belirsiz":
        output_lines.append("Bu soruya bire bir uyan içtihat bulunmamaktadır.")
        output_lines.append("Yukarıdaki kararlar ilgili konular bakımından en yakın emsal niteliğindedir.")
    else:
        output_lines.append("Bu soruya en yakın görülen kararlar esas alınmıştır.")
    
    output_lines.append("Somut olayın tüm detaylarına göre değerlendirme yapılması önerilir.")
    output_lines.append("=" * 70)
    
    return "\n".join(output_lines)

# ============================================================================
# PIPELINE FUNCTIONS
# ============================================================================

def run_llm_pipeline(
    question: str,
    limit: int = 100,
    years_back: Optional[int] = 15,
    sources: Optional[List[str]] = None,
    output_base_dir: str = "tests/docs",
    no_answer_threshold: float = 0.0,
) -> Dict[str, Any]:
    """LLM pipeline: Soru -> Anahtar kelime -> Arama -> Analiz adımlarını yürütür."""
    
    safe_print("═" * 70)
    safe_print("🔍 YARGITAY KARAR ARAMA SİSTEMİ v3.2")
    safe_print("═" * 70)
    safe_print(f"\n📝 Soru: \"{question.strip()}\"")
    
    t_pipeline_start = time.time()
    
    # 1. Anahtar kelime çıkarma
    safe_print("\n🤖 Anahtar Kelime Çıkarımı...")
    
    # Önce deterministik olarak kanun maddelerini çek
    law_articles = extract_law_articles_from_text(question)
    safe_print(f"   ✓ Deterministik Kanun Maddeleri: {', '.join(law_articles) if law_articles else 'Yok'}")
    
    # Sorudan deterministik literal / özel ifadeleri çıkar
    literal_keywords = extract_literal_keywords_from_question(question)
    safe_print(f"   ✓ Literal İfadeler: {', '.join(literal_keywords) if literal_keywords else 'Yok'}")
    
    # Sonra LLM ile diğer terimleri çek
    raw_keywords = _extract_keywords_with_llm(question)
    
    # Normalizasyon + deduplikasyon
    keyword_objects: List[Dict[str, Any]] = []
    seen_texts = set()
    
    # Kanun maddeleri
    for art in law_articles:
        norm = normalize_legal_term(art)
        key = norm.lower()
        if key in seen_texts:
            continue
        seen_texts.add(key)
        keyword_objects.append(
            create_keyword_object(
                norm,
                llm_confidence=1.0,
                keyword_type="article",
                source="law_article",
            )
        )
    
    # LLM'den gelen kelimeler
    for kw in raw_keywords:
        if not kw:
            continue
        norm = normalize_legal_term(kw)
        key = norm.lower()
        if key in seen_texts:
            continue
        seen_texts.add(key)
        keyword_objects.append(
            create_keyword_object(
                norm,
                llm_confidence=0.8,
                source="llm",
            )
        )
    
    # Literal ifadeler (hakaret, tırnak içi vs.) – strict sorguya girmesi zorunlu
    for lit in literal_keywords:
        if not lit:
            continue
        norm = lit.strip()
        key = norm.lower()
        if key in seen_texts:
            # Zaten varsa, mandatory + literal olarak güçlendir
            for obj in keyword_objects:
                if obj["text"].lower() == key:
                    obj["mandatory"] = True
                    if obj["type"] != "article":
                        obj["type"] = "literal"
            continue
        seen_texts.add(key)
        keyword_objects.append(
            create_keyword_object(
                norm,
                llm_confidence=1.0,
                keyword_type="literal",
                source="literal",
                mandatory=True,
            )
        )

    # Konseptten madde ipucu üret (örn. kira artış oranı -> TBK 344)
    lowered_texts = {kw["text"].lower() for kw in keyword_objects if kw.get("text")}
    for concept, arts in CONCEPT_TO_ARTICLE_HINTS.items():
        if any(concept in t for t in lowered_texts):
            for art in arts:
                if art.lower() not in lowered_texts:
                    keyword_objects.append(
                        create_keyword_object(
                            art,
                            llm_confidence=0.95,
                            keyword_type="article",
                            source="rule",
                        )
                    )
                    lowered_texts.add(art.lower())

    # Domain seedlerini enjekte et (TBK 344 / TÜFE vb.)
    # Kira/konut sinyali varsa domain seed ekle
    keyword_objects = add_domain_seeds(question, keyword_objects) if _has_kira_domain(keyword_objects) else keyword_objects
    seen_texts = {kw["text"].lower() for kw in keyword_objects if kw.get("text")}

    
    if not keyword_objects:
        safe_print("❌ HATA: Anahtar kelime çıkarılamadı.")
        return {"error": "Yetersiz anahtar kelime"}
    
    if len(keyword_objects) < MIN_TERMS:
        safe_print(f"⚠️ Uyarı: Sadece {len(keyword_objects)} anahtar kelime üretti, yine de devam ediliyor...")
    
    safe_print("   ✓ Anahtar Kelimeler:")
    for kw_obj in keyword_objects:
        mandatory_flag = " (zorunlu)" if kw_obj.get("mandatory") else ""
        safe_print(f"     - {kw_obj['text']} ({kw_obj['type']}){mandatory_flag}")
    
    # Madde 1: Query buckets oluştur (multi-query retrieval)
    safe_print("\n🌐 Sorgu Bucket'ları Oluşturuluyor (Multi-Query Retrieval)...")
    query_buckets = build_query_buckets(
        keyword_objects,
        extra_terms=literal_keywords,  # literal terimleri add-one varyantlarına ekle
        paraphrase_count=3,
        llm_for_paraphrase=os.environ.get("PARAPHRASE_MODEL"),
    )
    
    strict_query = query_buckets["strict_query"]
    broad_queries = query_buckets["broad_queries"]
    focus_queries = query_buckets.get("focus_queries") or []
    
    safe_print(f"   ✓ Strict Query: {strict_query}")
    safe_print(f"   ✓ Broad Query Varyantları: {len(broad_queries)} adet")
    for i, bq in enumerate(broad_queries[:3], 1):  # İlk 3'ünü göster
        safe_print(f"      {i}. {bq[:80]}...")
    if focus_queries:
        safe_print(f"   ✓ Focus Query Varyantları: {len(focus_queries)} adet")
    
    # Arama
    source_list = sources or DEFAULT_SOURCES
    all_docs_meta: List[Dict[str, Any]] = []
    metadata_limit = min(max(limit * 2, 50), 120)
    t0 = time.time()
    
    # Strict bucket araması (metadata)
    ranklists: List[List[str]] = []
    safe_print("\n🔍 Strict Bucket Araması (metadata)...")
    for src in source_list:
        conf = SOURCE_CONFIG[src]
        docs = search_yargitay(
            strict_query,
            limit=min(metadata_limit, 100),
            years_back=years_back,
            fetch_content=False,
            item_types=conf["item_types"],
            source_label=conf["label"],
            bucket="strict",
            query_signature=strict_query
        )
        all_docs_meta.extend(docs)
        strict_rank = [d.get("document_id") for d in docs if d.get("document_id")]
        if strict_rank:
            ranklists.append(strict_rank)
    
    safe_print(f"   ✓ Strict Bucket (meta): {len(all_docs_meta)} karar")
    seen_ids = {d.get("document_id") for d in all_docs_meta if d.get("document_id")}
    
    # Focus bucket araması (kira/TBK 344/TÜFE ekseni)
    if focus_queries:
        safe_print("\n🎯 Focus Bucket (TBK 344 / TÜFE) araması...")
        for idx, fq in enumerate(focus_queries, 1):
            safe_print(f"   🎯 {idx}/{len(focus_queries)}: {fq[:80]}...")
            for src in source_list:
                conf = SOURCE_CONFIG[src]
                docs = search_yargitay(
                    fq,
                    limit=min(15, metadata_limit // max(1, len(source_list))),
                    years_back=years_back,
                    fetch_content=False,
                    item_types=conf["item_types"],
                    source_label=conf["label"],
                    bucket="focus",
                    query_signature=fq
                )
                new_docs: List[Dict[str, Any]] = []
                for d in docs:
                    did = d.get("document_id")
                    if did and did in seen_ids:
                        continue
                    if did:
                        seen_ids.add(did)
                    new_docs.append(d)
                all_docs_meta.extend(new_docs)
                if new_docs:
                    ranklists.append([d.get("document_id") for d in new_docs if d.get("document_id")])
    
    new_from_broad = 0
    # Broad bucket araması (metadata, multi-query)
    if broad_queries:
        safe_print("\n🔍 Broad Bucket Araması (Multi-Query Varyantlar, metadata)...")
        for idx, broad_query in enumerate(broad_queries[:MAX_BROAD_VARIANTS], 1):
            safe_print(f"   🔄 Varyant {idx}/{min(len(broad_queries), MAX_BROAD_VARIANTS)}...")
            for src in source_list:
                conf = SOURCE_CONFIG[src]
                per_variant_limit = max(5, min(15, metadata_limit // max(1, len(source_list))))
                docs = search_yargitay(
                    broad_query,
                    limit=per_variant_limit,
                    years_back=years_back,
                    fetch_content=False,
                    item_types=conf["item_types"],
                    source_label=conf["label"],
                    bucket="broad",
                    query_signature=broad_query
                )
                new_docs = []
                for d in docs:
                    did = d.get("document_id")
                    if did and did in seen_ids:
                        continue
                    if did:
                        seen_ids.add(did)
                    new_docs.append(d)
                all_docs_meta.extend(new_docs)
                new_from_broad += len(new_docs)
                broad_rank = [d.get("document_id") for d in new_docs if d.get("document_id")]
                if broad_rank:
                    ranklists.append(broad_rank)
    if broad_queries:
        safe_print(f"    Broad ile yeni eklenen doküman: {new_from_broad}")

    # BM25 hibrit araması (opsiyonel)
    if BM25_ENABLED:
        safe_print("\n🧭 BM25 Hibrit Arama çalışıyor...")
        bm25_docs = search_bm25(question, limit=min(BM25_LIMIT, metadata_limit))
        new_bm25: List[Dict[str, Any]] = []
        for d in bm25_docs:
            did = d.get("document_id")
            if did and did in seen_ids:
                continue
            if did:
                seen_ids.add(did)
            new_bm25.append(d)
        if new_bm25:
            all_docs_meta.extend(new_bm25)
            bm25_rank = [d.get("document_id") for d in new_bm25 if d.get("document_id")]
            if bm25_rank:
                ranklists.append(bm25_rank)
            safe_print(f"    BM25 ile yeni eklenen: {len(new_bm25)}")
        else:
            safe_print("    BM25 sonuç eklemedi (ya sonuç yok ya da hepsi daha önce görüldü).")
    
    all_docs_meta = dedup_documents(all_docs_meta)
    meta_count = len(all_docs_meta)
    if meta_count > metadata_limit:
        all_docs_meta = all_docs_meta[:metadata_limit]
        meta_count = len(all_docs_meta)

    TARGET_MIN_META = int(os.environ.get("TARGET_MIN_META", "80"))
    kira_domain_flag = _has_kira_domain(keyword_objects)
    if meta_count < TARGET_MIN_META and kira_domain_flag:
        safe_print(f"\n🔎 Recall probe: meta {meta_count} < {TARGET_MIN_META}, tek-terimli fallbacklar koşuluyor (kira domain).")
        probe_queries = [
            '+"TBK 344"', '+"TÜFE"', '+"tuketici fiyat endeksi"', '+"12 aylik ortalama"',
            '+"kira tespit"', '+"kira artış"',
        ]
        new_from_probe = 0
        for pq in probe_queries:
            for src in source_list:
                conf = SOURCE_CONFIG[src]
                docs = search_yargitay(
                    pq,
                    limit=min(40, metadata_limit),
                    years_back=years_back,
                    fetch_content=False,
                    item_types=conf["item_types"],
                    source_label=conf["label"],
                    bucket="probe",
                    query_signature=pq,
                )
                new_docs = []
                for d in docs:
                    did = d.get("document_id")
                    if did and did in seen_ids:
                        continue
                    if did:
                        seen_ids.add(did)
                    new_docs.append(d)
                all_docs_meta.extend(new_docs)
                new_from_probe += len(new_docs)
        all_docs_meta = dedup_documents(all_docs_meta)
        meta_count = len(all_docs_meta)
        safe_print(f"    Recall sonrası toplam metadata: {meta_count} (probe ile {new_from_probe} yeni)")

    # RRF ile query listelerinin sırasını birleştir
    if ranklists:
        fused_ids = rrf_merge(ranklists)
        by_id = {d.get("document_id"): d for d in all_docs_meta if d.get("document_id")}
        ordered = [by_id[i] for i in fused_ids if i in by_id]
        # kalanları ekle
        seen_after = set(fused_ids)
        for d in all_docs_meta:
            did = d.get("document_id")
            if did and did in seen_after:
                continue
            ordered.append(d)
        all_docs_meta = ordered
    
    if not all_docs_meta:
        safe_print("\n⚠️ Hiç sonuç dönmedi, fallback sorgular deneniyor (TBK 344 / TÜFE / kira tespit)...")
        fallback_queries = [
            '+"TBK 344" +"TÜFE"',
            '+"TBK 344" +"tuketici fiyat endeksi"',
            '+"kira tespit" +"TÜFE"',
            '+"kira artış" +"TÜFE"',
        ]
        for fbq in fallback_queries:
            for src in source_list:
                conf = SOURCE_CONFIG[src]
                docs = search_yargitay(
                    fbq,
                    limit=min(metadata_limit, 50),
                    years_back=years_back,
                    fetch_content=False,
                    item_types=conf["item_types"],
                    source_label=conf["label"],
                    bucket="fallback",
                    query_signature=fbq
                )
                all_docs_meta.extend(docs)
        all_docs_meta = dedup_documents(all_docs_meta)
        meta_count = len(all_docs_meta)
        if meta_count > metadata_limit:
            all_docs_meta = all_docs_meta[:metadata_limit]
            meta_count = len(all_docs_meta)
        if not all_docs_meta:
            safe_print("\n🛑 HATA: Hiç karar bulunamadı (metadata).")
            return {"error": "Sonuç yok"}
    
    safe_print(f"   ✓ Toplam metadata karar: {meta_count}")
    
    # İlk rerank (metadata bazlı)
    if RERANK_PROVIDER and RERANK_PROVIDER != "none":
        safe_print("\n🔎 Rerank (metadata) aşaması başlatılıyor...")
        all_docs_meta = rerank_docs(question, all_docs_meta, top_n=min(RERANK_TOP_N, len(all_docs_meta)))
    
    # Tam metin zenginleştirme (en fazla limit*2 veya 40)
    fulltext_limit = min(len(all_docs_meta), max(limit * 2, 60), 120)
    safe_print(f"\n📄 Tam metin zenginleştirme: ilk {fulltext_limit} karar çekiliyor...")
    all_docs_full = enrich_full_texts(all_docs_meta, limit=fulltext_limit, max_workers=None)
    
    # İkinci rerank (tam metin bazlı)
    if RERANK_PROVIDER and RERANK_PROVIDER != "none":
        safe_print("\n🔎 Rerank (fulltext) aşaması başlatılıyor...")
        all_docs_full = rerank_docs(question, all_docs_full, top_n=min(RERANK_TOP_N, len(all_docs_full)))
    
    all_docs = all_docs_full
    
    if not all_docs:
        safe_print("\n❌ HATA: Hiç karar bulunamadı.")
        return {"error": "Sonuç yok"}

    # Madde 4: Kararları parse et (akıllı seçim)
    # Önce focus, sonra strict ve broad karışımı
    focus_docs = [d for d in all_docs if d.get("bucket") == "focus"]
    strict_docs = [d for d in all_docs if d.get("bucket") == "strict"]
    broad_docs = [d for d in all_docs if d.get("bucket") == "broad"]
    
    safe_print(f"\n📄 Karar Seçimi: {len(focus_docs)} focus, {len(strict_docs)} strict, {len(broad_docs)} broad")
    
    # Focus'u garantiye al, ardından strict ve broad karışımı
    selected_docs = (focus_docs[:10] + strict_docs[:10] + broad_docs[:5])[:25]
    safe_print(f"   [OK] {len(selected_docs)} karar parse edilecek (rerank sirasi korunuyor)")
    
    parsed_decisions = []
    for doc in selected_docs:
        parsed = parse_decision(
            doc.get("tam_metin", ""),
            doc.get("document_id", ""),
            doc
        )
        parsed_decisions.append(parsed)
    
    # Madde 5: İki aşamalı analiz
    safe_print("\n🤖 MAP Aşaması: Kararlar Özetleniyor...")
    decision_cards = []
    for parsed_dec in parsed_decisions:
        try:
            card = summarize_decision(parsed_dec, question)
            decision_cards.append(card)
        except Exception as e:
            logger.error(f"Karar özetleme hatası: {e}")
            continue
    
    safe_print(f"   ✓ {len(decision_cards)} karar özetlendi")
    
    safe_print("\n📇 Rule Card Retrieval: rule_cards koleksiyonu")
    rule_cards = fetch_rule_cards(question, top_k=RULE_CARD_TOP_K)
    safe_print(f"   ✓ {len(rule_cards)} rule card çekildi")
    
    safe_print("\n🤖 REDUCE Aşaması: Final Cevap Üretiliyor...")
    # Kaç kartın gerçekten ilgili olduğunu logla
    relevant_count = sum(1 for c in decision_cards if c.get("is_relevant_to_question"))
    safe_print(f"   ℹ️ {relevant_count}/{len(decision_cards)} karar soruyla ilgili işaretlendi")
    
    # Eğer yeterince güçlü kaynak yoksa no-answer fallback
    max_meta = max((d.get("bm25_score") or d.get("score") or 0.0) for d in all_docs_full) if all_docs_full else 0.0
    if no_answer_threshold > 0 and max_meta < no_answer_threshold:
        safe_print("\n⚠️ Yeterli güven yok, no-answer branch tetiklendi.")
        verified_answer = {
            "verdict": "belirsiz",
            "reasoning": [{"text": "Soruya dair yeterli güçlü kaynak bulunamadı; lütfen farklı ifadelerle tekrar deneyin.", "supporting_cases": []}],
            "cases_used": [],
        }
    else:
        draft_answer = aggregate_decisions(decision_cards, question, rule_cards)
        
        # Madde 7: Halüsinasyon kontrolü
        safe_print("\n✅ Halüsinasyon Kontrolü...")
        verified_answer = verify_answer(question, decision_cards, draft_answer)
    
    # DETERMINISTIK EMSAL ZORUNLULUĞU
    # LLM hiç emsal döndürmese bile, mutlaka en az birkaç yakın karar göster
    cases_used = verified_answer.get("cases_used") or []
    if not cases_used:
        safe_print("   ⚠️ LLM emsal döndürmedi, deterministik seçim yapılıyor...")
        nearest = pick_nearest_cases(decision_cards, max_cases=3)
        verified_answer["cases_used"] = nearest
        
        # Gerekçe de boşsa, yakın emsal gerekçesi ekle
        if not verified_answer.get("reasoning") or len(verified_answer["reasoning"]) == 0:
            verified_answer["reasoning"] = [{
                "text": "Aşağıdaki kararlar soruya bire bir uymasa da TCK 150/1 ve ilgili suçlar bakımından yakın emsal niteliğindedir.",
                "supporting_cases": [c["id"] for c in nearest]
            }]
        
        safe_print(f"   ✓ {len(nearest)} yakın emsal otomatik eklendi")
    
    # Oy mantığıyla verdict güçlendirmesi (opsiyonel - sadece belirsizse uygula)
    if verified_answer.get("verdict") == "belirsiz":
        computed_verdict = compute_verdict_from_cards(decision_cards)
        if computed_verdict != "belirsiz":
            safe_print(f"   ℹ️ Verdict kartlardan hesaplandı: {computed_verdict}")
            verified_answer["verdict"] = computed_verdict
    
    # Kira/TBK 344 domaininde deterministik sınır notu ve verdict koruması
    kira_domain = _has_kira_domain(keyword_objects)
    if kira_domain:
        # TÜFE/TBK sinyali içeren kartlar var mı?
        tufe_cards = []
        for c in decision_cards:
            blob = " ".join(
                [
                    c.get("facts_short", ""),
                    c.get("reasoning_short", ""),
                    " ".join(c.get("key_points", [])),
                ]
            )
            if _has_tufe_signal(blob):
                tufe_cards.append(c)
        if verified_answer.get("verdict") == "uygulanabilir" and not tufe_cards:
            verified_answer["verdict"] = "belirsiz"
            verified_answer.setdefault("reasoning", []).append({
                "text": "TBK 344/TÜFE sinyali bulunmadığı için kira artışı üst sınırı doğrulanamadı.",
                "supporting_cases": []
            })
        # Mutlaka TÜFE üst sınır notu ekle
        verified_answer.setdefault("reasoning", []).insert(0, {
            "text": "TBK 344 gereği kira artışı 12 aylık TÜFE ortalamasını aşamaz; bu oranı aşan artışlar sözleşme olsa dahi sınırlıdır.",
            "supporting_cases": [c.get("id") for c in tufe_cards[:2] if c.get("id")] if tufe_cards else []
        })
        # Soruda belirtilen yüzde talebi varsa ve yüksekse verdict'i temkinli yap
        percents = _extract_percent_values(question or "")
        if percents:
            max_pct = max(percents)
            if max_pct >= 50 and verified_answer.get("verdict") == "uygulanabilir":
                verified_answer["verdict"] = "belirsiz"
                verified_answer.setdefault("reasoning", []).append({
                    "text": f"Soruda talep edilen %{max_pct} artış, TBK 344 kapsamındaki 12 aylık TÜFE ortalaması sınırını aşabilir; bu nedenle olumlu görüş belirsiz olarak güncellendi.",
                    "supporting_cases": [c.get("id") for c in tufe_cards[:2] if c.get("id")] if tufe_cards else []
                })
    
    # Link alanlarını deterministik olarak ekle
    id2url = {c.get("id"): c.get("view_url") or c.get("url") for c in decision_cards if c.get("id")}
    for cu in verified_answer.get("cases_used", []):
        if cu.get("id") and not cu.get("url") and id2url.get(cu["id"]):
            cu["url"] = id2url[cu["id"]]

    # Dayanak kartları minimum 4 olacak şekilde tamamla (öncelik focus > strict > broad)
    cases_used = verified_answer.get("cases_used") or []
    if len(cases_used) < 4:
        # id seti
        used_ids = {c.get("id") for c in cases_used if c.get("id")}
        ordered_cards = sorted(
            decision_cards,
            key=lambda c: {"focus": 0, "strict": 1, "broad": 2}.get(c.get("bucket"), 3)
        )
        for c in ordered_cards:
            cid = c.get("id")
            if not cid or cid in used_ids:
                continue
            cases_used.append({
                "id": cid,
                "citation": c.get("citation", ""),
                "key_role": c.get("reasoning_short", "")[:200] or "Soru ile ilgili emsal",
                "view_url": c.get("view_url"),
                "bucket": c.get("bucket")
            })
            used_ids.add(cid)
            if len(cases_used) >= 4:
                break
        verified_answer["cases_used"] = cases_used
    
    # Madde 8: Format output
    duration = time.time() - t0
    safe_print(f"\n⏱️ Toplam süre: {duration:.1f} sn")
    safe_print("\n📊 Çıktı Formatlanıyor...")
    formatted_output = format_legal_output(verified_answer, question)
    
    # Dosyalara kaydet
    run_dir = _create_run_directory(output_base_dir)
    
    # Decision cards'ı kaydet (NDJSON)
    cards_path = run_dir / "decision_cards.ndjson"
    with cards_path.open("w", encoding="utf-8") as f:
        for card in decision_cards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    rule_cards_path = run_dir / "rule_cards.ndjson"
    with rule_cards_path.open("w", encoding="utf-8") as f:
        for card in rule_cards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    
    # Verified answer'ı kaydet
    answer_path = run_dir / "verified_answer.json"
    answer_path.write_text(json.dumps(verified_answer, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Formatted output'u kaydet
    output_path = run_dir / "final_output.txt"
    output_path.write_text(formatted_output, encoding="utf-8")
    
    safe_print(f"\n💾 Dosyalar Kaydedildi:")
    safe_print(f"   📄 Decision Cards: {cards_path}")
    safe_print(f"   📇 Rule Cards: {rule_cards_path}")
    safe_print(f"   📊 Verified Answer: {answer_path}")
    safe_print(f"   📝 Final Output: {output_path}")
    
    safe_print("\n" + formatted_output)
    
    return {
        "question": question,
        "keywords": keyword_objects,
        "query_buckets": query_buckets,
        "total_docs": len(all_docs),
        "meta_docs": meta_count,
        "fulltext_docs": len(all_docs_full),
        "duration_sec": duration,
        "decision_cards": decision_cards,
        "rule_cards": rule_cards,
        "verified_answer": verified_answer,
        "formatted_output": formatted_output
    }

# ============================================================================
# MADDE 9: REGRESSION TEST SETİ
# ============================================================================

def load_test_scenarios(test_file: str = "tests/legal_scenarios.json") -> List[Dict[str, Any]]:
    """Test senaryolarını yükler."""
    path = Path(test_file)
    if not path.exists():
        logger.warning(f"Test dosyası bulunamadı: {test_file}")
        return []
    
    try:
        with path.open("r", encoding="utf-8") as f:
            scenarios = json.load(f)
        return scenarios
    except Exception as e:
        logger.error(f"Test dosyası okuma hatası: {e}")
        return []

def run_tests(test_file: str = "tests/legal_scenarios.json", 
              output_dir: str = "outputs/tests/") -> None:
    """Tüm test senaryolarını çalıştırır ve çıktıları verilen klasöre yazar."""
    scenarios = load_test_scenarios(test_file)
    
    if not scenarios:
        safe_print("❌ Test senaryosu bulunamadı.")
        return
    
    safe_print(f"\n🧪 {len(scenarios)} Test Senaryosu Çalıştırılıyor...\n")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        question = scenario.get("question", "")
        expected_verdict = scenario.get("expected_verdict", "")
        expected_cases = scenario.get("expected_cases", [])
        
        safe_print(f"Test {i}/{len(scenarios)}: {question[:50]}...")
        
        # Beklenti yoksa çalıştırıp gereksiz dosya üretmeyelim
        if not expected_verdict and not expected_cases:
            results.append({
                "test_id": i,
                "question": question,
                "status": "SKIP",
                "reason": "Beklenen karar/verdict tanımlı değil"
            })
            safe_print("   ⏭️ SKIP")
            continue
        
        try:
            result = run_llm_pipeline(
                question=question,
                limit=50,
                years_back=15,
                sources=DEFAULT_SOURCES,
                output_base_dir=output_dir,
            )
            
            actual_verdict = result.get("verified_answer", {}).get("verdict", "")
            actual_cases = [c["id"] for c in result.get("verified_answer", {}).get("cases_used", [])]
            
            # Karşılaştır
            verdict_match = actual_verdict == expected_verdict if expected_verdict else None
            cases_overlap = len(set(actual_cases) & set(expected_cases)) if expected_cases else None
            
            test_result = {
                "test_id": i,
                "question": question,
                "expected_verdict": expected_verdict,
                "actual_verdict": actual_verdict,
                "verdict_match": verdict_match,
                "expected_cases": expected_cases,
                "actual_cases": actual_cases,
                "cases_overlap": cases_overlap,
                "status": "PASS" if verdict_match else "FAIL"
            }
            
            results.append(test_result)
            safe_print(f"   ✓ {test_result['status']}")
            
        except Exception as e:
            logger.error(f"Test {i} hatası: {e}")
            results.append({
                "test_id": i,
                "question": question,
                "status": "ERROR",
                "error": str(e)
            })
            safe_print(f"   ❌ ERROR")
    
    # Sonuçları kaydet
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_path / f"test_results_{timestamp}.json"
    results_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Özet
    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    errors = sum(1 for r in results if r.get("status") == "ERROR")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    
    safe_print("\n" + "=" * 70)
    safe_print("TEST SONUÇLARI")
    safe_print("=" * 70)
    safe_print(f"Toplam: {total}")
    safe_print(f"Başarılı: {passed}")
    safe_print(f"Başarısız: {failed}")
    safe_print(f"Hata: {errors}")
    safe_print(f"Atlanan: {skipped}")
    safe_print(f"\nSonuçlar kaydedildi: {results_file}")
    safe_print("=" * 70)

# ============================================================================
# FILE I/O FUNCTIONS
# ============================================================================

def _create_run_directory(base_dir: str = "tests/docs") -> Path:
    """Her sorgu için otomatik klasör oluşturur."""
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(r"sorgu(\d+)", re.I)
    max_idx = 0
    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        match = pattern.fullmatch(child.name)
        if match:
            try:
                max_idx = max(max_idx, int(match.group(1)))
            except ValueError:
                continue
    run_dir = base_path / f"sorgu{max_idx + 1:03d}"
    run_dir.mkdir(exist_ok=False)
    return run_dir

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main() -> None:
    """Ana program giriş noktası."""
    parser = argparse.ArgumentParser(
        description="Yargıtay Karar Arama ve LLM Analiz Sistemi v3.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  # LLM ile otomatik anahtar kelime çıkarma ve analiz
  python yargitay_search_v3.py --question "Nitelikli yağma suçunda TCK 150/1 uygulanır mı?"
  
  # OpenAI kullanarak arama
  python yargitay_search_v3.py --question "..." --llm-provider openai
  
  # Regression testlerini çalıştır
  python yargitay_search_v3.py --run-tests
        """
    )
    
    parser.add_argument("--question", help="Hukuki soru")
    parser.add_argument("--limit", type=int, default=100, help="Çekilecek en fazla karar sayısı")
    parser.add_argument("--years-back", type=int, default=15, help="Son X yıl ile sınırla")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES), help="Virgülle ayrılmış kaynak listesi")
    parser.add_argument("--llm-provider", choices=["openai", "ollama"], help="LLM sağlayıcısı")
    parser.add_argument("--run-tests", action="store_true", help="Regression testlerini çalıştır")
    parser.add_argument("--test-file", default="tests/legal_scenarios.json", help="Test senaryoları dosyası")
    
    args = parser.parse_args()
    
    # LLM provider seçimi
    global SELECTED_LLM_PROVIDER
    if args.llm_provider:
        if args.llm_provider.lower() == "openai":
            if not CHAT_GPT_API_KEY:
                safe_print("❌ Uyarı: OpenAI seçildi ancak CHAT_GPT_API_KEY tanımlı değil.")
                safe_print("   Ollama kullanılacak.")
                SELECTED_LLM_PROVIDER = "ollama"
            else:
                SELECTED_LLM_PROVIDER = "openai"
        else:
            SELECTED_LLM_PROVIDER = "ollama"
    else:
        # Varsayılanı Ollama yap; OpenAI ancak açıkça seçilirse kullanılır
        SELECTED_LLM_PROVIDER = "ollama"
    
    # Madde 9: Test modu
    if args.run_tests:
        run_tests(test_file=args.test_file)
        return
    
    # Soru alma
    question = args.question
    if not question:
        try:
            question = input("LLM'ye sorulacak hukuki soruyu girin: ").strip()
        except (EOFError, KeyboardInterrupt):
            safe_print("\nÇıkılıyor...")
            return
    
    if not question:
        parser.error("Soru girilmeli veya --run-tests kullanılmalı.")
    
    # Parametreleri işle
    years_back = args.years_back if args.years_back and args.years_back > 0 else None
    limit = max(1, min(args.limit, 300))
    
    raw_sources = [s.strip().lower() for s in (args.sources or "").split(",") if s.strip()]
    source_list = list(set(raw_sources)) if raw_sources else list(DEFAULT_SOURCES)
    
    # Pipeline çalıştır
    try:
        run_llm_pipeline(
            question,
            limit=limit,
            years_back=years_back,
            sources=source_list,
        )
    except Exception as e:
        logger.error(f"Pipeline hatası: {e}", exc_info=True)
        safe_print(f"\n❌ HATA: {e}")
        safe_print("\nLütfen soruyu yeniden formüle edin veya parametreleri kontrol edin.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nProgram kullanıcı tarafından durduruldu.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Beklenmeyen hata: {e}", exc_info=True)
        safe_print(f"\n❌ KRİTİK HATA: {e}")
        safe_print("Detaylar için yargitay_search.log dosyasını kontrol edin.")
        sys.exit(1)
