#!/usr/bin/env bash
set -euo pipefail

HOST="${OPENSEARCH_URL:-http://admin:admin@opensearch:9200}"
INDEX="legal_chunks_bm25"

payload=$(cat <<'JSON'
{
  "settings": {
    "analysis": {
      "filter": {
        "tr_stop": {"type": "stop", "stopwords": "_turkish_"},
        "tr_stemmer": {"type": "snowball", "language": "Turkish"},
        "tr_synonyms": {
          "type": "synonym",
          "lenient": true,
          "synonyms": [
            "fesih, sona erme",
            "uyarlama, \"aşırı ifa güçlüğü\"",
            "m., madde",
            "E., esas",
            "K., karar"
          ]
        }
      },
      "analyzer": {
        "tr_analyzer": {
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "asciifolding",
            "apostrophe",
            "tr_stop",
            "tr_stemmer",
            "tr_synonyms"
          ]
        }
      }
    }
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "doc_id": {"type": "keyword"},
      "version": {"type": "integer"},
      "title": {"type": "text", "analyzer": "tr_analyzer"},
      "content": {"type": "text", "analyzer": "tr_analyzer"},
      "article_no": {"type": "keyword"},
      "paragraph_no": {"type": "keyword"},
      "e_no": {"type": "keyword"},
      "k_no": {"type": "keyword"},
      "rg_no": {"type": "keyword"},
      "rg_date": {"type": "date"},
      "court": {"type": "keyword"},
      "chamber": {"type": "keyword"},
      "source": {"type": "keyword"},
      "doc_type": {"type": "keyword"},
      "url": {"type": "keyword"},
      "is_current": {"type": "boolean"}
    }
  }
}
JSON
)

echo "Creating index ${INDEX} on ${HOST} (idempotent)..."
curl -XPUT "${HOST}/${INDEX}" \
  -H "Content-Type: application/json" \
  -d "${payload}" || echo "Index may already exist; skipping."
