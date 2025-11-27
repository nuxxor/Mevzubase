# Dilekçe Modülü (Bağımsız, RAG’siz)

Bu modül, yerel LLM (Qwen/Ollama) ile şablon + QA destekli dilekçe taslakları üretir. RAG entegrasyonu kancası yoktur; tek başına çalışır.

## Bileşenler
- `petitions/schema.py`: Girdi/çıktı Pydantic şemaları (taraflar, olgular, deliller, talepler, istinaf/temyiz karar ref’i, tebliğ tarihi).
- `petitions/templates.py`: Dava/cevap/istinaf/temyiz/idari/suç duyurusu şablonları (başlık + bölüm sırası).
- `petitions/llm.py`: Yerel Qwen (Ollama HTTP) istemcisi ve statik test istemcisi.
- `petitions/generator.py`: Prompt → JSON bölüm üretimi → metin/HTML render → temel QA.
- `petitions/qa.py`: Zorunlu alan, rol, tebliğ tarihi, delil referansı eşleştirme, mahkeme adı kontrolü, 1. tekil/çoğul dil uyarıları.
- `petitions/renderer.py`: Metin ve HTML çıktısı (Times New Roman, 14pt, 1.5 satır aralığı).
- `petitions/export.py`: DOCX (python-docx) ve opsiyonel PDF (weasyprint) çıktısı.
- `scripts/petition_demo.py`: Hızlı demo (statik veya Qwen modu).
- `scripts/petition_web.py`: Bağımlılıksız mini web formu (yerel HTTP server).
- `scripts/petition_api.py`: JSON API `/generate` (POST) ile dilekçe üretimi.
- `frontend/petition/index.html`: CDN React ile hafif editör/önizleme (API’ye bağlanır).

## Çalıştırma
Örnek demo:
```bash
cd legal-etl
python -m scripts.petition_demo --mode static --format txt
# veya yerel Qwen (Ollama):
python -m scripts.petition_demo --mode qwen --format html
```
Çıktı varsayılan `petition_draft.txt` (txt) veya `petition_draft.txt/html` (html) dosyasına yazılır.

DOCX/PDF:
```bash
python -m scripts.petition_demo --mode static --format txt  # çıktı dosyasını export_docx/export_pdf ile dönüştürebilirsiniz
```
DOCX için `pip install python-docx` (PDF için `pip install weasyprint`) gerek. PDF yazımı yalnızca WeasyPrint kuruluysa çalışır; yoksa açık hata verir.

Basit web formu (test):
```bash
python -m scripts.petition_web --mode static --port 8000  # Qwen ile denemek için --mode qwen
# Tarayıcı: http://localhost:8000
```
(Bazı ortamlarda port açma yetkisi olmayabilir; izin/port ayarlarını gerekirse değiştirin.)

React önizleme (API + frontend):
```bash
# API'yi başlat (mode: static veya qwen)
python -m scripts.petition_api --mode qwen --port 9000
# Tarayıcıda frontend'i aç: legal-etl/frontend/petition/index.html
# (CORS için API 9000 ve frontend file:// veya aynı origin'de olmalı; varsayılan CORS açık.)
```
(React CDN kullanıyor; internet gerekir.)

## Yerel Qwen / Ollama
- Ollama servisini başlatın: `ollama serve`
- Modeli indirin/çalıştırın: `ollama pull qwen2.5:32b-instruct` (varsayılan model değişken `LocalQwenClient.model`; gerekirse kodda/ortamda değiştirin)
- API varsayılanı: `http://localhost:11434/api/generate`
- Gerekirse ortam değişkenleri: `OLLAMA_HOST`, `OLLAMA_MODEL` (şimdilik kod içinden değiştirilebilir).

## Test
```bash
cd legal-etl
pytest tests/test_petition_module.py
```

## Sonraki adım fikirleri
- DOCX biçimlendirmesini zenginleştirmek, PDF’yi stabil hale getirmek.
- Gelişmiş QA: süre hesaplama, mahkeme–dava tipi uyumu, ton/1. tekil filtreleri.
- Daha fazla şablon/örnek ve saha testi. 
