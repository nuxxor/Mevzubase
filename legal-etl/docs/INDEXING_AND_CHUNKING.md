INDEXING_AND_CHUNKING.md
Hedef


Yargıtay, EMSAL UYAP, AYM (BB+Norm), MBS (mevzuat) kaynaklarını kanıtlı ve avukat arama alışkanlığına uygun tek şemada indekslemek.


Embedding maliyetini düşük tutmak için delta‑embed (yalnız değişen chunk).


İleri analitik: içtihat eğilimi/karar değişimi tespiti.



1) Doc & Chunk Şeması (tek tip)
1.1 docs tablosu (örn. Postgres)
doc_id              TEXT  PK     -- deterministik
source              TEXT          -- YARGITAY | EMSAL | AYM_BB | AYM_NORM | MBS
doc_type            TEXT          -- karar | kanun | yonetmelik | ...
title               TEXT
court               TEXT          -- Yargıtay | BAM | AYM | ...
chamber/unit        TEXT          -- 3.HD | 4.Hukuk Dairesi | Genel Kurul | ...
e_no                TEXT NULL
k_no                TEXT NULL
b_no                TEXT NULL
law_no              TEXT NULL     -- 6098, 6100, ...
article_no          TEXT NULL     -- m.344/3 (MBS doc-level için NULL)
decision_date       DATE NULL
rg_no               TEXT NULL
rg_date             DATE NULL
url                 TEXT NOT NULL
checksum            TEXT NOT NULL -- sha256(normalized fulltext)
is_current          BOOL DEFAULT TRUE
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ

1.2 chunks tablosu
chunk_id            TEXT PK       -- hash(doc_id + part_no)
doc_id              TEXT FK
part_no             INT           -- 1..N
content             TEXT
content_hash        TEXT
token_count         INT
payload_json        JSONB         -- aşağıdaki anahtarlar
embed_version       INT DEFAULT 1
chunk_version       INT DEFAULT 1

payload_json zorunlu anahtarları:
{
  "source": "YARGITAY",
  "court": "Yargıtay",
  "chamber": "3. Hukuk Dairesi",
  "e_no": "2023/2580",
  "k_no": "2024/792",
  "b_no": null,
  "law_no": null,
  "article_no": null,
  "decision_date": "2024-02-27",
  "rg_no": null,
  "rg_date": null,
  "url": "https://karararama.yargitay.gov.tr/....",
  "aliases": ["E.2023/2580", "K.2024/792", "3.HD", "3. Hukuk Dairesi"],
  "legal_topic_tags": ["kira tespiti", "TBK 344", "uyarlama"],
  "anchor": "[KAYNAK:Yargıtay|DAİRE:3.HD|E:2023/2580|K:2024/792|T:2024-02-27]"
}


aliases ve anchor geri getirme ve doğruluk için kritik.


2) doc_id kuralları


Yargıtay: yargitay:{daire}:{E}-{K}:{YYYY-MM-DD}


EMSAL: emsal:{daire/katalog}:{E}-{K}:{YYYY-MM-DD}


AYM BB: aym:bb:{basvuru_no_primary}:{decision_date}


AYM NORM: aym:norm:{esas}-{karar}:{rg_no_or_date}


MBS madde (chunk’tan doc üretirsen): mbs:{law_no}:m.{article_path}:v{version}


MBS doc-level (opsiyonel): mbs:{law_no}:v{version}



3) Chunking kuralları
3.1 Kararlar (Yargıtay/EMSAL/AYM)


Bölüm başlıklarına göre kes: ÖZET, GEREĞİ DÜŞÜNÜLDÜ, GEREKÇE, HÜKÜM/SONUÇ.


Chunk başında anchor satırı:
[KAYNAK:{COURT}|DAİRE/ÜNİTE:{...}|E:{...}|K:{...}|T:{...}]


Token hedefi: 400–700. 850+’de sert kes.


İlk chunk mümkünse özet/künye.


Payload: aliases (E./K., daire kısa adı “3.HD”, “4.HD”, “Genel Kurul” vs.), legal_topic_tags.


3.2 Mevzuat (MBS)


MADDE başlıklarını regex ile yakala; geçici m., ek m. varyantlarını dahil et.


Madde başına 1–2 chunk.


aliases:


["TBK m.344","6098 m.344","BK 344","TBK 344","6098/344","m.344/III"]




versioning: her RG değişikliğinde version++; değişmeyen maddeler re‑embed edilmez.




4) İndeksleme (OpenSearch + Qdrant)
4.1 OpenSearch mapping (özet alanlar)


content, title → turkish analyzer + synonym filter


e_no, k_no, b_no, rg_no, law_no, article_no, chamber/unit, doc_type → keyword


decision_date → date


aliases[], legal_topic_tags[] → keyword


4.2 Qdrant


Koleksiyon: legal_chunks_v1 (cosine, 1024‑dim).


Upsert: content_hash değiştiyse.


Payload’a tam payload_json’u koy.


4.3 Sorgu yürütme (Hybrid)


Saha çıkar: Regex ile sorgudan E/K/BNo/RG/madde yakala → BM25 filtre/boost.


Aday getir: BM25 top‑200 ∪ Dense top‑200.


Rerank: Cohere Rerank → top‑20.


Cevap: Kaynak link + künye zorunlu.



5) “İçtihat değişti mi?” analizi
5.1 Topic‑window kıyası


legal_topic_tag="TBK 344" ve court in (Yargıtay, AYM) için:


Zaman pencereleri: [-10..-5 yıl] ve [son 5 yıl].


Her pencere için chunk embedding centroid hesapla (mean).


Cosine farkı + anahtar cümle (keyphrase) çıkar → “eğilim raporu”.




5.2 Yakın içtihatlar


Her yeni karar için: aynı legal_topic_tags ve yakın E/K formatında cosine > 0.80 olan 10 karar → “benzer kararlar”.




6) Delta & Zamanlama


Yargıtay/EMSAL/AYM: günlük Karar Tarihi ≥ dünkü (ay/14‑gün pencereleri).


MBS: saatlik watchlist + RG tetikleyici (yeni sayı yayımlandığında ilgili normu MBS’den çek).


Embed worker: ayrı kuyruk; yoğun dönemde yatay ölçeklenir.



7) Synonym/Alias başlangıç seti
E., Esas
K., Karar
B. No, Basvuru No, BNo
RG, Resmî Gazete
madde, m., m
TBK, Türk Borçlar Kanunu
TCK, Türk Ceza Kanunu
CMK, Ceza Muhakemesi Kanunu
HMK, Hukuk Muhakemeleri Kanunu
TTK, Türk Ticaret Kanunu


8) QA Kontrol Listesi


Her chunk’ta kaynak URL ve anchor var mı?


doc_id deterministik mi (aynı kayıtta değişmiyor mu)?


aliases[] boş değil mi (en az E./K. ya da madde alias’ı)?


Embedding yalnızca content_hash değiştiğinde mi atılıyor?


Örnek sorgular (manuel):


“TBK 344/3 uyarlama”  → TBK m.344/3 ve ilgili içtihatlar ilk sayfada mı?


“E.2023/2580 K.2024/792 3.HD” → ilgili karar ilk 3 sonucu mu?


“AYM Genel Kurul ifade özgürlüğü 2024” → BB/Norm doğru karışım mı?




Bitti.
Bu şemayla: (1) bugün topladığın Yargıtay/EMSAL, (2) sıradaki AYM ve MBS, ileride SPK/BDDK gibi kaynaklar da aynı formatta problemsiz eklenir. “İçtihat değişti mi?” analitiklerini de bu indeks üzerinde kolayca koştururuz.
