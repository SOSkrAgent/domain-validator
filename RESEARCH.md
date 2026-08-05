# Domain Validator — PoC Research Handoff

## What we built

PoC de validador de dominios con IA. Pipeline: concepto → generación LLM → filtro determinístico → evaluación LLM → disponibilidad API → resultados en UI con re-ranking live.

**Repo**: `github.com/SOSkrAgent/domain-validator`
**Deploy**: Dokploy → `http://domain-validator-rmebbv-f7ea24-66-70-177-137.sslip.io`
**Stack**: Streamlit + Docker + OpenCode Go/Zen + ResellerClub test API

---

## Pipeline actual

```
FASE 1 (15-20s)                     FASE 2 (~50s, chunks de 3)
─────────────────                    ──────────────────────────
big-pickle (Zen free)                kimi-k2.6 (Go)
prompt CSV: "name1,name2,..."        batch eval x3 por chunk
↓                                   ↓
parse CSV → enrich_candidates()     apply_scores() → in-place
(flags determinísticos)             + availability_batch()
↓                                   ↓
render inicial en UI                UI se reordena live
(⏳ en todos los domains)           scores + avail reales
```

### Modelos

| Fase | Modelo | Proveedor | Tiempo por lote | Costo |
|------|--------|-----------|-----------------|-------|
| Fast gen | `big-pickle` | Zen (free) | 15-20s | $0 |
| Scoring batch (3) | `kimi-k2.6` | Go | 15-25s | ~$0.01 |
| Disponibilidad | ResellerClub test | HTTP | 2-5s | $0 |

### Benchmark completo (modelos Go y Zen)

Ver sección `## Model Benchmark` al final de este doc.

---

## Arquitectura de archivos

```
app/
├── main.py          # Streamlit UI — render progresivo, re-ranking live
├── pipeline.py      # generate_fast(), enrich_candidates(), apply_scores()
├── rules.py         # 6 reglas determinísticas (español)
├── prompts.py       # FAST_GENERATION_PROMPT, BATCH_EVALUATION_PROMPT
└── requirements.txt # streamlit<1.60, openai, requests, starlette<1.0

docker-compose.yml   # 1 servicio: streamlit:8501
Dockerfile           # python:3.12-slim, BUILD_DATE arg para cache bust
```

### Endpoints LLM usados

- **Zen** (fast gen): `https://opencode.ai/zen/v1` — OpenAI-compatible, modelos gratuitos
- **Go** (scoring): `https://opencode.ai/zen/go/v1` — OpenAI-compatible, suscripción $10/mes

Ambos usan la misma API key de OpenCode.

---

## Reglas determinísticas (español)

Las ambiguas son solo flags informativos (⚠️). Las estructurales bloquean:

**Flags (informativos):**
- `digraph-ambiguity`: nombre contiene `ll` o `y` — /ʝ/ tiene dos grafías
- `bv-ambiguity`: contiene `b` Y `v` juntas
- `seseo-ambiguity`: 2+ grafías para /s/ (s, z, ce/ci)

**Bloqueantes:**
- `qui-vs-k`: contiene `k` (no nativa)
- `foreign-ending`: termina en -ck, -rk, -th, -sh, -ph, -gh, -ng
- `syllables`: más de 3 sílabas

---

## Bugs conocidos y fixes aplicados

1. **Starlette 1.3.1 incompatible con Streamlit** → Fix: `streamlit<1.60` + `starlette>=0.40,<1.0`

2. **OpenCode Go/Zen models gastan todos los tokens en "reasoning"**  
   - kimi-k2.6, hy3, glm-5.2, deepseek-v4-flash: todos tienen reasoning interno que consume ~80-95% de los completion tokens
   - Fix: `max_tokens=6000-8000` para batch scoring, `max_tokens=2000` para fast gen
   - Los modelos NO retornan JSON en `reasoning_content` — solo en `content`. Si `finish_reason=length`, `content` puede ser null.

3. **JSON malformado del LLM** → Fix: `_parse_json()` con fallback regex + `_extract_candidates()` por regex

4. **Docker compose no resuelve env vars del host en Dokploy** → Fix: hardcodear credenciales en `docker-compose.yml` (PoC, no producción)

5. **Re-ranking no funcionaba** → Fix: actualizar scores `in-place` en el objeto `CandidateResult` durante scoring, no al final

6. **Per-domain scoring individual no viable** → modelos consumen todos los tokens razonando antes de emitir JSON. Fix: chunk scoring (3 por lote).

---

## Dokploy setup

- **Project ID**: `3nIpgeF4m4QGlwpW0cOyo`
- **Compose ID**: `XED4LYx9j_nL9r3VqxNEp`
- **Environment ID**: `PHEAiqtgv6E3UrDXxCUgT`
- **GitHub**: `SOSkrAgent/domain-validator`, branch `main`, autoDeploy on push
- **GitHub App ID**: `rHieHoFMNmT28D-2u-M5j` (instalado en org SOSkr)
- **Server**: auto-assigned (null en config, Dokploy lo pone en cualquier nodo disponible)
- **Domain**: `domain-validator-rmebbv-f7ea24-66-70-177-137.sslip.io`
- **ResellerClub**: test API `https://test.httpapi.com` con IP del server Dokploy whitelisted
  - Auth: `auth-userid=0&api-key=3pQOUq5bgEUESxbTBFYWMk1WhSZJDKMM`
  - Cloudflare bloquea requests desde otras IPs — solo funciona desde el server Dokploy

### Deploy manual (cuando autodeploy no dispara)

```bash
# En Dokploy UI o via MCP:
# 1. Stop compose
# 2. Clean queues
# 3. Update BUILD_DATE env var (para forzar rebuild de Docker)
# 4. Deploy fresh
```

---

## Lo que falta

### Prioridad alta
- [ ] **ResellerClub availability no muestra datos** — env vars hardcodeadas pero falta verificar que el contenedor las lea. Posible que el API retorne formato distinto en test.
- [ ] **Duplicación de reglas/flags en UI** — posible bug de renderizado de Streamlit al reemplazar container con `st.empty()`
- [ ] **Manejo de errores en UI** — si el LLM falla, mostrar mensaje en vez de silencio

### Prioridad media
- [ ] Registrar dominios (ResellerClub production API)
- [ ] Modo "lista de nombres" además de "concepto"
- [ ] Persistencia / cache de resultados
- [ ] Búsqueda real de colisión de marcas (Google/TMsearch)

### Optimización
- [ ] Reducir tiempo de fast gen cambiando a un modelo sin reasoning overhead
- [ ] Paralelizar chunks de scoring (ThreadPoolExecutor para llamadas batch en paralelo)
- [ ] Usar streaming real en vez de polling para el scoring

---

## Model Benchmark (OpenCode Go + Zen free)

Benchmark realizado 2026-08-05. Tarea: generación JSON + evaluación reasoning.

### JSON Generation (domain names)

| Model | Time | Prompt tk | Completion tk | Valid JSON | Est cost/req |
|-------|------|-----------|---------------|------------|-------------|
| **hy3** | 21.3s | 97 | 1384 | ✅ | $0.0008 |
| deepseek-v4-pro | 33.3s | 85 | 1254 | ✅ | $0.0011 |
| kimi-k2.6 | 25.1s | 92 | 3480 | ✅ | $0.0140 |
| kimi-k3 | 41.9s | 169 | 1368 | ✅ | $0.0210 |
| glm-5.2 | 36.3s | 90 | 1265 | ✅ | $0.0057 |
| mimo-v2.5 | 36.8s | 325 | 2900 | ✅ | $0.0009 |
| **big-pickle** (Zen free) | 12.8s | 118 | 1824 | N/A (CSV) | $0 |
| deepseek-v4-flash-free (Zen) | 10.0s | 117 | 715 | N/A | $0 |
| deepseek-v4-flash (Go) | ❌ | - | - | ❌ | Geo-blocked |

### Reasoning / PR Review (henka-style)

| Model | Time | Prompt tk | Completion tk | Valid JSON | Est cost/req |
|-------|------|-----------|---------------|------------|-------------|
| **kimi-k2.6** | 11.2s | 100 | 1840 | ✅ | $0.0075 |
| mimo-v2.5 | 18.7s | 339 | 1613 | ✅ | $0.0005 |
| deepseek-v4-pro | 26.7s | 105 | 1020 | ✅ | $0.0009 |
| hy3 | 34.1s | 108 | 1828 | ✅ | $0.0011 |
| kimi-k3 | 52.5s | 177 | 1637 | ✅ | $0.0251 |
| glm-5.2 | 62.4s | 101 | 626 | ✅ | $0.0029 |

### Recomendaciones

| Use case | Best model | Why |
|----------|-----------|-----|
| Fast gen (CSV names) | big-pickle (Zen free) | 13s, free, consistente |
| Batch scoring (3-6 domains) | kimi-k2.6 (Go) | 11-25s, JSON confiable en batch |
| PR review / triage (henka) | kimi-k2.6 (Go) | 11s, mejor velocidad/calidad |
| Budget option | hy3 (Go) | barato pero lento (reasoning pesado) |
| Avoid | deepseek-v4-flash | Geo-blocked, requiere China opt-in |

---

## Lecciones aprendidas

1. **Modelos Go/Zen tienen reasoning interno masivo**: 80-95% de completion tokens son pensamiento, no output. Necesitan `max_tokens` alto (6000+) para output útil.

2. **JSON Schema (`response_format`) no funciona con modelos Go/Zen**: hay que usar `json_object` o mejor: prompt explícito + regex fallback.

3. **Streamlit no es thread-safe**: no se puede actualizar `st.session_state` desde background threads. El re-ranking se hace en el main thread con re-render vía `st.empty().container()`.

4. **Docker compose en Dokploy no resuelve `${VAR}` del host**: las env vars deben hardcodearse en el compose o pasarse vía Dokploy UI (Environment tab).

5. **Chunk scoring > per-domain scoring**: evaluar 3 dominios a la vez es 3x más rápido que 1 a la vez, porque el reasoning overhead es fijo por llamada.

6. **El prompt mínimo (CSV) es clave para fast gen**: "15 names: a,b,c" usa menos tokens y el modelo no se distrae con formato JSON.

---

## Cómo continuar

1. Clonar el repo
2. Tener una API key de OpenCode (Go + Zen usan la misma)
3. `docker compose up` o deploy en Dokploy
4. Variables de entorno críticas en `docker-compose.yml`:
   - `OPENCLAW_API_KEY` — API key de OpenCode
   - `LLM_FAST_MODEL` — modelo para fast gen (default: big-pickle)
   - `LLM_MODEL` — modelo para scoring (default: kimi-k2.6)
   - `RESELLERCLUB_API_KEY` — token de ResellerClub test
5. Abrir `http://localhost:8501`
