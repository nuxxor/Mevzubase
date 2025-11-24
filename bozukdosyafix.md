bozukdosyafix
============

Özet
- Yargıtay NDJSON’larda karakter bozulması ve 2005’te duplikasyon vardı.
- `legal-etl/scripts/clean_yargitay.py` ile dedup + karakter normalize + kısa kayıt filtreleme yaptık; çıktı `legal-etl/cleaned/` altına yazıldı.
- PowerShell konsolu UTF-8 göstermiyor olabilir; dosya içeriği UTF-8 düzgün.

Neler yapıldı
- Dedup: `doc_id` bazlı; 2005’teki ikili kopyalar atıldı.
- Karakter düzeltme: charmap ile `Ç¬/Ç÷→ü/ç`, `Çô/Çó→ö`, `Žñ→ı`, `Žø→İ`, `?→ğ`, `Y/ƒ?Y→ş`, `ƒ?O→Ş`, `Å→ç` vb.
- Whitespace sadeleştirme, basit boilerplate filtresi (`[KAYNAK:...]`, “İçtihat Metni”).
- Çok kısa kayıtlar (varsayılan `<50` char) elendi.

Script kullanımı
- Temizleme (mevcut): `python legal-etl/scripts/clean_yargitay.py --input-glob "legal-etl/yargitaydocs/yargitay_*.ndjson" --out-dir legal-etl/cleaned`
- Chunk üretmek için (isteğe bağlı): `python legal-etl/scripts/clean_yargitay.py --input-glob "legal-etl/yargitaydocs/yargitay_*.ndjson" --out-dir legal-etl/cleaned --chunk-dir legal-etl/chunks --max-chars 3500 --overlap-chars 400`
- Kısa kayıt eşiği: `--min-chars` (varsayılan 50). Boilerplate’i tutmak için `--keep-boilerplate`.

Karakter görüntü sorunu
- Konsolda garip karakter görürseniz içerik yine de UTF-8’dir. Geçici çözüm: PowerShell’de `$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8` ya da Python ile direkt okuyup doğrulayın:
  `python -c "import json, pathlib; print(json.loads(pathlib.Path('legal-etl/cleaned/yargitay_2005_clean.ndjson').open(encoding='utf-8').readline())['text'][:200])"`

Yeni dosya eklendiğinde
- Aynı komutla temizleyip `legal-etl/cleaned/` altına yazdırın; chunk gerekiyorsa `--chunk-dir` parametresini ekleyin.
