# Mevzubase RAG Özeti

## Kaynak/parse akışı
- Bağlayıcılar `legal-etl/src/connectors` altında. Yargıtay (Bedesten/Mevzuat) ve Emsal için JSON + HTML fallback kullanılıyor; Playwright ile boş gelen sayfalara tarayıcı fallback var.
- `parse` çıktısı `CanonDoc` (doc_id, kaynak, başlık, tarih, daire, mahkeme, meta) ve ham HTML’i saklıyor; checksum ile versiyonlama ve `chunk_version`/`embed_version` meta’ları dolduruluyor.
- Text temizleme: `decision_chunker.normalize_text` satır gürültülerini, encoding artefaktlarını süpürüyor; kanun numarası/daire normalize ediliyor (`core/legal.py`).

## Chunking
- Kararlar bölüm başlıklarına göre (`ÖZET`, `GEREKÇE`, `HÜKÜM/SONUÇ` vb.) ayrılıyor (`decision_chunker.split_sections`).
- Her chunk’a üst bilgi anchor ekleniyor: `[KAYNAK:...|DAİRE:...|E:...|K:...|T:...]` + `[BÖLÜM]`.
- Yumuşak hedef ~600 token, sert limit ~850 token (`SOFT_TOKEN_TARGET`, `HARD_TOKEN_LIMIT`); uzun paragraflar bölünüyor, boş chunk bırakılmıyor.
- `payload` içinde doc meta (kaynak, doc_type, url, court, chamber, e_no/k_no, decision_date, tag’ler) taşınıyor; `chunk_id` `doc_id:v{version}:c{n}` formatında üretiliyor.
- Chunk overlap eklendi (50 token civarı), chunk_version/embed_version 2’ye geçirildi; embed/indexi yeni sürümlerle yeniden çalıştırmak gerekiyor.

## Embedding ve vektör deposu
- Varsayılan embedder `legal-etl/src/core/embed.py`: Cohere `embed-multilingual-v3.0` (1024 boyut) ile batch 48; `COHERE_API_KEY` zorunlu.
- Qdrant indexer `core/index_qdrant.py`: koleksiyon `legal_chunks_v1`, COSINE mesafe, boyut 1024; payload’a `chunk_id/article_no/paragraph_no` eklenip upsert ediliyor.
- Alternatif yerel yol `scripts/yargitay_local_pipeline.py`: NDJSON chunk’ları SentenceTransformer `BAAI/bge-m3` ile normalize edilmiş vektörlere çevirip Qdrant’a yazıyor (opsiyonel int8 quantization + on-disk, HNSW m=32/ef=256).
- Lexical taraf: `core/index_bm25.py` OpenSearch indeksine (TR analyzer + synonyms varsayımı) chunk metnini yazabiliyor; RAG’de hibrit için hazır.

## Retrieval + rerank
- `scripts/query_qdrant.py`: Sorgu embed’i varsayılan `BAAI/bge-m3`; Qdrant’tan `retrieval_top_k` çekip local CrossEncoder (`BAAI/bge-reranker-v2-m3`) veya Cohere `rerank-v3.5` ile ikinci aşama sıralama yapabiliyor.
- `yargitay_search.py`: Çoklu sorgu (strict/broad/focus) üretip RRF ile birleştiriyor; meta ve fulltext için iki aşamalı rerank. Reranker provider seçimi env’den (`RERANK_PROVIDER=none|local|cohere|parallel|auto`), model varsayılan `BAAI/bge-reranker-v2-m3`, fallback `jinaai/jina-reranker-v2-base-multilingual`; Cohere rerank opsiyonel. Rerank yoksa lexical overlap fallback var.
- Tam metin çekimi paralel (`enrich_full_texts`, default 12 worker); timeout/backoff ayarlı.
- Yeni domain seed’leri: Kira/TBK 344/TÜFE ve nafaka/TMK 175/329 için deterministik sinyaller ve focus query’leri eklendi (nafaka soruları artık bulunabiliyor).
- Mevcut `yargitay_search` API tabanlı akış: full vektörlü RAG gelene kadar geçici çözüm ve/veya RAG sonuçlarını doğrulamak için kullanılabilir. RAG’den gelen linkler Yargıtay’dan scrape edilip ek bir doğrulama katmanı olarak çalıştırılabilir.

## LLM katmanı
- `yargitay_search.py` LLM sağlayıcısı: default Ollama `qwen2.5:32b-instruct`, `--llm-provider openai` veya `SELECTED_LLM_PROVIDER=openai` ile ChatGPT (`gpt-4o-mini`) çağrısı. `_call_llm` ile ortak kapı, timeouts/logging var.
- Kullanım yerleri: anahtar kelime çıkarma, JSON tamiri, karar özetleme (map), soru-özel sonuç çıkarımı, halüsinasyon kontrolü (evidence doğrulama) ve final özet (reduce). En iyi 2 pasaj seçimi reranker varsa onun skoruna göre yapılıyor.

## Kural Kartları (Rule Cards)
- Sorun: LLM ince ayrımlarda (açık/gizli ayıp, ihbar süresi, iğfal) aks kayması yapabiliyor; her issue için elle kural yazmak ölçeklenmiyor.
- Çözüm fikri: Karar metinlerinden otomatik “kural kartı” çıkarımı. Şema: `{issue, facts_key, rule, exceptions, holding, citations, confidence}`. Map prompt ile karar → JSON; opsiyonel reduce (dedup/merge); kartları embedleyip ayrı koleksiyonda saklamak; sorgu anında kart + karar snippet’leri birlikte prompt’a eklemek.
- Prototip: `legal-etl/scripts/rule_card_extractor.py` eklendi. Top-N karar chunk’ı Qdrant’tan çekiyor, LLM map prompt’u ile kart üretiyor, dedup edip NDJSON yazıyor (LLM entegrasyonu için `call_llm` doldurulacak). Pilot: satım/ayıp (açık/gizli, ekspertiz, ihbar, iğfal) issue’su.
- Entegrasyon hedefi: Kartlar embed + “rule_cards” koleksiyonuna yazılacak; sorgu sırasında issue sınıflandırma/semantic search ile 3–5 kart çekilip final prompt’ta açık/gizli/ihbar/iğfal slotları zorunlu kılınacak, cite-check yapılacak. Scrape tamamlandıkça kart havuzu batch olarak güncellenecek.
- Yapılanlar (pilot): 2005–2009 chunk’ları `yargitay_chunks_local_v1` koleksiyonuna (Qdrant) yüklendi. `rule_card_extractor` Ollama’ya (_call_llm) bağlandı ve satım/ayıp için 4 kart üretildi (`rule_cards.ndjson`). Kartlar BGE-m3 ile embedlenip `rule_cards` koleksiyonuna GPU üzerinden yazıldı. (Komut örneği: `python -m scripts.rule_card_extractor --issue "satım/ayıp" --queries "ayıp ihbar ekspertiz" --top-n 5 --collection yargitay_chunks_local_v1 --qdrant-url http://localhost:6333 --device cuda` + Qdrant’a `rule_cards` upsert.)
- Ek issue kartları: kira/TBK 344 (4 kart), nafaka/TMK 175/329 (6), iş/kıdem-ihbar (1), eser/ayıp (5), tüketici/ayıplı mal (5) üretildi ve `rule_cards` koleksiyonuna eklendi (toplam 25+ kart).
- Plan (scrape tamamlanınca): issue listesi + otomatik sınıflandırma ile her issue için batch extractor (top-N Qdrant → map LLM → dedup) çalıştırıp NDJSON üret; BGE-m3 ile embedleyip `rule_cards` koleksiyonuna incremental upsert; nightly/weekly job ile yeni kararlar geldikçe kart havuzunu güncelle; sorgu pipeline’ında issue sınıflandırma → rule_cards retrieval → kart + snippet birlikte prompt zorunlu formatla kullan.
- Nightly/otomasyon taslağı: her gece yeni kararları scrape → temizle → chunk → embed + Qdrant incremental upsert. Issue sınıflandırıcı ile yeni kararları etiketle, her issue için “son X gün” top-N çekip map LLM ile kart üret; hash/dedup ile eski kartları güncelle, yenileri ekle; embedleyip `rule_cards` koleksiyonuna upsert. Cron/Airflow ile orkestrasyon + smoke test + metrik (kart sayısı, dedup oranı, LLM hata oranı). LLM hatasında fallback kart veya mevcut kartları koruma.

### Başarı Beklentisi (85–90 bandı için gerekenler)
- Koşullar: tam korpus (2010+), 15–30 çekirdek issue, güvenilir issue sınıflandırıcı, top-N kart üretimi (10–20) + dedup/merge, cite doğrulama, sıkı prompt/guardrail (kart+snippet zorunlu format), no-answer/çelişki tespiti, düzenli nightly batch, disiplinli eval (Qrels + RAGAS/insan A/B).
- Beklenti: Bu iyileştirmelerle iyi kapsanmış domainlerde %85–90 memnuniyet bandı mümkün; geniş serbest alanda daha düşük kalabilir. Eval ve geri besleme olmadan %90+ iddialı.

## Dilekçe editörü (prototype)
- `legal-editor/` altında React + TipTap tabanlı web arayüzü kuruldu; form (mahkeme, taraflar, olgular+delil referansı, hukuki sebepler, talepler, deliller) + sağda Word-benzeri rich text editör (bold/italic/underline/strike/list/hizalama/link/vurgulama) ve A4 benzeri sayfa önizlemesi var.
- Versiyonlama: editör içeriği “Taslak olarak kaydet” ile Versiyon 1, 2… olarak saklanıp dropdown’dan yüklenebiliyor; otomatik kaydı yok, kullanıcı tetikliyor.
- Taslak üretimi: frontend “Taslak Üret” ile backend `/generate` endpoint’ine POST atıyor; API `mode=qwen` çalışırken Ollama Qwen (qwen2.5:32b-instruct) ile HTML döndürüyor, editörde görüntülenip düzenleniyor. `mode=static` ile mock JSON döndürmek mümkün.
- Basit HTML test formu (`scripts/petition_api.py` içinde) ve zengin UI (Vite dev server) mevcut; prod build `legal-editor/dist` ile alınabiliyor.

## İyileştirme notları
1) **Embed/query hizalaması**: Üretim vektörleri Cohere (1024d) ise sorgu tarafının da Cohere embed’i kullanması; BGE ile indeks kurulacaksa doc embed’lerini de aynı modele çevirmek (aksi halde recall düşer).  
2) **Değerlendirme kiti**: 20–50 soruluk Türkçe hukuki Qrels seti ile `query_qdrant.py` üzerinden hit@k / nDCG@k ölçümü eklemek; rerank on/off ve farklı embed modellerini kıyaslamak için basit bir benchmark script’i eklenmeli.  
3) **Hibrit sıralama**: OpenSearch BM25 sonuçlarını Qdrant ile RRF/weighted fusion (örn. alpha scoring) ile birleştirmek, kısa sorgularda recall’ı artırır.  
4) **Chunk kalitesi**: Anchor + bölüm başlıkları iyi; ek olarak 50–100 token overlap veya cümle sonu bazlı kesme eklemek, pasaja düşen kritik cümlelerin bölünmesini azaltır. `chunk_version`/`embed_version` meta’ları arttırıp A/B embed denemesi yapılabilir.  
5) **Reranker opsiyonu**: Varsayılanı `local` yapıp GPU mevcutsa otomatik açmak; batch size autotune ve max_length 512→768 denemesi Türkçe uzun cümleler için fayda sağlayabilir. Cohere rerank’ı sadece düşük güvenli sorgular için devreye alan bir “gated rerank” stratejisi eklenebilir.  
6) **LLM maliyet/latency**: Ollama Qwen2.5 hızlı; OpenAI seçildiğinde prompt’ta token sınırı/quote sayısını kısıtlayıp yanıt uzunluğunu kontrol etmek, streaming/logging eklemek yararlı.  
7) **Gözlemlenebilirlik**: Embed/upsert ve rerank hatalarını sayan metrikler (Prometheus push veya basit JSON log) + Qdrant sorgu latency’si; LLM yanıtlarında evidence coverage oranını loglamak kalite takibi için iyi metrikler olacaktır.

## Yol haritası (semantic + kural tabanı)
- Scrape tamamlandıktan sonra tam vektörlü RAG’e geç: chunk_version/embed_version 2 ile tüm korpusu embedle (BGE-m3 veya seçilecek model) ve Qdrant/Weaviate’e yaz; API-only aramayı azalt.
- Genel kural/sözlük katmanı: sınırlı domain seed setleri (kira/TBK344, nafaka/TMK175/329, şikayet/takipsizlik gibi usul terimleri) ve synonym sözlükleri; her soru için manuel varyant yerine geniş kapsayıcı sinyaller.
- Multi-query + paraphrase: kural bazlı varyantları ve LLM paraphrase’i koru; embed’li aramada da recall’i güçlendir.
- Eval & metrikler: embed sonrası Hit/MRR ve RAGAS/LLM-judge metriklerini ekle; Phoenix/LangSmith trace ile regresyonları izle.
- Performans: LLM model boyutu ve özetlenecek karar sayısını ayarlayarak latency’yi düşür; gerekirse daha küçük lokal model kullan.
- Domain fine-tune: RTX 5090 üzerinde mümkün. (1) Embedding/reranker modelleri (BGE/SBERT, cross-encoder) için LoRA veya tam fine-tune ile Türkçe hukuk relevansına uyarlama; (2) küçük/orta LLM’ler (7–13B) için LoRA/QLoRA ile Türkçe hukuk Q&A/instruction adaptasyonu. Amaç: recall/sıralama/cevap doğruluğunu domain’e özgü artırmak.
- Test artefaktları: `tests/docs/sorgu*` ve `tests/eval_runs/` çıktıları şu an referans için duruyor; production’a geçmeden, scrape+embed tamamlandığında bu kartlar silinip temiz bir başlangıç yapılmalı.
