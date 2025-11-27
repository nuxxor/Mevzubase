# GPU OOM Notu (BGE-m3 embedding)

**Sorun**: `scripts/yargitay_local_pipeline.py` ile `BAAI/bge-m3` (SentenceTransformer) GPU’da embedding yaparken CUDA OOM veriyor. 31 GB GPU’da `--batch-size 4 --limit 500` denemesinde ~16–256 GB tahsis isteği yüzünden düşüyor.

**Gözlemler**
- Model: `BAAI/bge-m3` (xlm-roberta tabanlı, büyük). GPU belleği 31 GB; serbest bellek ~10–16 GB iken OOM.
- Denenen komutlar:  
  - `--device cuda --batch-size 4 --limit 500 --recreate` → OOM  
  - `--device cuda --batch-size 4 --limit 500 --recreate` (tekrar, daha küçük batch) → yine OOM
- Qdrant boş; koleksiyon oluşsa bile embed aşaması tamamlanmadı.

**Geçici çözüm (garantili)**: CPU ile küçük batch (8) ve gerekirse limit kademeli artırmak. Yavaş ama çalışır.

**GPU’da çalıştırma seçenekleri (önce hızlı test)**
1) Batch’i 1’e düşür, expandable allocator aç:  
   ```bash
   PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
   python scripts/yargitay_local_pipeline.py \
     --chunks-path cleaned/chunks_2005/yargitay_2005_chunks.ndjson \
     --collection yargitay_chunks_local_v1 \
     --qdrant-url http://localhost:6333 \
     --device cuda \
     --batch-size 1 \
     --limit 500 \
     --recreate
   ```
   Test geçerse `--limit`’i kaldırıp aynı batch-size ile tam yük.
2) Modeli küçült: `BAAI/bge-base-tr` veya `BAAI/bge-small` benzeri (Türkçe kapsaması doğrulanmalı). Komut aynı, sadece `--model` değişir.
3) Sequence boyunu kısalt (kod değişikliği): `SentenceTransformer` yüklemesi sonrası `model.max_seq_length = 512` veya daha küçük; hafıza düşer, hafif doğruluk kaybı olabilir.
4) Batch aralarında cache boşaltmak için kodda `torch.cuda.empty_cache()` eklenebilir; etkisi sınırlı.

**CPU komut (çalışması beklenen)**:
```bash
python scripts/yargitay_local_pipeline.py \
  --chunks-path cleaned/chunks_2005/yargitay_2005_chunks.ndjson \
  --collection yargitay_chunks_local_v1 \
  --qdrant-url http://localhost:6333 \
  --device cpu \
  --batch-size 8 \
  --limit 500 \
  --recreate
```
Geçerse `--limit`’i kaldırıp full 2005, ardından 2006–2009’u `--recreate` olmadan ekle.

**Sonraki adım önerisi**: GPU’da kalmak istiyorsak önce 1) batch=1 + expandable allocator ile 500’lük test; olmazsa 2) daha küçük model; olmazsa 3) CPU ile embed edip devam. 2010+ scrape bitince aynı koleksiyona ekleme yapılacak.***
