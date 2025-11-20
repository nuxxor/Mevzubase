Executive Summary

The optimal solution is likely a hybrid architecture that maximizes local control while selectively leveraging cloud APIs for specific tasks. In our analysis, Setup A (Self-Hosted) can achieve comparable retrieval quality (≈90–95% of Setup B) by using modern open-source multilingual embeddings and a local cross-encoder reranker, all while staying within the budget (∼$500/month). Setup B (Fully Managed Cloud) offers ease of use and slightly higher baseline accuracy, but at a dramatically higher cost – especially due to the expensive reranking API – and raises data compliance concerns. We recommend a hybrid: self-hosted Qdrant for vector search and a local cross-encoder, combined with cloud-based embedding generation (if needed for quality) and the Claude API for final answer generation. This yields high quality (>90% of the fully managed approach) at a fraction of the monthly cost, and keeps sensitive legal data on-premise. Key findings:

Quality: Larger 1024-d embeddings (Cohere v3) show only modest gains over 384-d models on retrieval tasks, especially once a strong reranker is applied. Removing 50% of embedding dimensions causes <10% drop in retrieval performance
aclanthology.org
, indicating diminishing returns for higher dimensions. Cross-encoder reranking provides a significant boost in precision and nDCG – e.g. one study saw nDCG@10 improve by ~21% with a reranker
python.plainenglish.io
. Open-source models like BGE and E5 are competitive with Cohere on multilingual benchmarks, often within a few points of nDCG
greennode.ai
. Thus, Setup A’s retrieval quality can closely approach Setup B’s (within ~5–10% on metrics like P@5, nDCG@10).

Cost: Setup B’s ongoing costs would far exceed the budget. Qdrant Cloud clusters for our data size (tens of millions of vectors) run in the hundreds per month (e.g. ~$130/month for 8GB instance
reddit.com
; scaling to 64GB+ RAM with HA pushes this toward ~$1000/month). Cohere’s APIs add heavy usage costs – Embedding is $0.10 per 1M tokens
agentset.ai
 (negligible for query text, but ~$300–900 one-time to embed 9M docs), while Rerank is $2 per 1000 input tokens
llmpricingtable.com
llmpricingtable.com
. Reranking even 10–20 documents per query would cost $3–$6 per query, or tens of thousands monthly at our volume – not sustainable. Claude’s generation costs are moderate ($3 per million input tokens, $15 per M output for Sonnet 4.5
claude.com
claude.com
) – roughly $0.01–$0.02 per query in our use case – and can be cut ~90% for repeated prompt parts with caching
claude.com
claude.com
. Setup A avoids most of the cloud costs: aside from Claude, it mainly incurs power, hardware and maintenance costs (est. $50–$100/mo electricity for a 24-core + RTX 5090 server, plus disk/backup and admin overhead). The break-even point is very low – even at a few hundred queries/day, the cloud reranker alone would cost more than the entire self-hosted stack.

Performance: Both setups can meet acceptable latency (P95 <2s). Setup A offers lower end-to-end latency once the system is warmed up, since local inference avoids network calls. A self-hosted Qdrant (Rust, HNSW index) can handle on the order of tens of queries per second on million-scale data with sub-100ms vector search latency
medium.com
medium.com
. (In one benchmark, Qdrant achieved ~81 QPS on a 5M vector dataset with ~98.5% recall
medium.com
, ~100ms average query time
medium.com
.) Qdrant Cloud should be similar in throughput (with adequate CPU/RAM provisioning), though network overhead adds ~10–20ms. The local cross-encoder on an RTX 5090 is extremely fast – a lightweight model (e.g. MiniLM-based) can rerank ~100 passages in under 0.5s, i.e. hundreds of passages/sec throughput. By contrast, the Cohere Rerank API would add network latency and likely operate sequentially over documents (the model processes each document–query pair up to 4096 tokens
docs.cohere.com
). Overall, Setup A can achieve ~P50 300–500ms per query (vector search ~50ms, rerank ~200ms for top-50) plus ~1s for Claude’s answer. Setup B might see ~P50 800ms–1.5s due to API calls (embedding + vector DB + rerank), and higher tail latencies (P95 2s+). Throughput is limited by cloud API rate limits in Setup B, whereas Setup A’s only bottleneck is GPU compute (which is scalable on-premise up to a few QPS easily).

Operational Factors: Setup B offers easier initial setup and fully managed ops (automatic scaling, failover, monitoring UI, and an uptime SLA from Qdrant Cloud
qdrant.tech
qdrant.tech
). It offloads maintenance but introduces external dependencies. Setup A requires engineering effort to deploy and monitor (self-hosted Qdrant will need manual updates, and you’d implement logging/alerts via open-source tools). Reliability-wise, Qdrant Cloud with HA can achieve high uptime (multi-AZ, auto-healing clusters
qdrant.tech
qdrant.tech
), whereas a single on-prem node is a single point of failure. Scaling the index in Setup A beyond one machine is non-trivial – Qdrant open-source supports only experimental clustering (or sharding data manually), so vertical scaling is the main path. In contrast, Qdrant Cloud allows easy horizontal scaling (adding more nodes or replicas via their console)
qdrant.tech
. Data privacy is a major differentiator: keeping 9M legal documents on local storage ensures sensitive text isn’t transmitted to third parties (aside from prompt excerpts to Claude). Setup B would send document embeddings (and possibly content for rerank) to external servers – a potential compliance issue for legal data. While Cohere/Anthropic have usage policies, the sovereignty and control with local storage is preferable for legal tech.

Given these findings, we recommend prioritizing Setup A or a Hybrid over a fully managed Setup B. The remainder of this report provides detailed comparisons and justifications.

1. Quality Analysis (Retrieval & Ranking)

Embedding Dimensions – 384d vs 1024d: Research indicates that jumping to very large embedding vectors yields diminishing returns in retrieval performance. High-dimensional embeddings can encode more nuance, but the gain is modest once you’re beyond a few hundred dimensions
milvus.io
. In fact, a recent EMNLP 2025 study found that randomly truncating 50% of dimensions causes <10% drop on retrieval and classification tasks
aclanthology.org
 – and in many cases less than 5% loss
aclanthology.org
. This suggests a 1024-d model won’t be dramatically better than a well-trained 384-d model for our use case. The extra dimensions often encode redundant information; many dimensions can even be pruned with minimal impact on metrics
aclanthology.org
aclanthology.org
. For specialized domains like legal text in Turkish, what matters more is the embedding training data and alignment to the domain language, rather than sheer dimensionality. A strong 384-d multilingual model that’s been tuned on diverse languages (or legal data) can outperform a 1024-d model trained primarily on other domains.

Multilingual Embedding Quality (Open-Source vs Cohere): Cohere’s latest embed-multilingual-v3.0 model is a high-quality 1024-d embedding model covering 100+ languages. It has been evaluated on standard benchmarks (e.g. MTEB) with an average nDCG around the low 60s
medium.com
, which is on par with state-of-the-art. However, open models have caught up: for example, the BGE-multilingual (BGE M3) and E5-large models are among the top performers on retrieval benchmarks, often matching or exceeding proprietary models in accuracy
greennode.ai
greennode.ai
. These open embeddings consistently top multilingual leaderboards like MTEB, far surpassing older baseline models (e.g. SBERT)
greennode.ai
. In multilingual tests, Cohere’s v3 is competitive – AgentSet reports an average nDCG@10 ≈0.78 for Cohere-multilingual-v3 vs 0.68 for Cohere-English-v3
agentset.ai
agentset.ai
, underscoring the importance of multilingual training. We did not find a Turkey-specific benchmark, but anecdotal evidence and the strong multilingual training of BGE/E5 suggest that open models can closely rival Cohere in Turkish legal document retrieval. Notably, being able to fine-tune open models on domain data (e.g. Turkish case law) can further narrow any quality gap
greennode.ai
greennode.ai
 – an option not available with closed APIs.

Retrieval vs Re-Ranking Improvements: A two-stage Dense Retrieval + Cross-Encoder pipeline is known to substantially improve result relevance. The first-stage (embedding) retrieval ensures high recall of potentially relevant docs, while the cross-encoder re-ranker re-evaluates those top results with superior precision. Studies on BEIR and MS MARCO have quantified this: a bi-encoder alone might achieve, say, nDCG@10 in the 40–50 range, whereas a cross-encoder (MonoBERT or MonoT5) re-ranking the top 10–100 can raise nDCG@10 by ~10–20 points in many cases. For example, in one biomedical/legal QA scenario, adding a cross-encoder boosted Precision@1 from 0.75 to 1.00 and nDCG@10 by 21.5%
python.plainenglish.io
. Similarly, the BEIR leaderboards show that a BM25 or dense retriever alone is often outperformed by 20–30% (relative) when using a reranker
elastic.co
aclanthology.org
. We can expect our system to follow suit: the cross-encoder will correct false positives and surface subtle matches (e.g. understanding legal synonyms or negation that the bi-encoder missed). The improvement is especially pronounced for nuanced legal queries, where context matters (e.g. distinguishing “temyiz” (appeal) in different contexts).

Local vs Commercial Models for Reranking: The Cohere Rerank v3.5 model is a powerful multilingual reranker (trained on English and non-English data) and presumably would handle Turkish inputs (it “supports the same languages as embed-multilingual-v3.0” per Cohere docs
docs.cohere.com
). However, local alternatives exist. The proposed BGE-reranker-v2-m3 is likely a multilingual MiniLM or similar cross-encoder fine-tuned for retrieval. These smaller cross-encoders (≈110M parameters) have demonstrated surprisingly strong performance. For instance, MiniLM-based cross-encoders fine-tuned on MS MARCO can achieve nearly the same rerank effectiveness as BERT-large cross-encoders at a fraction of compute. While we don’t have a direct benchmark of BGE-reranker vs Cohere Rerank, it’s reasonable to expect the gap to be small – potentially a few percentage points in metrics like MRR or nDCG. Both are transformer-based models scoring query–document pairs. If needed, one could even fine-tune the local reranker on a small set of Turkish legal QA pairs to specialize it (Cohere’s model cannot be custom-trained).

Expected Precision@5 / Recall@10 / nDCG@10: Taking all the above into account, we estimate Setup B’s fully-managed pipeline might achieve (hypothetically) something like 5–10% higher Recall@10 and nDCG@10 than Setup A out-of-the-box. For example, if Cohere embeddings + rerank could get nDCG@10 ≈ 0.80 on our evaluations, the local Setup A might reach ~0.72–0.75 – i.e. >90% of the quality. Precision@5 (a high-precision metric) would be very close between the two, since that heavily depends on the cross-encoder. With both approaches using a cross-encoder, we expect Prec@5 difference < 5%. In fact, the local Setup A might have an edge in some cases if we fine-tune models on domain data. Domain-specific embedding fine-tuning (e.g. a hypothetical “TurkLegal-BERT” embedding) could yield better recall of niche concepts than a general API model. There is ongoing research in Turkish legal embeddings (e.g. TurkEmbed4Retrieval project) showing that domain-specific training improves retrieval of court decisions
arxiv.org
. Incorporating such techniques in Setup A could further shrink the gap.

In summary, Setup A can meet the quality requirements (>90% of cloud setup). By using a modern multilingual embedding (384-d or 768-d) and an effective reranker, it will retrieve nearly the same relevant cases as Setup B. The fully-managed Setup B might eke out slightly higher raw recall (especially on out-of-domain queries) due to its larger embedding model, but the difference in final answer quality is minor. Given that answer generation (Claude) is the same in both setups, users are unlikely to notice a quality difference in practice. Both approaches should satisfy legal professionals by finding on-point precedents and pertinent statutes with high accuracy, especially after tuning.

2. Cost Analysis

Below we break down the expected monthly costs for Setup B (Managed Cloud stack) versus Setup A (Self-hosted). All costs are in USD. We assume ~30,000 queries per month (about 1,000 per day) as given, and include any one-time or initial costs separately.

Setup B – Managed Cloud Services: This includes Qdrant Cloud, Cohere APIs, Claude API, and cloud storage. High-availability (HA) configurations are assumed for critical components (vector DB).

Service Component	Monthly Cost (Estimate)	Details & Assumptions
Qdrant Cloud – 32GB	~$250 (HA)
($125 without HA)	Managed vector DB. 32GB RAM cluster with 2×replicas for HA. Based on user reports: e.g. 8GB costs ~$130/mo with redundancy
reddit.com
, so 32GB ≈$500; we assume improved efficiency/usage yields ~$250. A 64GB HA cluster would be ~$500–600/mo.
Qdrant Cloud – 64GB	~$500 (HA)
($250 without HA)	64GB cluster needed if ~60–70M vectors loaded in memory. (One benchmark indicates ~67GB for 10M vectors
github.com
. Using INT8 quantization, memory needs drop ~4×.) Cost interpolated from smaller sizes and alternative hosting quotes (e.g. ~ $120–150/mo for 64GB single-node
github.com
). With HA replication, roughly double.
Cohere Embed API	$5–$10	Assuming ~30k queries (short texts) + occasional new documents. Cohere charges $0.10 per 1M tokens
agentset.ai
. 30k queries * ~20 tokens avg = 0.6M tokens ⇒ $0.06. Negligible for queries. The main cost is one-time embedding of 9M docs: e.g. 9M docs * ~500 tokens each = 4.5B tokens ⇒ ~$450 (one-time). Amortizing that over 12 months = ~$37/mo.* So monthly usage ~$5 + one-time indexing amort. (If using 1024-d “embed-v3” at same price as 384-d.)
Cohere Rerank API	Very high – not feasible at scale	Cohere Rerank v3.5 is $2 per 1K input tokens
llmpricingtable.com
. For 30k queries, if we rerank 10 results (each ~300 tokens), that’s ~90M tokens = $180,000! This cost is prohibitive. Even with 5 results, ~$90k/month. (No subscription plan currently mitigates this). In practice, one would not use the API for all queries due to cost – or use a smaller reranker model if offered (Cohere doesn’t have a cheaper tier for rerank).
Claude API (Sonnet 4.5)	~$300 (no caching)
~$200 (with caching)	Anthropic pricing: $3 per million input tokens, $15 per million output
claude.com
. Assuming each query sends ~1500 input tokens (prompt, retrieved text) and gets 300 output tokens: that’s 0.0015M*$3 + 0.0003M*$15 ≈ $0.006 + $0.0045 = $0.0105 per query. For 30k queries, ~$315/month. With prompt caching of repeated instructions/context, input cost can drop ~80–90%. E.g. caching 500 tokens of system prompt: first-time “write” cost $3.75/M
claude.com
, reuse “read” cost $0.30/M
claude.com
. If ~30% of the 1500 tokens are cached, we save ~$0.0015/query. New cost ≈$0.009/query → ~$270/mo. We estimate ~$200–$250 after caching optimizations.*
Cloud Storage (S3)	~$50	Storage for 9M raw docs (PDF/HTML). Assuming ~200GB of data, at $0.023/GB = ~$4.6/mo, plus extra for backups, retrieval and overhead. Rounding up for data transfer, etc. If using Qdrant disk storage for vectors, that is included in Qdrant cost (managed disks).
Support/Misc	~$50	AWS/GCP data transfer fees, Claude extended context charges (if using 200k+ context windows, billed at higher rate
claude.com
), monitoring services, etc.

Total Setup B: Approximately $600–$800 per month excluding the Cohere Rerank cost. In practice, including full reranking via API is infeasible (would be $100k+). A realistic cloud approach might omit Cohere’s rerank and rely on the vector search alone or a cheaper rerank method – but that would sacrifice quality. So, our cost assumes perhaps using rerank API only sparingly (or not at all) to remain within <$1000 budget. With that caveat, the core services (Qdrant, embed, Claude, storage) land around $700/month. Pushing to a 128GB HA Qdrant cluster (for ~90M vectors fully in-memory) would raise costs toward $1.2k+.

Setup A – Self-Hosted Infrastructure: We consider the operational expenses of running a 24-core CPU server with an RTX 5090 GPU and local storage. We assume the hardware is already acquired (or on lease) and focus on recurring costs.

Cost Component	Monthly Cost (Estimate)	Details & Assumptions
Server Hardware	CapEx (approx. $15k upfront)
or ~$600 amortized/mo	One-time purchase of a high-end server: 24-core CPU + 128GB RAM (~$5k), RTX 5090 (~$3k), NVMe SSDs for vector index and docs (~$2k), redundancy (RAID, extra storage, etc.), and other infrastructure (cooling, rack, etc.). If amortized over 2–3 years, this is ~$500–$600/mo. (If hardware is rented, e.g. a dedicated GPU machine, it might be $1000+/mo.) We exclude this from OpEx since budget focuses on recurring costs.
Power Consumption	~$80	Power draw of server ~500W on average (higher during heavy GPU use). 500W * 720 hours ≈ 360 kWh. At $0.10–$0.15/kWh, that’s ~$40–$55. Add cooling and peripheral overhead → ~$70–$90. (This assumes near-constant usage; idle or lower utilization will reduce kWh.)
Internet/Bandwidth	~$20	Business broadband or datacenter hosting of the server. Legal text isn’t extremely bandwidth heavy (embedding 9M docs locally avoids sending them over network). Mainly costs for keeping the server online. If hosted in a colocation, this might be bundled.
Storage & Backup	~$30	Depreciation or rental of storage media. 9M documents (let’s say 200–300GB) on local disk is negligible if you have a few TB NVMe. We include offsite backup: e.g. syncing data to a cloud bucket or tapes. 300GB on S3 with infrequent access ~ $7, plus some retrieval or glacier storage – say $20–30 total.
Maintenance (Labour)	~$0 direct
(Developer on-call)	No direct fee, but there is an implicit cost of engineers managing the system. We assume the team can handle monitoring, updates, and bug fixes as part of their duties. This “cost” is the time to apply Qdrant updates, replace failed drives, etc. (If valued, perhaps a few hours per week of an engineer’s time.) We list it as $0 monetary cost but note the overhead.
Software Licenses	$0	All components (Qdrant OSS, sentence-transformers, PyTorch, etc.) are open-source with no license fees.

Total Setup A: Approximately $130–$150/month in direct recurring expenses (power, internet, backup). If we include hardware amortization, it effectively “uses up” most of the $500/month preferred budget, but note that this is a capital investment – after ~2 years the equipment is paid off. The key point is that ongoing costs are very low compared to the cloud. The expensive items are up-front. Even factoring in $600/mo for hardware, the 3-year TCO of Setup A is far below the equivalent 3-year spend on cloud services.

Break-Even Analysis: The breakeven query volume where self-hosting becomes cheaper is extremely low in this scenario. This is primarily because of the Rerank API’s cost scaling. As shown, even a few hundred queries per day would incur thousands of dollars in Cohere rerank fees, blowing past Setup A’s fixed costs. If we imagine a cloud setup without the reranker, the main variable cost would be Claude API usage (which both setups share). Qdrant Cloud and embedding costs are more fixed or scale with data rather than queries. So the breakeven is essentially already reached at our initial volume (500–1000 q/day). To quantify:

At ~1,000 queries/day, Setup B might cost ~$20/day in Claude + negligible embed + fixed ~$20/day in Qdrant = ~$40/day (≈$1200/mo), not counting reranker. Setup A would cost maybe $5/day in power + hardware amortization (say $20/day) = $25/day (≈$750/mo). Even before reranking, Setup A is cheaper.

If we include reranking in cloud: even 100 q/day with 10 docs each (~0.5M tokens/day for rerank) = $1,000/day just for rerank – clearly not viable. So one would drop the reranker long before reaching a “breakeven” point.

In summary, Setup A becomes more economical essentially at any non-trivial query volume. The only scenario where Setup B could be cheaper is very low usage (e.g. <100 queries per month). In that case, one could stay within free tiers (1GB Qdrant free, minimal Claude usage). But our use case (20–30k queries/mo and growing) far exceeds that. By the time we reach even a few thousand queries per month, the self-hosted infrastructure pays off. As the user base grows 2–3× in the next year, the cost advantage of self-hosting will widen further – Setup A’s costs won’t increase much (power and maintenance may go up slightly for higher QPS, but not dramatically), whereas Setup B would scale roughly linearly with usage (especially if using usage-priced APIs).

One more note: The Claude prompt caching can significantly reduce that component of cost as query volume scales. If many queries reuse the same lengthy instructions or legal context, Anthropic’s prompt read rate of $0.30/M is 10× cheaper than normal input cost
claude.com
claude.com
. Implementing aggressive caching (e.g. caching system prompts, boilerplate legal text) could cut Claude spend by ~50% in practice – effectively increasing the queries/month possible within a given budget. We modeled both scenarios above; even without caching, Claude is not the budget bottleneck. The real cost drivers are the vector DB and reranker choices.

3. Performance & Scalability

We evaluate the throughput and latency of each approach across the components of the pipeline:

Vector Search Throughput (QPS): Qdrant (Rust) is built for high performance vector search. In a single-node deployment with HNSW, it can easily handle dozens of searches per second on millions of vectors
medium.com
. In fact, benchmarks show Qdrant ~80 QPS on 5M vectors with <100ms latency at high recall
medium.com
medium.com
. Our corpus is larger (up to ~90M vectors if each document is chunked), but we are using product quantization / INT8 to keep memory and compute manageable. On a 24-core CPU with fast NVMe, we anticipate at least 10–20 QPS capacity for the vector stage, which is more than enough (>100k queries/day). Qdrant Cloud can similarly scale – their managed service can partition data and use multi-core optimizations. If needed, one could add replicas to handle higher QPS (either in self-hosted by running a read-replica, or in cloud by adding a node via the console). Given our expected load (~0.3 QPS average, ~1–2 QPS peak), both setups easily handle throughput. The self-hosted Qdrant should be run in persistent mode (with on-disk storage) but with ample RAM cache – NVMe access is fast (<100 microseconds) but keeping hot portions of the index in memory will yield consistent low latency.

End-to-End Latency (per query): Both setups aim for P95 under 2 seconds, which is achievable. Let’s break down typical latencies:

Setup A (Local): Embedding query with a local model – ~20ms (for a 384-d MiniLM on CPU) or virtually 0 if we pre-embed common queries. Vector search – ~50–100ms (HNSW search over tens of millions, assuming ef parameter tuned for >0.9 recall). Local rerank – depends on number of hits reranked. If we rerank top-50: a small cross-encoder can score a pair in ~5–10ms on GPU, and we can batch them. For instance, 50 pairs in 5 batches of 10 → ~5 * 10ms = ~50ms. Even with overhead, reranking ~50 results should be ~50–150ms. Claude generation – this is the largest contributor: to output, say, a 2-paragraph answer (300 tokens), Claude might take ~1.5–2.5 seconds just in generation time (its throughput ~ ~150 tokens/sec). However, since the question says P95 <2s acceptable, perhaps the answers are short. If we restrict the answer length, Claude can respond in ~0.5–1.0s. The prompt processing time is usually minor (~100ms) relative to output. So total P50 for Setup A could be around 500ms – 1.2s (not counting Claude’s long outputs). P95 might be ~1.5s if a large answer is needed or GPU is under load. These figures assume moderate concurrency (our hardware could even parallelize a few queries at once).

Setup B (Cloud APIs): Embedding query – Cohere’s API responds in ~50–100ms typically for a short text embedding (plus network ~20ms). Qdrant Cloud vector search – perhaps ~50ms if data in memory, plus 10–20ms network overhead to send the query and get results. Cohere rerank – this is a potential latency bottleneck. If we send 10 documents to rerank-v3.5, the API must process each (the model will score each doc separately internally). They might do it in parallel under the hood, but the response time is at least hundreds of milliseconds, possibly ~300–500ms, given the model size and 10x documents (and including network). (If we attempted 50 docs, it could approach a second). Claude generation – similar ~1s for a short answer, but note we must send the retrieved documents over to Claude via API, which adds maybe 100ms overhead (Claude’s API has ~20–50ms latency plus streaming of results). Summing these: P50 might be ~800ms – 1.5s, P95 ~2.5s. In particular, the multi-call nature (client->Cohere, client->Qdrant, client->Cohere again, then client->Claude) accumulates latency. And any network hiccup can add variability.

Real-world measurements would be needed for precise numbers, but qualitatively Setup A has lower latency variability. Local GPU and CPU operate at consistent speeds, whereas cloud calls can sometimes queue or have cold-start delays. For instance, Cohere’s service might have occasional spikes. Claude’s API is the same for both – though one advantage in Setup A: you can cache prompts on your side more effectively (since you control when to reuse context).

Concurrency & Scaling: Setup A is currently a single-machine. It can handle a few concurrent queries easily (the GPU can batch or quickly context-switch the cross-encoder; the CPU has many cores for parallel HNSW queries). If query load grew 10x, one might need to scale up: options include adding another GPU server and partitioning the vector index (e.g. split the corpus by year or type between two Qdrant instances, and query both – since 9M decisions could be sharded). Qdrant open-source does support sharding in a cluster mode, but it’s relatively new – a simpler approach is vertical scaling (e.g. upgrade to 64-core CPU, more RAM). The RTX 5090 is very powerful; it can likely handle >100 qps for reranking if needed, so the GPU is not the bottleneck until query rates are extreme. Setup B scaling is more straightforward on paper: Qdrant Cloud can add replicas or increase pod size (just a higher bill), Cohere and Claude are serverless (they auto-scale, with rate limits that can be raised by request). However, one hidden scalability issue in Setup B is rate limiting and throughput cost: Cohere’s API might throttle requests if QPS is too high (default limits maybe ~100/min for free, more for paid). We’d likely need to negotiate higher limits for real-time use. Similarly, Anthropic has a per-minute token limit. These are solvable with enterprise plans, but it’s something to monitor. On latency under load, Qdrant Cloud with multiple concurrent queries might introduce tail latency if CPU is saturated – but with adequate provisioning, it stays low latency (their cloud likely uses autoscaling to maintain performance).

Pipeline P99 considerations: In legal search, some queries might retrieve an unusually large number of candidate passages (for example, a very general query like “TBK m.112” might pull thousands of results). We will likely cap the reranker input (e.g. top-50 or top-100). In Setup A, sending 100 passages to the local cross-encoder will linearly increase compute (~2× the 50-passages case, maybe 100–200ms). In Setup B, sending 100 to Cohere rerank is not feasible (both cost and context length – 100 * ~200 tokens each = 20k tokens, exceeding the 4096 limit per call
docs.cohere.com
). So we’d be forced to only rerank a subset, or do multiple API calls. That scenario would blow up latency or get truncated. Thus, ironically, Setup A can handle “bigger” queries more gracefully (at the cost of some more GPU time), whereas Setup B might have to drop recall to keep latencies in check.

Indexing and Updates: One performance aspect outside of query latency is indexing throughput. If we frequently update the corpus (say new court decisions added daily), Setup A can ingest documents by computing embeddings on the GPU (very fast – thousands per second for a 384-d model) and inserting into Qdrant. Qdrant’s index build for HNSW can be done in the background; it’s fairly efficient but for millions of points it takes time. The MyScale benchmark showed Qdrant took ~145 minutes to index 5M vectors
medium.com
 (others were faster), though that was presumably single-threaded index build. In practice, we might batch inserts or use Qdrant’s multi-thread optimization. Setup B could leverage Cohere’s embedding API for new data (slower than GPU but can be parallelized by making many requests). Qdrant Cloud’s indexing speed would be similar order of magnitude (they might even throttle large uploads to not impact the cluster). For occasional updates, this is fine. If a reindex of all 9M was needed, Setup A might actually be faster since it can use the GPU fully (embedding 9M docs ~ maybe a couple hours) and local disk IO – whereas pushing 9M docs through an API would be network-bound (though Cohere does have a batch job API option).

Overall, both setups meet our performance needs (moderate QPS, sub-2s latencies). Setup A offers more consistent and controllable performance, whereas Setup B offers elastic scaling (for a price) and convenience at the cost of some extra latency per call. Given that our users (lawyers/judges) likely value correctness over ultra-low latency, both 0.5s and 1.5s are acceptable. But the risk with Setup B is if the network or API slows down, we have less recourse; with Setup A, we can always optimize or upgrade hardware to maintain snappy performance.

4. Operational Considerations

Beyond raw performance and cost, we compare reliability, manageability, and compliance aspects of the two setups:

Reliability & Uptime: Setup B, using Qdrant Cloud with HA, is designed for high uptime. Qdrant Cloud provides auto-healing, backups, and zero-downtime upgrades as part of the service
qdrant.tech
qdrant.tech
. If a node fails, the replica takes over. They likely offer an SLA (perhaps 99.9% uptime) for managed clusters. Similarly, Cohere and Anthropic operate distributed clusters globally – these APIs are generally reliable, though not immune to outages. (Anthropic’s status page indicates good uptime; however, there have been instances of OpenAI/others hitting rate limit issues or regional outages for short periods). Setup A’s reliability rests on our own server hardware: a single server has inherent single-point-of-failure risk (disk failure, power outage, etc.). We can mitigate some with redundant PSUs, RAIDed disks, and a UPS backup. But achieving cloud-like 99.9% availability would require either a secondary failover server or accepting some downtime in worst-case failures. If uptime is mission-critical, one could mirror Setup A to a second machine (doubling hardware costs, akin to running your own HA cluster). In practice, if occasional maintenance downtime (e.g. a few minutes to reboot for updates) is acceptable, Setup A can be run in a mostly-available manner. We’d recommend at least daily offsite backups of the vector index and docs, so that if hardware fails, we can recover on a new machine within hours. Qdrant’s snapshot backup feature can help with this.

Monitoring & Alerting: Qdrant Cloud comes with central monitoring and log management
qdrant.tech
 – likely a web UI showing CPU/RAM usage, QPS, etc., and possibly integration to alert on high error rates. In Setup B, a lot of the infrastructure is monitored by the provider (we’d mainly watch our application and API usage). Setup A requires us to set up monitoring: we’d need to instrument Qdrant (it exposes Prometheus metrics), GPU/CPU utilization, and have alerting rules (e.g. if Qdrant not responding or vector search latency spikes). This is additional work: e.g. installing Prometheus + Grafana or using a service. Notably, Qdrant Cloud frees us from managing that – the trade-off is more DevOps effort in Setup A. Similarly, for the application logs (user queries, etc.), we’d set that up ourselves (which can be a benefit for customization but is effort). Debugging issues in Setup A means digging into server logs, possibly the Qdrant source if something goes wrong. In Setup B, if something fails (e.g. vector search times out), we have support to contact and a dashboard to consult. Qdrant Cloud’s support (standard with subscription) would assist in issues on their side
qdrant.tech
.

Scaling Strategy: If our usage grows, Setup B allows horizontal scaling fairly easily: we could increase Qdrant memory or replicas with a few clicks (or via their API)
qdrant.tech
, albeit with higher cost. We could also integrate a caching layer (e.g. use a Redis cache for frequent queries’ results) – that’s applicable to both setups. Setup A scaling is more vertical unless we invest in clustering Qdrant ourselves. We can still scale quite far vertically: e.g. upgrade to 256GB RAM, or add more disks, or a second GPU for parallel reranking. Eventually, if query load were extremely high (say tens of QPS consistently), we might consider running multiple Qdrant instances sharded by document type (for example, separate indices for civil, criminal, administrative case law, and merge results in the app). That would require our code to query multiple sources and merge, which is doable but more complex than cloud scaling. The cloud could handle that sharding behind the scenes if we simply pay for a bigger cluster. In summary, cloud is more convenient for scaling, but setup A can handle our projected growth (2-3×) with its existing headroom and perhaps a RAM upgrade.

Data Privacy & Compliance: This is a crucial factor for legal data. Setup A keeps all raw documents and vector representations on-premise (or at least on a server under our full control). That means no third-party ever sees the full text of decisions. In Setup B, there are multiple points where data is leaving our controlled environment:

When using Cohere’s embed API, the document text (or significant excerpts) are sent to Cohere’s servers. While Cohere’s policy is presumably not to store or misuse the data, many legal organizations have policies against sending sensitive content to external AI APIs. (Case law might be public, but any confidential notes or even just the act of querying certain things could be sensitive.)

Using the rerank API would send chunks of documents and queries to Cohere as well, compounding this issue.

Qdrant Cloud means vector data (which might indirectly contain information about the documents, though not reversible, it’s still derived data) resides on a third-party cloud (could be AWS or GCP via Qdrant). If the data must remain in-country (Turkey) for sovereignty, Qdrant Cloud might not guarantee that (unless they offer a region in EU or Turkey – currently likely in EU/Germany for Legal Tech use as per their site).

Claude API: regardless of Setup A or B, we are using Claude via API. This will send the user’s query and retrieved snippets to Anthropic’s servers (likely in US). That is one area of potential concern for GDPR or privacy if any personal data is in those snippets. We would need to have a data processing agreement with Anthropic or use their Claude Instant (cheaper model) deployed on premises (not currently an option). This is a known trade-off; since we require a strong LLM, we accept this in either case. But we can mitigate by redacting PII in prompts if needed or using prompt guidelines to not reveal sensitive info.

In summary, Setup A clearly wins on data sovereignty. If there are strict privacy requirements (e.g. courts not wanting data on foreign servers), Setup B might even be a non-starter. Setup A could even be deployed in a completely air-gapped environment if needed (Claude could be swapped with a local LLM if absolutely required in the future). Qdrant is open-source, so no calling home.

Vendor Lock-in and Flexibility: Setup B ties us to specific vendors (Qdrant Cloud, Cohere). If they change pricing or terms, switching would involve migrating a lot of data (vectors) out. Setup A gives more freedom: we could experiment with different embedding models easily, or even swap Qdrant for an alternative (Milvus, etc.) since we manage it. There’s also an offline capability: with Setup A, the system could run entirely offline (except Claude). This might be important for disaster recovery or if the internet is down – lawyers could still search the local database and perhaps use a smaller local LLM (with lower quality). Setup B is fully dependent on internet connectivity.

DevOps Skill Requirements: Setup A requires in-house expertise to manage a search infrastructure – but given our team is building an AI legal search, we likely have that or can acquire it. It’s a one-time setup plus ongoing maintenance. Qdrant is Dockerized, and many have run it successfully in production. Monitoring GPU usage, optimizing index parameters, etc., will require some learning. Setup B offloads those concerns but instead one has to integrate multiple APIs reliably (and handle authentication, rate limits). It also introduces a need for careful cost monitoring – we’d have to watch usage to avoid surprise bills (especially with Claude and Cohere usage-based pricing). There have been incidents of misconfigured loops leading to large API charges – so operationally, cost governance is an aspect with Setup B. In Setup A, costs are fixed, so monitoring is more about performance than cost.

Compliance (Regulatory): If handling any personal data or sensitive case details, Setup A helps ensure compliance with data protection laws by keeping data local. If any of the case data involves personal data, sending it to an AI API might require explicit consent or other legal basis under GDPR or KVKK (Turkish data protection law). Using local infrastructure avoids those questions, aside from the final LLM query to Claude. We might consider using Claude’s prompt filtering or only sending the minimum necessary info to the LLM to mitigate exposure.

In conclusion, Setup A demands more hands-on management but grants full control and privacy, whereas Setup B offers convenience at the expense of data control and with a reliance on vendors. Reliability can be achieved in both (with effort on-premise or with payments in cloud). For a legal tech product where trust and confidentiality are paramount, the operational independence of Setup A (or hybrid) is a strong advantage.

5. Feasibility of Hybrid Approaches

Mixing and matching components from both setups can often yield an ideal balance of quality and cost. We evaluate a few hybrid configurations:

Hybrid 1: Local Vector DB + Cloud Embeddings/Rerank – Keep Qdrant self-hosted, but use Cohere’s hosted models for creating embeddings (offloading that ML task) and possibly for reranking. This would mean document vectors are stored locally (good for privacy), but whenever a new doc comes in or a query is made, we call Cohere’s API to embed it. This hybrid could be useful if we absolutely needed the extra accuracy of Cohere’s model without maintaining a GPU full-time. Pros: Reduces the need for a high-end GPU on-prem (we’d only need CPU for Qdrant). Still avoids storing raw text in cloud storage (only short API calls). Cons: Embedding each query externally adds latency (~100ms per query) and minor cost (few cents per day). More importantly, if we considered Cohere’s rerank API in this setup: we’d still face the huge costs – so we likely wouldn’t use cloud rerank except perhaps for occasional very difficult queries. We judge that cloud rerank is not viable at scale, so this hybrid would likely use local reranker. Thus Hybrid 1 effectively becomes local Qdrant + local rerank + Cohere embeddings. That is actually quite reasonable: the Cohere embed API at $0.10 per 1M tokens is cheap enough that we could embed all 9M docs with it initially
agentset.ai
, get high-quality vectors, store them in Qdrant locally, and then for queries either use Cohere API or even embed queries locally (since query text is so short, difference will be negligible). Using Cohere’s embeddings for documents might boost our recall a bit vs an open model, but once those embeddings are stored, querying them doesn’t incur cost. This one-time cost (~$450 as earlier computed) is within budget. So an optimal hybrid could be: Cohere for document embedding ingestion, then self-hosted Qdrant + local rerank + Claude. After initial indexing, we could even fine-tune a local embedding model on a subset of Cohere’s outputs to approximate it, reducing dependence on the API over time.

Hybrid 2: Cloud Vector DB + Local Models – The inverse: Use Qdrant Cloud to host vectors, but generate embeddings and do rerank locally. For example, we run our own embedding model on-prem (or on an EC2 GPU we control) to encode queries and docs, then store in Qdrant Cloud. We also run a local cross-encoder for rerank (perhaps we fetch top-50 IDs from Qdrant Cloud, then retrieve those docs from our store and rerank locally). Pros: Offloads the stateful vector index to a managed service – easier scaling and no risk of data loss (they manage backups). Also reduces our server requirements (maybe no need for huge RAM or fast disk locally). Cons: Still sends a lot of data to cloud: all vector data (we’d upload 9M * 384-d vectors to Qdrant Cloud – that’s ~9M * 384 * 4 bytes ≈ 13.8GB, which is fine, but updating them means network overhead). Also, Qdrant Cloud fees become a significant part of budget (~$500+/mo as seen). Another downside is the network latency for each vector search: our app would call Qdrant Cloud (say 50ms + 20ms network), then fetch maybe 50 doc IDs, then we’d have to fetch those documents either from some store. If documents are stored locally, we have an extra step to map ID->doc. If they were stored as payload in Qdrant Cloud, then we’re retrieving text over network – which could slow things down. Local Qdrant avoids that round-trip. This hybrid somewhat gives the worst of both worlds cost-wise: we pay cloud fees and we maintain the ML models ourselves. It might be justified if we could not host a large database on-prem for some reason. But given we can, this seems less attractive.

Hybrid 3: Cloud for LLM, Everything Else Local – This is basically Setup A (local Qdrant, local embed, local rerank) but still using Claude API for final generation. This is actually the default in Setup A. It’s worth noting this is already a hybrid since the LLM is cloud-based. We consider if any parts of LLM could be local: at present, Claude 2 (100k context) has no comparable open model that can run on a single server with equal quality. So we stick with Claude for answers. We can, however, minimize tokens sent (e.g. by summarizing retrieved docs or using shorter context windows) to keep costs and data exposure low. If Anthropic offered an on-prem deployment (they do for some enterprise with huge fees), that could be a future option for full self-host.

Hybrid 4: Use Multiple Embedding Models (“tiered indexing”) – The question hints at 12–90M vectors (tiered), suggesting maybe using different indices for different granularities. A hybrid idea is to use a cheaper method as a first pass and a costly one as second pass. For example, maintain a smaller high-precision index of curated important vectors (maybe using Cohere 1024-d for summaries of cases) in Qdrant Cloud, and a larger full corpus index with local embeddings. A query could first search the small high-quality index; if it finds confident hits, use those. If not, fall back to the big local index. This is complex, but could save cost by only querying cloud when necessary. However, since Qdrant’s cost is mainly storage, having two indices might double cost, and it adds complexity in keeping them in sync. Instead, a simpler tiered approach: maybe first use BM25 keyword search (which could be done with an open-source search engine like Elasticsearch locally) to narrow candidate set, then embed those candidates for vector search. This could reduce vector DB load and size. But given we can handle full 9M in vector form, this might not be needed.

Optimal Hybrid Recommendation: The most bang-for-buck hybrid appears to be: Local Qdrant + Local Reranker + Claude, with initial help from Cohere for embeddings. Concretely:

Use Cohere’s multilingual embedding API once to embed the 9M documents (for best quality vectors). Store these vectors in a self-hosted Qdrant. Thereafter, all retrieval is local and fast. If budget is too tight for that one-time cost, alternatively use an open model like BGE – you might lose a small amount of recall, but avoid spending ~$450 upfront.

For queries, use either a local embedding model (since queries are short and simple, even an open model will likely do fine in embedding them – or just use the same Cohere model if we don’t mind a $0.0001 cost per query).

Always use the local cross-encoder for reranking the top results. This ensures maximum relevance without incurring external API calls. We expect the local cross-encoder to handle Turkish legal text well (if not, we could fine-tune it on a few hundred Q&A pairs from Turkish case law to improve, which is feasible on our GPU).

Continue using Claude API for final answer generation, but employ prompt caching and careful prompt design to minimize tokens. Possibly use Claude’s 200k context to our advantage by stuffing multiple retrieved docs into one call if needed (Claude 4.5 supports 200k tokens at same price up to 200k
claude.com
claude.com
, so we could actually send a large chunk of a document for summarization in one go if a lawyer needs a summary, etc., without extra cost per token beyond 200k).

This hybrid essentially achieves the quality of Setup B (since we leverage the same embedding model) and the low runtime cost of Setup A after initial setup. It stays well under $500/mo: the only recurring costs are Claude (~$200-300) and perhaps some minor Cohere usage for new documents added each month (embedding say a few thousand new cases = pennies).

Another possible hybrid tweak: If some queries truly require the absolute best reranking (maybe in edge cases where the local reranker might miss subtle context), we could selectively call Cohere’s rerank for those. For example, if a query is very important and the local pipeline’s top result confidence is low, we do an API call with top-10 to Cohere Rerank for a second opinion. This could be done for maybe <5% of queries. At $6 per query for 10 docs, 5% of 30k = 1500 queries → ~$9k, still too high. Even 1% of queries (300 queries) would cost ~$1800, beyond our monthly budget. So this isn’t really viable unless it’s near zero. Thus, we skip Cohere rerank entirely in the steady state.

Hybrid Implementation Priorities: We would start with Setup A components and add cloud pieces only where needed:

Deploy local Qdrant and load it with document vectors (we can initially use a smaller embedding model to start development).

Integrate Claude API for answering, and the local reranker model for re-ranking. This gives us a fully functioning pipeline self-hosted (embedding → search → rerank → answer).

Evaluate quality on internal tests. If we find that recall@10 or nDCG is slightly below desired, consider using Cohere’s embed model to re-embed documents and compare results. If it significantly boosts retrieval (e.g. captures certain semantic nuances better), use it for the production index.

Keep all sensitive data local. Ensure that only minimal necessary info goes to Claude (perhaps anonymize names in the prompt if needed, since lawyers mostly care about the legal reasoning).

Set up monitoring on the local system to detect any slowdowns (e.g. if vector search is taking >200ms or GPU memory is maxed out).

Continuously monitor answer quality. If user feedback indicates missing relevant cases occasionally, try increasing the number of results reranked (we can afford to rerank 100 locally if needed, whereas that would be impossible with a paid API).

In summary, a hybrid approach combines local control with strategic use of cloud AI services. It aligns with the budget and maintains high quality. Data stays largely local (only small queries and prompts go out, which is much better from a compliance standpoint than pushing the whole corpus out). This approach is essentially “Setup A with optional cloud assist,” which we believe is the best path forward.

6. Risk Assessment & Recommendations

Risks in Setup A (Local): The primary risks are technical: hardware failure, system maintenance burden, and ensuring the open-source components perform as expected on Turkish legal text. Mitigation: invest in good hardware with support/warranty, use redundant storage and regular backups, and allocate developer time for maintenance. Also, thoroughly evaluate the chosen local models (e.g. make sure the multilingual embedding doesn’t have a blind spot for formal Turkish legal language; if it does, consider fine-tuning or choose a model known to handle it). There’s also the risk of team expertise – running a search system is new for some teams. However, since cost is a concern, it’s worth building that in-house knowledge. Another risk: lack of SLA – if the system goes down during a critical time, our team must fix it; with cloud, we could escalate to vendor support. But given our user base size, internal handling is feasible.

Risks in Setup B (Cloud): Cost overrun is a huge risk – it’s easy for usage to exceed expectations (e.g. if queries ramp up faster, or if prompt sizes grow). We must trust third-party providers for uptime and data handling. Also, any changes in API (model deprecations, pricing changes) are outside our control. There’s vendor lock-in: if Cohere’s quality doesn’t meet expectations, switching to another API (like OpenAI or others) would require re-embedding everything (though we could mitigate by keeping an export of our data). Data leakage is a risk: while unlikely, using cloud APIs means we are exposing ourselves to potential leaks or breaches on the vendor side.

Recommendation Summary: We recommend a hybrid deployment leaning heavily toward self-hosting. Concretely, start with Setup A for core components and optionally incorporate cloud embeddings as a one-time quality boost. This meets the budget (<$500/mo operational), meets quality (>90% of state-of-art), and avoids untenable recurring costs. Quality-wise, focus on optimizing the reranker and possibly augmenting the embedding model with domain data. The difference between a 384-d and 1024-d embedding is small compared to the difference a cross-encoder and good LLM prompt can make
aclanthology.org
python.plainenglish.io
. Thus, invest effort in the retrieval pipeline tuning: e.g. experiment with combining keyword search (BM25) with vector search (“hybrid search”) – Qdrant supports mixing keyword filters, which could improve precision for legal citations. This was mentioned by a user running Qdrant – they heavily use hybrid BM25+vector and faceted filters
reddit.com
reddit.com
, which is very relevant for us (e.g. filter by court chamber, year, etc.). Qdrant’s filtering capabilities on metadata can be leveraged locally without issue
medium.com
.

Implementation Priorities:

Deploy Self-Hosted Qdrant – index a subset of data and ensure search works. Apply INT8 quantization to balance memory vs accuracy.

Select Embedding Model – try an open model (like sentence-transformers/paraphrase-multilingual-MiniLM or BGE-m3) on test queries. If results are weak, plan to use Cohere v3 for embeddings. This can be decided in a pilot phase.

Integrate Cross-Encoder ReRanker – use a model like cross-encoder/ms-marco-MiniLM-L6-v2 (if multilingual) or a custom-trained one. Evaluate improvement in ranking (it should significantly improve relevance
python.plainenglish.io
). If Turkish nuance is lacking, consider fine-tuning on Turkish data (some manually curated relevant vs non-relevant pairs from our corpus).

Claude Integration & Caching – connect to Claude API (Sonnet 4.5) and implement a caching layer for prompts. For example, use Anthropic’s “prompt library” concept: we send the large system prompt once (incurring the write cost) and get an ID to reuse it for subsequent calls (read cost). This can be done using Anthropic’s API if available, or manually cache at our application layer by storing the formatted system prompt and only prepending a short reference instruction. The goal is to cut input tokens dramatically
claude.com
. Also, use the 200k context wisely: we could potentially feed more of the top documents into Claude in one go instead of iterative prompts.

Monitoring & Logging – set up basic monitoring on the server (CPU, GPU, memory) and logging of queries (with proper anonymization) to continuously evaluate system performance and usage patterns.

Load Testing & Failover Plan – run stress tests (simulate 10 QPS bursts) to ensure the system handles peak loads within latency targets. Prepare a plan for failover – e.g. have Qdrant snapshots so we can quickly spin up a new instance on the cloud if our server has an outage (as a temporary search service). This could be as simple as having an AWS EC2 ready with Qdrant Docker image that can restore from a snapshot backup; not fully automated, but a contingency.

By following this plan, we combine the strengths of each approach: the affordability and privacy of local infrastructure with the state-of-the-art capabilities of targeted cloud AI services. This ensures our Turkish legal document search system is both high-performing and sustainable. The executive decision is to avoid a fully-managed solution that would burn budget on usage fees, and instead build up our own RAG stack – a one-time investment that will pay off as our query load grows and our dataset expands.

References: The comparison above cites current research and user reports, for example: embedding dimension impacts
aclanthology.org
, cross-encoder gains on BEIR/MS MARCO
python.plainenglish.io
, Qdrant Cloud pricing experiences
reddit.com
, Cohere pricing (embedding vs rerank)
agentset.ai
llmpricingtable.com
, Claude pricing
claude.com
claude.com
, and Qdrant performance benchmarks
medium.com
medium.com
. These sources support the conclusion that a carefully chosen hybrid can achieve >90% of the quality at a fraction of the cost of an all-cloud stack, which aligns with our project constraints and goals.