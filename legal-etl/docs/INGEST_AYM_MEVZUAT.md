INGEST_AYM_MEVZUAT.md
0) Amaç ve kapsam


Amaç:


AYM kararları (Bireysel Başvuru, Norm Denetimi) ve


Mevzuat Bilgi Sistemi (mevzuat.gov.tr) konsolide metinlerini; güncel ve kanıtlı şekilde toplayıp, madde/paragraph bazlı indekslemek.




Kullanım senaryosu (avukat araması):


“E. 2023/9144 K. 2025/…”; “B. No 2019/12345”; “AYM Genel Kurul karar tarihi 02.10.2025”


“TBK m.344”, “RG 27836”, “TİY 14/2”, “kanun numarası 6098”


Özetle; numaralara dayalı aramalar (E/K/B./RG/madde), madde isimleri ve konu kelimeleri birlikte çalışmalı.




Tasarım ilkeleri:


Her chunk kanıtlı (kaynak URL + künye) olmalı.


Madde‑bazlı sürüm/diff (mevzuat) ve delta‑embed (yalnız değişen chunk) ile maliyet düşürülür.


Ham içerik (HTML/PDF) saklanır → gelecekte yeniden chunk/embedding mümkün olur (geri dönüş yok kaygısını bitirir).






1) Kaynaklar (resmî girişler)
# AYM (Anayasa Mahkemesi)
Portal (giriş sayfası):   anayasa.gov.tr/tr/kararlar-bilgi-bankasi/
Bireysel Başvuru KBB:      kararlarbilgibankasi.anayasa.gov.tr
Norm Kararlar KBB:         normkararlarbilgibankasi.anayasa.gov.tr

# Mevzuat (Konsolide metinler)
Mevzuat Bilgi Sistemi:     mevzuat.gov.tr
(Delta sinyali için)       resmigazete.gov.tr  [günlük sayı/“Mükerrer”]


Not: URL’leri robots/TOS’a uygun, nazik hızla çekin. Erişim kimlik doğrulaması istemeyen kamusal arayüzler hedeflenir.


2) Veri modeli (doc / chunk / payload)
2.1 doc_id kuralı (deterministik)


AYM – Bireysel Başvuru (BB):
doc_id = "aym:bb:{basvuru_no}:{decision_date}"
Ör: aym:bb:2023/9144:2025-10-02


AYM – Norm Denetimi (NORM):
doc_id = "aym:norm:{esas_yil}/{esas_no}-{karar_yil}/{karar_no}:{rg_no_or_decision_date}"
Ör: aym:norm:2023/13366-2025/44:32345


Mevzuat (MBS – madde bazlı):
doc_id = "mbs:{norm_code}:{article_no}:{version}"
Ör: mbs:6098:m.344/3:v7

norm_code = kanun/CBK/KHK/yonetmelik kodu (ör. “6098”), version = RG no/tarih kaynaklı artan sürüm.



2.2 Minimal docs alanları
doc_id, source('AYM_BB'|'AYM_NORM'|'MBS'),
doc_type('karar'|'kanun'|'yonetmelik'...), title,
decision_date (karar), rg_no, rg_date, effective_from, effective_to,
court('AYM'), unit('Genel Kurul'|'Birinci Bölüm'...), 
e_no, k_no, b_no, law_no(norm_code),
url (canonical), checksum (sha256 of normalized text),
is_current (bool), created_at, updated_at

2.3 chunks (sorgulanacak parça) – payload önerisi
chunk_id, doc_id, version, 
article_no (MBS) | paragraph_no (karar),
content (plain text), content_hash, token_count,
payload JSON:
{
  "source": "AYM_BB"|"AYM_NORM"|"MBS",
  "court": "AYM",
  "unit": "Genel Kurul"|"Birinci Bölüm"|null,
  "e_no": "2023/9144", "k_no": "2025/44", "b_no": "2023/9144",
  "decision_date": "2025-10-02",
  "rg_no": "32345", "rg_date": "2025-10-15",
  "law_no": "6098",
  "article_no": "m.344/3",
  "url": "https://…",
  "is_current": true,
  "chunk_version": 1,       # chunker kuralları değişirse artır
  "embed_version": 1        # embedding modeli değişirse artır
}


Arama/use‑case için kritik payload anahtarları: e_no, k_no, b_no, rg_no, law_no, article_no, unit, decision_date.


3) Chunking kuralları
3.1 AYM – Bireysel Başvuru


Özet (varsa): 1 kısa chunk (maks. 600–700 token).


Gerekçe: paragraf/parça başına 400–600 token; paragraph_no ver.


Başlık/öz gibi künye bloğu chunk metninin başına etiket satırı olarak eklenebilir (retrieval desteği):
[MAHKEME: AYM | BİRİM: Birinci Bölüm | B. NO: 2023/9144 | KARAR T: 02.10.2025]


Bu satır yer gösterici; kullanıcıya dönerken gizlenebilir.



3.2 AYM – Norm Denetimi


Özet/sonuç bölümü ayrı chunk (iptal/ret, yürürlüğe giriş).


Gerekçe bölümleri 400–600 token.


RG meta’sını (№/tarih) payload’a mutlaka ekleyin.


3.3 Mevzuat (MBS)


Madde‑bazlı split (m. 1, m. 1/A, m. 344/3 vs.).


Madde başına 1–2 chunk (512–800 token).


Versioning: MBS “değiştiren RG” bilgisine göre version++; değişmeyen maddeler yeniden embed edilmez (delta‑embed).


Madde diff’i üretin (UI için).



4) Arayan kişiye (avukat) göre indeksleme
Avukatların tipik sorguları:


Numara‑bazlı: “E.2023/9144 K.2025/558”, “B.No 2019/12345”, “RG 32345”, “6098 m.344”


Kurum/ünite: “AYM Genel Kurul”, “Birinci Bölüm 2024”


Konu: “mülkiyet hakkı”, “ifade özgürlüğü”, “uyarlama / aşırı ifa güçlüğü”


İndeks stratejisi (hybrid):


BM25 / OpenSearch alanları: content, title, e_no, k_no, b_no, rg_no, law_no, article_no, unit, court, doc_type.


TR analyzer + synonyms:
"E., Esas; K., Karar; B. No, Basvuru No, B No; RG, Resmi Gazete; m., madde;
TBK, Türk Borçlar Kanunu; TCK, Türk Ceza Kanunu; CMK, Ceza Muhakemesi Kanunu"


Regex normalizasyon (index-time):


E.? ?(?P<yil>\d{4})/?(?P<no>\d+) → E:{yil}/{no}


K.? ?(?P<yil>\d{4})/?(?P<no>\d+) → K:{yil}/{no}


B\.?\s?No → BNo


m\.?\s?(?P<madde>\d+(/[0-9A-Z]+)?) → m:{madde}




Dense vektör (Qdrant, 1024‑dim) + Cohere Rerank:


BM25 top‑k (örn. 200) → dense recall (örn. 200) birleştir → Rerank top‑20.


Böylece numara/keyword/madde sorguları birlikte güçlü çalışır.




ÖNEMLİ: Ham HTML/PDF’i sakla; chunk_version/embed_version alanlarını kullan. Bir gün chunk kurallarını iyileştirirsek tek komutla re‑chunk/re‑embed.


5) AYM – Bireysel Başvuru Connector (tasarım)
5.1 Listeleme stratejisi


UI’de sol filtrede Karar Tarihi / Yayın Tarihi var. Delta için Karar Tarihi ≥ dünkü önerilir.


İlk çağrıda network dinle: JSON uçları varsa (liste/ sayfa parametreli), HTTPX ile doğrudan çağır. Yoksa DOM fallback.


“Kullanıcı Kılavuzu”na göre kartlarda şunlar bulunur: B. No, Birim (Birinci/İkinci/Genel Kurul), Başvuru/Karar/Yayın tarihi, Başvuru Konusu → bunları meta olarak al.


5.2 Detay çekme


Liste satırında id/uuid varsa “detay” JSON uçlarını çağır; aksi halde “Yazdır/PDF” alanı varsa PDF’i indir → metin çıkar.


Künye: b_no, unit, decision_date, publication_date, rg_no/rg_date (varsa), result (ihlâl/kabul edilemez vb.).


5.3 Kod iskeleti (özet)
# src/connectors/aym_bb.py
class AymBBConnector(BaseConnector):
    source = "AYM_BB"

    def list_items_window(self, start: date, end: date) -> Iterable[ItemRef]:
        # Playwright ile aramayı tetikle, response JSON yakala (search/list/data)
        # rows -> ItemRef(key=f"AYM_BB:{b_no}:{decision_date}", metadata=row)
        ...

    def fetch(self, ref: ItemRef) -> RawDoc:
        # row içinde detail id varsa httpx ile detail JSON -> RawDoc(content_json=...)
        # yoksa sayfayı açıp 'Yazdır'/'PDF' yakala -> pdf bytes
        ...

    def parse(self, raw: RawDoc) -> CanonDoc:
        # JSON varsa doğrudan; PDF/HTML fallback parse
        # doc_id = f"aym:bb:{b_no}:{decision_date}"
        # meta: unit, result, rg_no/rg_date
        ...

    def chunk(self, doc: CanonDoc):
        # summary + gerekçe paragrafları (400–600 token)
        ...


6) AYM – Norm Kararlar Connector
6.1 Listeleme stratejisi


Arayüzde Esas/Karar no, RG tarihi/sayısı filtreleri bulunur.


Delta ingest: “Resmî Gazete tarihi ≥ dünkü” ile çok stabil.


Network’te liste JSON varsa doğrudan kullan; length/pageSize=100 gibi parametreleri deneyin.


6.2 Detay çekme


Detay JSON (varsa) → metin; yoksa PDF/Yazdır çıktısından al.


Künye: e_no, k_no, decision_date, rg_no, rg_date, unit (Genel Kurul ağırlıklı), subject, result.


6.3 Kod iskeleti
# src/connectors/aym_norm.py
class AymNormConnector(BaseConnector):
    source = "AYM_NORM"

    def list_items_window(self, start: date, end: date) -> Iterable[ItemRef]:
        # RG tarihine göre aralık; JSON yakala -> ItemRef
        ...

    def fetch(self, ref: ItemRef) -> RawDoc:
        # detail JSON veya Yazdır/PDF
        ...

    def parse(self, raw: RawDoc) -> CanonDoc:
        # doc_id = f"aym:norm:{e_no}-{k_no}:{rg_no or decision_date}"
        ...

    def chunk(self, doc: CanonDoc):
        # hüküm/özet ayrı; gerekçe paragrafları 400–600 token
        ...


7) Mevzuat Bilgi Sistemi (MBS) Connector
7.1 Hedef


Konsolide metin (kanun, CBK, KHK, yönetmelik, tebliğ...).


Madde‑bazlı normalizasyon ve version/diff:


MBS sayfalarında genelde “değiştiren RG no/tarih” dipnotu bulunur.


Her değişiklikte ilgili maddeye version++ verilir.




7.2 Delta stratejisi


Watchlist (sıklıkla kullanılanlar): TBK(6098), HMK(6100), TCK(5237), CMK(5271), TTK(6102), İİK(2004), KVK(6698), KİK(4734), KHK/CBK temel seti, vs.


Saatlik kontrol: sayfa ETag/Last-Modified veya content_hash değişti mi?


Günlük genel tarama: son 24 saatte RG’de değişen kalem varsa ilgili normu MBS’den çek.


7.3 Parse/normalize


Başlık, norm kodu (kanun no), yürürlük/mülga, değiştiren RG (no/tarih).


MADDE başlıklarını (regex: ^MADDE\s+(\d+[A-Z]?(/\d+)?)(\s*-\s*)?) tespit et; madde metnini ayrı al.


Doc/Chunk üretimi:


doc_id = mbs:{law_no}:{article_no}:{version}


payload: law_no, article_no, rg_no/rg_date, effective_from/to, is_current.




7.4 Kod iskeleti
# src/connectors/mevzuat_mbs.py
class MBSConnector(BaseConnector):
    source = "MBS"

    def list_items(self, watchlist: list[str]) -> Iterable[ItemRef]:
        # watchlist: ['6098','6100','5237', ...]
        # her normun konsolide sayfasını yield et (ETag/If-Modified-Since destekli)
        ...

    def fetch(self, ref: ItemRef) -> RawDoc:
        # HTML çek; RAW'ı 'raw/' altına kaydet (idempotent)
        ...

    def parse(self, raw: RawDoc) -> list[CanonDoc]:
        # Sayfayı madde bazında parçala; her madde için CanonDoc döndür (veya tek doc + çok chunk)
        # version bilgisini 'değiştiren RG' / yürürlük dipnotundan üret
        ...

    def chunk(self, doc: CanonDoc):
        # madde başına 1–2 chunk
        ...


8) Orkestrasyon (Airflow) & Zamanlama


aym_daily.py


01:30 – AYM_NORM (RG tarihine göre dün→bugün)


02:15 – AYM_BB (Karar tarihine göre dün→bugün)




mbs_hourly.py


08:00–20:00 arası saatlik watchlist kontrolü


04:00 – RG tetikli güncelleme (son gün değişen normları çek)




Her DAG: Lister → Detailer → Parser → Diff → Delta‑Embed → Index adımlarına kuyruk mesajları bırakır.



9) Indeksler (OpenSearch + Qdrant)
9.1 OpenSearch mapping (özet)
{
  "settings": {
    "analysis": {
      "filter": {
        "tr_stemmer": {"type":"stemmer","language":"turkish"},
        "synonyms": {
          "type":"synonym",
          "lenient": true,
          "synonyms": [
            "E., Esas",
            "K., Karar",
            "B. No, Basvuru No, BNo",
            "RG, Resmi Gazete",
            "m., madde",
            "TBK, Türk Borçlar Kanunu",
            "TCK, Türk Ceza Kanunu",
            "CMK, Ceza Muhakemesi Kanunu"
          ]
        }
      },
      "analyzer": {
        "tr_lex": {
          "tokenizer":"standard",
          "filter":["lowercase","asciifolding","tr_stemmer","synonyms"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "content":     {"type":"text","analyzer":"tr_lex"},
      "title":       {"type":"text","analyzer":"tr_lex"},
      "e_no":        {"type":"keyword"},
      "k_no":        {"type":"keyword"},
      "b_no":        {"type":"keyword"},
      "rg_no":       {"type":"keyword"},
      "law_no":      {"type":"keyword"},
      "article_no":  {"type":"keyword"},
      "unit":        {"type":"keyword"},
      "court":       {"type":"keyword"},
      "doc_type":    {"type":"keyword"},
      "decision_date":{"type":"date","format":"yyyy-MM-dd"}
    }
  }
}

9.2 Qdrant


Koleksiyon: legal_chunks_v1 (cosine, size=1024; Cohere embed v3).


Upsert: yalnız content_hash değişen chunk.


Payload: yukarıdaki payload JSON aynen.



10) Sorgu işleme (hybrid RAG geri getirme)


Önişleme:


Sorguda E., K., B No, RG, m. desenleri varsa saha çıkar (regex).


Bu sahaları BM25 filtre boost olarak kullan: e_no:2019/123 veya article_no:m.344/3 gibi.




Aday getirme:


BM25 top‑200 ∪ Dense top‑200 → birleştir.




Rerank (Cohere Rerank):


top‑N (örn. 20) → cevaplayıcıya kaynakla gönder.




Kaynak gösterimi:


Kullanıcıya E/K/B/ RG / madde ve URL’ler görünsün (kanıtlı).




11) Kalite, test ve güvence


Smoke test (her connector):


Bir pencere/filtre ile ≥ 5 kayıt gelsin; doc_id deterministik; payload kritik alanlar dolu.




Idempotency: Aynı kayıt iki kez işlendiğinde tek doc/chunk olmalı.


Eval (geri getirme):


200 soru seti. Recall@50 ≥ 0.95, nDCG@10 ≥ 0.85, Kaynaklı cevap ≥ %95.




Loglama & metrik:


ingested_docs_total{source}


delta_embed_queue_lag


errors_total{stage, source}


ingest_latency_seconds{source}




12) Hata/kenar durumları


AYM metinleri bazen yalnız PDF: PDF’ten çıkarılan metinde sayfa numarası/paragraf kayması olabilir → chunk öncesi normalize_whitespace() uygulayın; paragraf başlıklarını (I., II., A., B.) koruyun.


MBS maddelerinde alt fıkra/ibare değişiklikleri: article_no aynı kalır; version++ ve effective_from/to ayarlanır. Diff görünümü için eski sürümü sakla (is_current=false).


Aynı kararın UYAP/AYM kopyaları: content_hash ile dedup (aynı metne iki embedding yok).




13) Hızlı çalışma yönergesi (developer için)


Ortam: Docker compose (Postgres, Qdrant, OpenSearch, Redis, Airflow) + .env.


Connector’lar:


AymBBConnector, AymNormConnector, MBSConnector dosyalarını oluştur.


Playwright ile response JSON yakalamayı dene; varsa httpx ile doğrudan çek.




Backfill:


AYM: --window month (veya 14 gün) + “Karar/ RG tarihi” pencereleri.


MBS: “watchlist” (6098, 6100, 5237, 5271, 6102, 2004, 6698, 4734…); ilk koşuda tüm maddeleri al.




Delta:


AYM BB/NORM günlük; MBS saatlik + RG tetikli.




Embedding’i ayır: ingest sırasında yalnızca metin yaz; embed_worker delta tüketir.


Doğrula: 10 kaydı kontrol listesiyle insan gözüne göster (küne/URL/metin).




14) Örnek payload’lar
AYM_BB (Bireysel)
{
  "doc_id": "aym:bb:2023/9144:2025-10-02",
  "source": "AYM_BB",
  "doc_type": "karar",
  "title": "HÜLKİ GÜNEŞ Başvurusuna İlişkin Karar",
  "court": "AYM",
  "unit": "Birinci Bölüm",
  "b_no": "2023/9144",
  "decision_date": "2025-10-02",
  "publication_date": "2025-10-15",
  "rg_no": "32345",
  "url": "https://kararlarbilgibankasi.anayasa.gov.tr/…",
  "is_current": true
}

AYM_NORM (Norm denetimi)
{
  "doc_id": "aym:norm:2023/13366-2025/44:32345",
  "source": "AYM_NORM",
  "doc_type": "karar",
  "court": "AYM",
  "unit": "Genel Kurul",
  "e_no": "2023/13366",
  "k_no": "2025/44",
  "decision_date": "2025-03-10",
  "rg_no": "32345",
  "rg_date": "2025-03-25",
  "url": "https://normkararlarbilgibankasi.anayasa.gov.tr/…",
  "is_current": true
}

MBS (Madde)
{
  "doc_id": "mbs:6098:m.344/3:v7",
  "source": "MBS",
  "doc_type": "kanun",
  "title": "Türk Borçlar Kanunu",
  "law_no": "6098",
  "article_no": "m.344/3",
  "rg_no": "27836",
  "rg_date": "2011-02-04",
  "effective_from": "2011-07-01",
  "effective_to": null,
  "url": "https://www.mevzuat.gov.tr/…",
  "is_current": true
}


15) SSS (kısa)


“Sonradan chunk kurallarını değiştirirsek?”
Ham HTML/PDF saklanıyor; chunk_version arttırıp yeniden chunk+embed yaparız (mevcut indeksleri upsert).


“Avukat numarayla aradı ama boş?”
Regex normalizasyonu genişletin (E 2023/…, E:2023/…, “Esas 2023/…”); synonym listesini güncelleyin.


“Süre/performans?”
AYM listeleri genelde JSON ile dönüyor; pageSize=100 + 2–3 worker ile dakikada binlerce satır çekilebilir. MBS saatlik/delta minimal yük.




Bitti.
Bu dokümanla yeni geliştirici; AYM (BB+Norm) ve MBS toplayıcılarını yazıp günlük delta ve madde‑bazlı sürüm/diff akışını kısa sürede ayağa kaldırabilir. Eğer istersen bir sonraki adımda gerçek Python dosyalarını (Playwright/httpx kullanan connector ve Airflow DAG’leri) da buraya ekleyebilirim.
