# Operasyon: op-yargitay-dict-2005

Amaç: 2005 Yargıtay karar korpusundan CPU tabanlı frekans/co-occurrence tabanlı bir “hukuk sözlüğü” çıkarıp anahtar kelime üretiminde kullanılabilir hale getirmek (GPU yok, embedding yok, lokal rerank yok).

## Varsayımlar
- Kaynak formatı: kararlar JSON/NDJSON/CSV/SQLite benzeri bir yapıda; her kayıtta en azından `tam_metin` (veya html), `ozet` ve meta alanları (tarih, daire, karar no) var.
- Metinler HTML ise temizleme `yargitay_search.py` içindeki `_html_to_text` benzeri bir filtreyle yapılacak.
- Çalışma ortamı CPU ağırlıklı (Intel 14900KF); RTX 5090 kullanılmayacak.

## Çıktılar
- `data/keyword_hints.json`: madde→top kavramlar, suç→top kavramlar (co-occurrence tabanlı) + düşük frekanslı gürültü ayıklanmış listeler.
- `data/typo_map.json`: en sık görülen yazım hatası → doğru yazım.
- İsteğe bağlı: `data/stop_terms.json` (çok geniş kavramları strict’ten temizlemek için).

## Önerilen adımlar (2005)
1) **Ham veri okuma**: 2005 dump’ı parça parça oku, metin/özet alanlarını çıkar (HTML ise temizle).
2) **Normalize**: Unicode NFKC, Türkçe diakritik düzeltme (mevcut typo sözlüğü + otomatik ASCII fold).
3) **Token & n-gram sayımı**: unigram/bigram/tri-gram frekanslarını çıkar; düşük frekans (<5) at.
4) **Kanun maddesi eşlik analizi**: `LAW_PATTERN` ile tespit edilen maddelere eşlik eden top n-gram’ları (örn. top 20) hesapla.
5) **Suç/usul kavramı eşlik analizi**: mevcut suç/procedure seed setiyle co-occurrence çıkar.
6) **Typo adayları**: ASCII fold edilmiş biçimiyle eşleşmeyen ama yüksek frekanslı token’ları topla; manuel doğrulama listesi üret.
7) **Export**: JSON dosyalarını `data/` altına yaz; kullanım için `build_query_buckets` entegrasyonuna hazır formatta tut.

## Notlar
- İşlem CPU ile paralel yapılabilir (multiprocessing/pandas); GPU kullanılmayacak.
- Tamamlandığında aynı pipeline 2006–2008’e de uygulanabilir; sonuçlar incremental birleştirilebilir.
