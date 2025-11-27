# Kural Kartları – Otomatik Kural Çıkarımı Fikri

Bu dosya, 9.5M Yargıtay (ve diğer) kararından otomatik “kural kartı” üretip, RAG/LLM katmanına entegre etme fikrini özetler. Amaç: Her senaryo için elle kural yazmadan, karar metinlerinden yapılandırılmış kural/istisna/holding çıkarıp LLM’e sağlam bir dayanak sağlamak.

## Neden?
- **Hallüsinasyon/aks kayması**: LLM açık/gizli ayıp, ihbar süresi, iğfal gibi ince ayrımlarda yanlış aks seçebiliyor (ör. açık ayıp + ekspertiz varken satıcıyı sorumlu tutmak).
- **Ölçek**: 50k+ farklı sorun tipi için tek tek “prompt kuralı” yazmak imkansız; karar korpusundan otomatik kural çıkarımı gerekiyor.
- **Tutarlılık**: Şemalı rule card’lar (issue, kural, istisna, holding, cite) LLM’e kılavuz vererek yanıtları normalize eder.

## Fikir: Kural Kartı Pipeline’ı
1) **Sınıflandırma**: Soru/olay ve/veya kararları hızlıca “issue” etiketlerine ayır (ör. satım/ayıp, kira, iş, aile). Bu, uygun şemayı seçmek için yeterli granularitede olmalı.
2) **Karar Retrieval**: Etiketli alt-kümede (veya genel korpusta) ilgili top-N kararları embed + vektör aramayla çek.
3) **LLM çıkarım (map/reduce)**: Her karar için şemalı özet üret:
   ```json
   {
     "issue": "satım/ayıp",
     "facts_key": ["ekspertiz", "açık/gizli", "ihbar süresi", "iğfal/ağır kusur"],
     "rule": "...",
     "exceptions": ["..."],
     "holding": "...",
     "citations": ["19 HD 2015/8094", "..."],
     "confidence": 0-1
   }
   ```
   Reduce aşamasında benzer kartları birleştir, çoğulları teke indir.
4) **Kümeleme/Dedup**: Rule card embed’lerini kümele, tekrarları tekilleştir; düşük güvenli kartları at.
5) **Kural kartı indeksi**: NDJSON + vektör index (qdrant/pgvector) olarak sakla; “issue + holding + cite” alanlarına göre query edilebilir hale getir.
6) **Sorgu zamanı entegrasyon**:
   - Soru → issue sınıflandır → ilgili rule card’ları retrieve (3–5 adet).
   - Karar snippet’leriyle birlikte LLM prompt’unda “kural kartı” bölümünü ekle.
   - Prompt’ta şema zorunluluğu: açık/gizli, ekspertiz, ihbar, iğfal gibi slotları doldur; cite zorunlu.
   - QA/guardrail: kaynak yoksa “emin değilim”; aks çelişiyorsa uyar.

## Beklenen Kazanımlar
- **Doğruluk**: Kural/istisna seçimi korpus dayanaklı olur; LLM “önceden öğrenilmiş” yerine “kurala bağlı” karar verir.
- **Tutarlılık**: Aynı issue için benzer aks ve gerekçe üretilir; prompt drift azalır.
- **Ölçeklenebilirlik**: Yeni kararlar geldikçe otomatik nightly/weekly batch ile kural kartı havuzu güncellenebilir.

## Açık Sorular / Araştırma Notları
- **Issue hiyerarşisi**: Kaç kategori yeter? (satım/ayıp, kira, iş, aile, ceza/şikayet, idare, vs.) Daha ince etiket gerekirse otomatik alt-küme keşfi (topic modeling) yapılabilir.
- **Confidence ölçümü**: LLM çıktısında güven skoru? İnsan onayı için sempl. Karara dayalı heuristik (öz/holding netliği, cite varlığı).
- **Kümeleme kalitesi**: Hangi embedding modeli (legal-tuned?) kart dedup için daha iyi? ManualChunks? 
- **Eval**: 20–50 senaryoda rule card destekli vs desteksiz cevapların kalite farkı; hallüsinasyon/aks hatası düşüşü.
- **Güncelleme sıklığı**: 9.5M korpus için tam batch pahalı; incremental/streaming güncelleme gerekebilir.

## Hızlı Başlangıç Önerisi
- Küçük bir `scripts/rule_card_extractor.py` ile top-20 karar çek → LLM map (JSON şema) → gerekirse dedup/merge → NDJSON kart üret. (İskelet dosya eklendi.)
- Basit issue setiyle (satım/ayıp, kira, iş) pilot çıkarım yap; kartları embed + qdrant koleksiyonuna yaz.
- yargitay_search reduce prompt’una “rule card” bölümü ekle, açık/gizli/ekspertiz/ihbar/iğfal slotlarını zorunlu kıl; cite-check yap.
- Pilot eval: mevcut ayıp senaryosunda yanlış aks (satıcı lehine/satıcı aleyhine) düzeliyor mu gözle.
