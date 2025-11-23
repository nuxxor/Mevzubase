# yargitay_search.py revizyon notları (v3.2 üzerinde yapılan iyileştirmeler)

## 1) Konfig / ortam
- Env değişkenleri eklendi: `COHERE_API_KEY`, `PARALLEL_API_KEY`, `RERANK_PROVIDER` (none|local|cohere|parallel|auto), `RERANK_MODEL` (HF), `COHERE_RERANK_MODEL`, `RERANK_TOP_N`.
- Link alanı: `view_url` tüm dokümanlara `/ictihat/{id}?query=...` formatıyla ekleniyor.

## 2) Reranker katmanı
- Sağlayıcı sınıfları: `LocalHFReranker` (HF cross-encoder, GPU/CPU), `CohereReranker`, `ParallelReranker` (stub).
- `pick_reranker` ile provider seçimi; `rerank_docs` meta ve fulltext aşamalarında isteğe bağlı çalışıyor.
- RRF füzyon (`rrf_merge`) eklenerek farklı query listeleri tek sıralamaya indirgeniyor.

## 3) Query/terim iyileştirmeleri
- Stop-concept filtresi: “yasal, sozlesme/sözlesme, zam, durum, dava, mahkeme” strict’ten çıkartılıyor.
- TBK 344 genişletmesi: “TBK 344, TBK m.344, Turk Borclar Kanunu 344, on iki aylik ortalama, tufe, tuketici fiyat endeksi” broad varyantlara ekleniyor.
- Diyakritik/kısaltma varyant üretici: TÜFE/TUFE, Yİ-ÜFE varyantları ve ascii’leşmiş formlar broad’a ekleniyor.
- Türkçe typo düzeltmeleri genişletildi (tufe→tüfe, tuketici→tüketici, yi-ufe→yi-üfe vb.).

## 4) Retrieval akışı
- İki aşamalı: Önce strict+broad meta (`fetch_content=False`) toplanıyor, dedup ve RRF uygulanıyor, istenirse metadata-rerank çalışıyor.
- Ardından ilk `max(limit*2, 40)` kaydın tam metni çekiliyor, fulltext-rerank uygulanıyor.
- Dedup helper (`dedup_documents`) ve tam metin yeniden çekme (`enrich_full_texts`) eklendi.
- Async httpx araması için `async_search_yargitay` stub’ı hazır (henüz akışta kullanılmıyor).

## 5) Pasaj / evidence
- `parse_decision` 300–400 kelimelik pasajlar üretiyor (fallback’te de ekler).
- `summarize_decision` reranker varsa en iyi 2 pasajı LLM’e veriyor; prompt artık `evidence` (quote+start/end) istiyor.
- Decision kartları link ve bucket bilgisini taşıyor.
- `verify_answer` evidence’ı metin/pasaj içinde (ve varsa start/end aralığında) doğruluyor, geçmeyen alıntıları atıyor.

## 6) Telemetri ve çıktı
- Pipeline başında zaman damgası, formatlama öncesi toplam süre logu.
- `run_llm_pipeline` çıktısına `meta_docs`, `fulltext_docs`, `duration_sec` alanları eklendi.
- Dosya kayıtları aynı (decision_cards.ndjson, verified_answer.json, final_output.txt).

## 7) Değişmeyenler / notlar
- Map/Reduce mantığı, strict vs. broad ayrımı, nearest-case fallback korunuyor; nearest-case artık `view_url` da taşır.
- Async/httpx entegrasyonu henüz akışa bağlanmadı; ileride paralel çekim için kullanılabilir.

## 8) Olası sonraki adımlar
- `async_search_yargitay` akışa bağlanıp varyantlar/ kaynaklar paralel çekilebilir.
- Telemetriyi dosyaya/JSON’a yazma; hit@k ve latency metriklerini ekleme.
- Evidence start/end tespitini section bazlı iyileştirme; passage-level rerank modelini (provider tabanlı) doğrudan kullanma.

## 9) Son eklemeler (arama + timeout + TÜFE/TBK)
- Arama timeout varsayılanı `SEARCH_TIMEOUT_SEC=45`; içerik çekme için `DOC_TIMEOUT_SEC=180`, `CONNECT_TIMEOUT_SEC=10` env ile ayarlanabilir.
- HTTP çağrıları `requests.Session` + Retry adapter ile yapılır; arama istekleri `(connect, read)` tuple timeout kullanır.
- Broad/drop/add varyantlarında en az iki terim şartı var; tek kelimelik sorgular üretilmiyor ve dedup aşamasında eleniyor; broad limit 10.
- TÜFE/TBK 344 sinyali güçlendirildi: broad ve fallback sorgularda tüfe/TÜFE/“tüketici fiyat endeksi” + TBK 344 kombinasyonları öne alındı.
- Reranker varsayılanı BGE (`BAAI/bge-reranker-v2-m3`), fallback Jina; final çıktı linkleri gösteriliyor, cases_used URL’leri deterministik ekleniyor.

## 10) Kira focus bucket + pipeline sadeleşmesi (güncel ekler)
- Yeni yardımcılar: `_ascii_fold` ile stop filtre normalize, `_has_kira_domain` ile kira domain tespiti, `_kira_focus_queries` ile TBK 344/TÜFE odaklı sorgular (6 adetle sınır).
- STOP_CONCEPTS’e `genel` eklendi; strict filtresi ascii-fold edilmiş stoplarla çalışıyor; kira domeninde strict’e deterministik TBK 344 + TÜFE sinyali enjekte ediliyor.
- Focus bucket araması strict sonrası, broad öncesi çalışıyor; dedup+RRF’e giriyor, seçimde focus/strict/broad 12/12/6 (max 30) ağırlıklı.
- Diyakritik varyant üretimi sade: gerçek TÜFE/Yİ-ÜFE/TBK 344 yazımları, yapay yiu-fe vb. çıkarıldı; TBK m. 344 varyantı eklendi.
- enrich_full_texts varsayılanı `max_workers=12`; pipeline’da üçüncü rerank kaldırıldı (meta + fulltext yeter).
- LocalHFReranker `trust_remote_code` bayrağını tokenizer/model yüklemesine geçiriyor (remote code gerektiren modeller için).
