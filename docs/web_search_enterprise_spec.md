# Enterprise Web Search — Upgrade Spec

**Scope:** `core/web_search.py` and the `willow_web_search` MCP tool  
**Baseline:** single-IP DDG HTML scrape, no proxy, no rate limiting, self-identifying UA  
**Goal:** production-grade search layer suitable for sustained, multi-tenant volume

---

## 1. Provider Abstraction

The current code conflates "search" with "DuckDuckGo HTML scrape." At scale these must separate.

### Interface

```python
class SearchProvider(Protocol):
    name: str
    def search(self, query: str, max_results: int) -> list[SearchResult]: ...
    def health(self) -> ProviderHealth: ...
```

### Implementations (priority order)

| Provider | Notes |
|---|---|
| `BraveSearchProvider` | Documented JSON API, generous free tier, no ToS issues |
| `SerpApiProvider` | Aggregates Google/Bing/DDG; paid but reliable |
| `BingSearchProvider` | Azure Cognitive Search; enterprise SLA available |
| `DDGHtmlProvider` | Current impl; demoted to last-resort fallback only |

### Fallback Chain

`search_web()` iterates providers in configured priority order, advancing on block/failure:

```
primary → secondary → tertiary → DDGHtmlProvider → []
```

Each advance is logged with reason and recorded in metrics. The fallback chain resets per query, not per session.

---

## 2. Request Hardening

### 2a. User-Agent

The current UA (`Willow/2.0; +github.com/...`) is trivially blockable.

Replace with a rotating pool of realistic browser UAs, drawn at request time. Pool is versioned externally (JSON file or env var) so it can be updated without a code deploy. For the HTML fallback provider specifically, UA must match the TLS fingerprint — a Chrome UA sent with a `requests` TLS handshake is a detectable mismatch at scale.

**Recommendation:** migrate the DDG HTML fallback to `httpx` with `httpx-tls-fingerprint` or `curl_cffi` to produce a browser-consistent TLS fingerprint. This is the single highest-leverage hardening change for the HTML scrape path.

### 2b. Header Normalization

Every request should include a plausible, consistent header set:

```
Accept: text/html,application/xhtml+xml,...
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
```

Headers must be consistent with the chosen UA. Mismatched header fingerprints are a reliable bot signal.

### 2c. Request Pacing

Add per-proxy jitter: `base_delay * (1 + random.uniform(-0.2, 0.4))`. Never fire requests in a tight loop from the same IP. The 8-worker ThreadPoolExecutor already provides some natural spread; add a configurable `min_interval_per_proxy` (default 1.5s).

---

## 3. Proxy Management

This is the core scaling problem Ben identified. There are three distinct sub-problems.

### 3a. Pool Architecture

```
ProxyPool
├── ProxyEntry(url, type, geo, score, last_used, failure_count)
├── rotation_policy: round_robin | weighted | geo_aware
└── health_checker: background thread, interval configurable
```

Pool is initialized from config (env var or file), not hardcoded. Supports:
- **Datacenter proxies** — fast, cheap, easiest to block
- **ISP proxies** — harder to block, moderate cost
- **Residential proxies** — hardest to block, highest cost, highest latency variance

For real volume, the pool should contain all three tiers; the rotation policy uses tier as a factor in weighting.

### 3b. Quality Scoring

Each `ProxyEntry` maintains a rolling score (0–1):

```
score = success_rate_last_100 * latency_weight * freshness_weight
```

Requests are preferentially routed to high-score proxies. A proxy that returns 429 or a CAPTCHA page loses score immediately. A proxy with `score < 0.2` is quarantined (no new requests) until health check passes.

### 3c. Retirement & Replenishment

When a proxy's failure count exceeds threshold:
1. Mark retired, remove from active pool
2. Emit `proxy.retired` metric with reason
3. Trigger replenishment callback (hook to provider API or alert to operator)

The pool should maintain a minimum active size (`MIN_POOL_SIZE`, default 5). If active pool drops below minimum, escalate to operator alert.

### 3d. Session Affinity (optional)

Some queries benefit from IP continuity (e.g., paginated results). Add optional `session_id` param to `search_web()`; the pool maps session IDs to proxy entries for the duration of the session (TTL configurable).

---

## 4. Rate Limiting & Circuit Breaker

### 4a. Per-Proxy Rate Limit

Token bucket per proxy entry. Default: 20 req/min. Configurable per tier (datacenter: 30, residential: 10). Requests that would exceed the bucket wait in queue or are routed to a different proxy.

### 4b. Per-Domain Rate Limit

Separate token bucket per target domain (DuckDuckGo, Bing, etc.). This is independent of proxy rotation — even with fresh IPs, hammering one domain endpoint triggers server-side rate limiting.

### 4c. Circuit Breaker

Per-provider circuit breaker with three states:

```
CLOSED  → normal operation
OPEN    → all requests fail fast (no network call)
HALF_OPEN → one probe request; success → CLOSED, failure → OPEN
```

Thresholds (configurable):
- Trip: 5 consecutive failures or 50% failure rate in 60s window
- Half-open delay: 30s (exponential: 30, 60, 120, max 300)

---

## 5. Retry Logic

Current code: one attempt, silent empty return on any error.

### Retry Policy

```
max_attempts: 3
backoff: exponential with jitter
  attempt 1 → 0s
  attempt 2 → 1–2s
  attempt 3 → 2–4s
retry_on: [429, 503, 504, ConnectionError, Timeout]
no_retry_on: [403, 407]  # hard block — retire proxy instead
```

On 403/407, the proxy used for that request is marked failed (score penalty), and the request is retried immediately on a different proxy (counts as attempt 2).

### Retry Budget

Each call to `search_web()` has a total timeout budget (default 15s) that spans all retry attempts. This prevents a worst-case retry spiral from blocking the caller.

---

## 6. Result Quality Pipeline

### 6a. URL Deduplication

Normalize URLs before dedup:
- Strip tracking params (`utm_*`, `fbclid`, `ref`, etc.)
- Canonicalize scheme + trailing slash
- Resolve DDG redirect wrappers (current `_unwrap_ddg` handles this)

### 6b. Relevance Scoring

Add a lightweight relevance pass before returning results:
- Query term overlap in title (strong signal)
- Query term overlap in snippet (moderate signal)
- Domain reputation score from a static tier list (trusted > general > low-quality)

Results are re-ranked by composite score. This is pure Python, no ML required at this tier.

### 6c. Freshness

DDG HTML doesn't surface dates. For the API-backed providers (Brave, Bing), capture and normalize the `date` field. Expose `max_age_days` param on `search_web()` to filter stale results when freshness matters.

### 6d. Low-Quality Domain Filter

Maintain a blocklist of known content farms, ad aggregators, and scraper-of-scrapers domains. Applied as a filter before returning results. Blocklist is a config file, not hardcoded.

---

## 7. HTML Parser Resilience (DDG fallback only)

The current regex approach breaks silently when DDG changes its HTML structure.

### Structural Change Detection

After each successful parse, record a fingerprint of the response structure (presence of key CSS class names). On subsequent requests, compare fingerprint. If structure diverges:
1. Log `ddg.structure_changed` warning
2. Attempt secondary parse strategy (CSS selector via `lxml` or `bs4`)
3. If both fail, emit alert and disable DDG provider until operator reviews

### Parser Redundancy

Implement two parsers:
- `RegexParser` — current approach, fast
- `LxmlParser` — `lxml` + XPath, more robust to minor structural variation

`DDGHtmlProvider` tries `RegexParser` first; falls back to `LxmlParser` on empty result before concluding the request failed.

---

## 8. Caching

### Query Cache

```
key: sha256(normalized_query + trusted_only + provider_chain)
value: list[SearchResult]
TTL: 300s (general), 60s (news/current-events queries)
backend: in-process LRU (default) or Redis (multi-process/multi-instance)
```

Cache is opt-out, not opt-in. `search_web(..., cache=False)` bypasses.

Current-events detection: queries containing today's date, "latest", "just", "breaking" get short TTL automatically.

---

## 9. Observability

### Structured Logging

Every request logs a structured record:

```json
{
  "event": "web_search",
  "query_hash": "...",
  "provider": "brave",
  "proxy_id": "p-042",
  "proxy_tier": "isp",
  "status": 200,
  "result_count": 8,
  "latency_ms": 340,
  "cache_hit": false,
  "attempt": 1
}
```

No raw queries in logs (privacy). Query hash only.

### Metrics (Prometheus-compatible)

```
web_search_requests_total{provider, status, tier}
web_search_latency_seconds{provider, tier}  # histogram
web_search_proxy_score{proxy_id}            # gauge
web_search_cache_hit_total
web_search_provider_fallback_total{from, to, reason}
proxy_pool_active_size
proxy_pool_quarantined_size
```

### Alerting Thresholds

| Condition | Severity |
|---|---|
| Primary provider failure rate > 20% (5m) | warning |
| All providers failing | critical |
| Active proxy pool < MIN_POOL_SIZE | warning |
| DDG structure change detected | warning |
| Circuit breaker tripped | warning |

---

## 10. Configuration

All values currently hardcoded must move to config. No magic numbers in source.

### Environment Variables (minimal viable)

```
WILLOW_SEARCH_PROVIDER_ORDER=brave,bing,ddg_html
WILLOW_SEARCH_PROXY_POOL=http://p1:port,http://p2:port,...
WILLOW_SEARCH_PROXY_ROTATION=weighted
WILLOW_SEARCH_MIN_POOL_SIZE=5
WILLOW_SEARCH_CACHE_BACKEND=lru  # or redis
WILLOW_SEARCH_REDIS_URL=redis://...
BRAVE_API_KEY=...
BING_API_KEY=...
SERPAPI_KEY=...
```

### Config Validation at Boot

On startup, `SearchConfig.validate()` checks:
- At least one provider has valid credentials
- Proxy pool is reachable (ping test)
- Cache backend is accessible

Fail fast with clear error rather than degrading silently at query time.

---

## 11. Implementation Phases

| Phase | Scope | Risk |
|---|---|---|
| 1 | Provider abstraction + Brave as primary | Low — additive only |
| 2 | Proxy pool (no scoring yet, round-robin) | Medium |
| 3 | Circuit breaker + retry logic | Low |
| 4 | Proxy quality scoring + quarantine | Medium |
| 5 | Caching layer | Low |
| 6 | Observability (metrics + structured logs) | Low |
| 7 | Request hardening (TLS fingerprint, UA pool) | Medium |
| 8 | HTML parser resilience + structure detection | Low |

Phases 1–3 get you past the immediate volume cliff. Phases 4–8 are long-term reliability.

---

## What This Does Not Cover

- **Full JavaScript rendering** (Playwright/Puppeteer) — adds significant latency and infrastructure cost; only worth it if JSON API providers are unavailable
- **CAPTCHA solving** — signals the scraping approach is fundamentally wrong at that volume; switch providers instead
- **Search result re-ranking via LLM** — relevant for quality at scale but out of scope here
