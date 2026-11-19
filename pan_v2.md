# DarGlobal × Wasalt Chatbot — Design & Execution Plan (V2)
**Owner:** Hamdy | **Deadline:** Fri 20 Nov 2026, 5:00 pm Cairo | **Budget:** 25 focused hours | **Cost:** $0  
**Stack:** Python 3.11 · FastAPI · SQLite (FTS5) · plain HTML/CSS/JS (No build step) · Docker · Render (free) · OpenRouter `:free` models  

## 0. Read First — Findings & Constraints
| # | Finding (Verified Nov 2026) | Impact | V2 Decision |
|---|---|---|---|
| 1 | Hugging Face Docker Spaces require a paid PRO plan. | HF is not a free option. | **Render Free** (512MB RAM, 0.1 CPU) is the primary host. |
| 2 | OpenRouter free tier: 50 req/day cap. Reviewer testing can exhaust this. | High risk of demo failure. | **Aggressive caching** of starter questions. Per-IP rate limiting. "Sources-only" fallback when budget is hit. |
| 3 | DarGlobal is protected by Incapsula WAF. | Standard `httpx` gets 403/JS challenges. | Use **Stealth Playwright** for a curated list of ~30 high-value URLs. Fallback to static HTML if WAF allows. |
| 4 | Wasalt listing pages may block aggressive scraping. | Wasting hours on WAF bypass risks the deadline. | **Hybrid approach:** Attempt `__NEXT_DATA__` extraction via `httpx`. If blocked, immediately deploy an **Enhanced Mock Dataset** (50 realistic, varied listings) to guarantee a rich, queryable RAG demo. |
| 5 | Arabic queries fail on English-only BM25. | Poor bonus-point performance. | Implement a **bidirectional gazetteer** (`data/gazetteer.json`) for query expansion (e.g., "الرياض" → "riyadh"). |

---

## 1. Requirements & Scope (V2 Upgrades)
### Functional Requirements
- **FR-1:** Answer natural-language questions about DarGlobal (projects, brands, IR) and Wasalt (listings, cities, auctions).
- **FR-2:** **Every answer cites sources** via elegant, clickable chips (Title, Company, URL, Scrape Date).
- **FR-3:** **Bilingual (EN/AR).** Arabic degrades gracefully via gazetteer expansion; UI supports full RTL.
- **FR-4:** **Zero LLM arithmetic.** Numeric questions (prices, medians) are answered from precomputed SQLite aggregates.
- **FR-5:** Graceful refusal: "I couldn't find this in the collected data" + suggestions.
- **FR-6:** Source filter UI: Both / DarGlobal / Wasalt.
- **FR-7:** Editorial empty state with 6 categorized starter questions.
- **FR-8:** Streaming SSE responses with a refined typing indicator.
- **FR-9:** Visible, quiet disclaimer: *"Informational only, not an offer. Prices are indicative."*
- **FR-10:** "Sources-only" mode activates automatically if the LLM is rate-limited or fails.

### Non-Functional Requirements
- **NFR-1:** Time to first token ≤ 3s (warm), ≤ 8s (cold start wake-up).
- **NFR-2:** Runtime RAM ≤ 400 MB (headroom under Render's 512 MB).
- **NFR-3:** Cost = $0. No credit card required.
- **NFR-4:** Reproducible: `build_index.py` deterministically generates the index from `data/processed/*.jsonl`.
- **NFR-5:** UI matches DarGlobal's luxury aesthetic (dark, editorial, gold/silver accents, refined typography).

---

## 2. Data Acquisition Strategy (V2)
### DarGlobal (Static Marketing Pages)
- **Method:** Stealth Playwright (to bypass Incapsula) targeting a curated sitemap list of ~30 high-value URLs (Projects, Press, Investor, Brands).
- **Extraction:** `selectolax` (Lexbor) to strip scripts/styles and extract clean text.
- **Output:** `data/processed/darglobal_pages.jsonl`

### Wasalt (Dynamic Listings)
- **Method:** Hybrid. 
  1. Try `httpx` + regex for `__NEXT_DATA__` on 50 sitemap URLs.
  2. If >50% fail with 403, **abort and use the Enhanced Mock Dataset**.
- **Enhanced Mock Dataset:** 50 realistic listings across Riyadh, Jeddah, Dammam (mix of sale/rent, villas/apartments, EN/AR text, realistic prices/areas). This guarantees the RAG demo has rich, queryable data without WAF hell.
- **Output:** `data/processed/wasalt_listings.jsonl`

---

## 3. Data Modelling & Preprocessing (V2 Upgrades)
### Canonical Document Schema
- `doc_id`, `source`, `company`, `page_type`, `url`, `title`, `language`, `scraped_at`
- **Content:** `text_display` (clean, for LLM), `text_search` (lowercased, normalized for FTS5).
- **Metadata:** `city`, `country`, `property_type`, `purpose`, `price_value`, `currency`, `area_sqm`, `bedrooms`, `brand_partner`.

### Advanced Chunking (V2)
- **Prose:** Split by headings (`<h1>`, `<h2>`) or every ~800 characters with 10% overlap.
- **Listings:** Keep as a single, dense chunk per listing (title, city, type, price, area, beds, description).
- **Contextual Prefix:** Every chunk gets a prefix: `[Wasalt | listing | Riyadh | SAR | en]` to boost BM25 relevance.

### Precomputed Aggregates
- At build time, compute stats per `(city, property_type, purpose)`: `count`, `avg_price`, `median_price`.
- Store in a dedicated `aggregates` SQLite table. The LLM will *read* these facts, never calculate them.

### Gazetteer (`data/gazetteer.json`)
- Bidirectional mapping for query expansion: `{"الرياض": ["riyadh"], "darglobal": ["دار", "جلوبال"], "villa": ["فيلا"]}`.

---

## 4. Retrieval & RAG Architecture (V2)
**Chosen Design:** Metadata-filtered BM25 (SQLite FTS5) + Precomputed Facts + Gazetteer Query Expansion. *(No heavy dense embeddings to stay under 512MB RAM).*

### Retrieval Flow:
1. **Detect Language & Expand:** Normalize query, expand tokens using `gazetteer.json`.
2. **Filter:** Apply `source` filter (both/darglobal/wasalt).
3. **Fetch Facts:** If query contains numeric keywords ("price", "سعر"), fetch top 3 rows from `aggregates` table.
4. **Fetch Passages:** Query `chunks_fts` with expanded tokens, `ORDER BY rank LIMIT 5`.
5. **Fallback:** If 0 results, run a broad `LIKE '%query%'` fallback. If still 0, return empty context (triggers graceful refusal).

---

## 5. LLM Layer & Quota Management (V2)
- **Model Chain:** `nvidia/nemotron-3.5-super-vl:free` → `nvidia/nemotron-3.5-lightning:free`
- **Quota Protection:**
  - **LRU Cache:** In-memory cache keyed by `(normalized_query + source_filter)`. Pre-seed the 6 starter questions.
  - **Daily Budget:** Hard stop at 40 LLM calls/day.
  - **Sources-Only Fallback:** If budget hit or model returns 429/503, skip LLM entirely. Format top 3 chunks as the answer with a "⚠️ Model unavailable — showing sources" badge.
- **System Prompt:** Strict rules: "Answer ONLY using CONTEXT. NEVER calculate prices. Cite using [1], [2]. Match user language. Add disclaimer."

---

## 6. UI/UX Design Specification (Integrated from `design.md`)
**Direction:** Editorial, restrained, luxury real-estate. Dark-first. No generic chat bubbles.

### Design Tokens (`styles.css`)
- **Colors:** `--bg: #0A0A0B`, `--surface: #141416`, `--text: #F4F1EA` (warm ivory), `--gold: #C6A15B`, `--silver: #C9CCD1`, `--src-wasalt: #5FB8A8`.
- **Typography:** 
  - Display/Headlines: `Cormorant Garamond` (serif, elegant).
  - UI/Body: `Jost` (geometric sans).
  - Arabic: `IBM Plex Sans Arabic`.
- **Shape:** `--r-sm: 2px` (buttons, chips), `--r-md: 4px` (cards). Hairline borders (`1px solid rgba(255,255,255,0.10)`). No heavy shadows.

### Component Layout
1. **Header:** Wordmark "DAR·WASALT ASSISTANT", Segmented Source Control (Both/DarGlobal/Wasalt with colored dots), Language switch (English | العربية).
2. **Hero (Empty State):** Eyebrow "AI RESEARCH ASSISTANT", Serif H1 "Ask about DarGlobal & Wasalt", Stat Strip (Pages Indexed, Wasalt Listings, Data As Of), 2x3 grid of editorial starter cards.
3. **Composer:** Hairline border, auto-grow textarea, circular gold-accented send button. Sticky bottom.
4. **Messages:** User message (subtle bubble). Assistant message (full width, no bubble, 2px gold vertical rule on start edge).
5. **Citation Chips:** Signature element. Row below answer. `[1] Title · Company ↗`. Colored dot (gold=DarGlobal, teal=Wasalt).
6. **RTL Support:** Full logical CSS properties (`margin-inline`, `padding-inline`). `dir="auto"` on messages.

---

## 7. Application Architecture
```text
darglobal-rag/
 ├── app/
 │   ├── main.py               # FastAPI app, static mount, SSE /api/chat, /api/meta
 │   ├── config.py             # Env vars, model chain, limits
 │   ├── retrieval/
 │   │   ├── store.py          # SQLite FTS5, gazetteer expansion, aggregate fetching
 │   │   └── cache.py          # Simple LRU cache for starter questions
 │   ├── llm/
 │   │   ├── client.py         # OpenRouter streaming, model fallback, sources-only logic
 │   │   └── prompts.py        # Strict system prompt
 │   └── ui/                   # Vanilla HTML/CSS/JS (design.md specs)
 │       ├── index.html
 │       ├── styles.css        # Luxury tokens, RTL, responsive
 │       └── app.js            # SSE handler, state, rendering
 ├── ingestion/
 │   ├── scrape_darglobal.py   # Stealth Playwright + selectolax
 │   ├── scrape_wasalt.py      # Hybrid: __NEXT_DATA__ or fallback to mock generator
 │   └── build_index.py        # JSONL → rag.sqlite (FTS5 + aggregates)
 ├── data/
 │   ├── gazetteer.json        # EN/AR alias mapping
 │   └── processed/            # *.jsonl files (committed to git)
 ├── Dockerfile                # Multi-stage: builder (deps) → slim runtime
 ├── .dockerignore             # Exclude data/raw, .env, tests
 └── requirements.txt          # fastapi, uvicorn, httpx, selectolax, playwright, python-dotenv