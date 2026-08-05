# Domain Validator — PoC

PoC de validador de dominios con IA. Pipeline: concepto → generación LLM → filtro determinístico → evaluación LLM → disponibilidad API → resultados.

## Pipeline

```
concepto
  → LLM genera N candidatos
  → filtro determinístico       ← gratis, descarta ~50%
  → LLM evalúa lo que quedó     ← caro, solo sobrevivientes
  → ResellerClub por TLD        ← llamadas de red
  → array de resultados
```

## Formato de salida

```jsonc
{
  "name": "quilara",
  "flags": [
    { "rule": "digraph-ambiguity", "ok": true },
    { "rule": "bv-ambiguity", "ok": true },
    { "rule": "seseo-ambiguity", "ok": true },
    { "rule": "qui-vs-k", "ok": true },
    { "rule": "foreign-ending", "ok": true }
  ],
  "metrics": {
    "syllables": 3,
    "length": 7,
    "dictable": true,
    "spanish_phonetic": true
  },
  "scores": {
    "evocation":    { "value": 5, "why": "..." },
    "memorability": { "value": 4, "why": "..." },
    "story":        { "value": 5, "why": "..." },
    "collision":    { "value": 4, "why": "..." }
  },
  "total_score": 4.3,
  "availability": {
    "com": "taken",
    "co":  "available",
    "net": "taken",
    "org": "available"
  },
  "verdict": "candidate"
}
```

## Reglas determinísticas (español)

| Regla | Detecta |
|-------|---------|
| `digraph-ambiguity` | `ll`/`y` suenan igual: tres grafías para un sonido |
| `bv-ambiguity` | `b`/`v` suenan igual sin nada que desambigüe |
| `seseo-ambiguity` | `c`+e/i, `s`, `z` suenan igual en Latinoamérica |
| `qui-vs-k` | `qui` es grafía nativa; `k` solo préstamos |
| `foreign-ending` | español no termina en `-rk`, `-ck`, `-th` |
| `syllables` | más de 3 sílabas se dicta peor |

Criterio unificador: se escribe bien al escucharlo una vez, sin deletrear.

## Arquitectura

```
┌─────────────────────────────────────────┐
│  Dokploy                                 │
│  ┌──────────────┐   ┌────────────────┐  │
│  │  Streamlit   │──▶│   OpenClaw     │  │
│  │  (UI + reglas)│  │  (LLM Gateway) │  │
│  │  :8501       │   │  :18789        │  │
│  └──────┬───────┘   └────────────────┘  │
│         │                                │
│         │ HTTP                            │
│         ▼                                │
│  ResellerClub API                        │
│  (disponibilidad)                        │
└─────────────────────────────────────────┘
```

## Stack

| Capa | Tecnología |
|------|------------|
| UI | Streamlit |
| LLM | OpenClaw (endpoint OpenAI-compatible) |
| Disponibilidad | ResellerClub API |
| Orquestación | Dokploy + docker-compose |
| Lenguaje | Python |

## Estructura del repo

```
domain-validator/
├── app/
│   ├── main.py              # Streamlit UI
│   ├── pipeline.py          # Pipeline: generar, filtrar, evaluar, disponibilidad
│   ├── rules.py             # Reglas determinísticas
│   ├── prompts.py           # Prompts del sistema (generación y evaluación)
│   └── requirements.txt     # Dependencias Python
├── openclaw/
│   └── config.yaml          # Config de OpenClaw (modelo, providers)
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Comunicación Streamlit ↔ OpenClaw

OpenAI-compatible endpoint. Streamlit usa `openai` SDK apuntando a `http://openclaw:18789/v1`.

Structured output vía `response_format: { type: "json_schema", ... }` — el modelo devuelve JSON validado contra el schema definido.

## Decisiones de diseño

| # | Decisión | Respuesta |
|---|----------|-----------|
| 1 | Propósito | PoC, validar idea, tirar-para-aprender |
| 2 | Entrada | Concepto (LLM genera candidatos) |
| 3 | Candidatos iniciales | 10 generados, ~5 sobreviven filtro |
| 4 | Score total | Promedio ponderado + scores individuales con `why` |
| 5 | Reglas | Solo español (6 reglas determinísticas, regex) |
| 6 | Conceptos de prueba | 3: quilara + 2 de sectores distintos |
| 7 | TLDs consultados | .com, .co, .net, .org |
| 8 | Prompts | Embebidos en código (PoC) |
| 9 | Colisión de marcas | Fuera de alcance del PoC |
| 10 | LLM manager | OpenClaw (endpoint OpenAI-compatible) |
| 11 | UI | Streamlit |
| 12 | Disponibilidad | ResellerClub API |
| 13 | Repositorio | Monorepo, docker-compose |
| 14 | Orquestación | Dokploy |
| 15 | Idioma UI/prompts | Cualquiera (LLM lo maneja); reglas solo español |

## Fuera de alcance del PoC

- Registrar dominios (solo consulta)
- Marcas registradas reales (score `collision` no confiable, sin búsqueda web)
- Persistencia / base de datos
- Modo "lista de nombres" (solo modo concepto)
- Soporte multi-idioma para reglas determinísticas

## Lo que hace creíble el demo

Cada descarte tiene nombre y motivo, no opinión. Ejemplo:

> `quiyara` — descartado por `digraph-ambiguity`: en español /ʝ/ se escribe `ll` o `y`, quien lo escucha no sabe cuál escribir.

## Instalación

```bash
git clone <repo-url>
cd domain-validator
docker compose up
```

Streamlit en `http://localhost:8501`.
