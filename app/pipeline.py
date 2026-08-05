import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests
from openai import OpenAI

from prompts import (
    BATCH_EVALUATION_PROMPT,
    FAST_GENERATION_PROMPT,
    SINGLE_EVALUATION_PROMPT,
)
from rules import apply_rules, passes_filter

TLDS = [".com", ".co", ".net", ".org"]


@dataclass
class CandidateResult:
    name: str
    flags: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    total_score: float = 0.0
    availability: dict = field(default_factory=dict)
    verdict: str = "pending"
    rationale: str = ""
    error: str = ""


def _parse_json(content: str) -> dict:
    if not content:
        raise ValueError("Empty response from LLM")
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except (json.JSONDecodeError, TypeError):
            pass
    raise ValueError(f"No parseable JSON in response: {content[:300]}")


def _build_zen_client() -> OpenAI:
    return OpenAI(
        base_url="https://opencode.ai/zen/v1",
        api_key=os.getenv("OPENCLAW_API_KEY", "sk-demo"),
    )


def _build_go_client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("OPENCLAW_URL", "https://opencode.ai/zen/go/v1"),
        api_key=os.getenv("OPENCLAW_API_KEY", "sk-demo"),
    )


def generate_fast(concept: str, n: int = 15) -> list[str]:
    client = _build_zen_client()
    model = os.getenv("LLM_FAST_MODEL", "deepseek-v4-flash-free")
    prompt = FAST_GENERATION_PROMPT.format(n=n, concept=concept)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
        temperature=0.9,
    )
    content = response.choices[0].message.content or ""
    names = [n.strip().lower() for n in content.split(",") if n.strip() and len(n.strip()) >= 3]
    return names[:n]


def score_stream(candidates: list[CandidateResult], concept: str):
    names = [c.name for c in candidates]
    avail = availability_batch(names)

    client = _build_go_client()
    model = os.getenv("LLM_MODEL", "kimi-k2.6")
    total = len(candidates)

    for i, c in enumerate(candidates):
        prompt = SINGLE_EVALUATION_PROMPT.format(name=c.name, concept=concept)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
        content = response.choices[0].message.content
        if content:
            try:
                data = _parse_json(content)
                if "evocation" in data:
                    c.scores = {
                        "evocation": data.get("evocation", {}),
                        "memorability": data.get("memorability", {}),
                        "story": data.get("story", {}),
                        "collision": data.get("collision", {}),
                    }
                    c.total_score = _total_score(data)
            except (ValueError, json.JSONDecodeError):
                pass
        yield i + 1, total, c.name

    for c in candidates:
        c.availability = avail.get(c.name, {})
        if all(v in ("taken", "unavailable") for v in c.availability.values()):
            c.verdict = "unavailable"
        elif not c.scores:
            c.verdict = "pending"
        elif c.total_score < 3.0:
            c.verdict = "weak"
        else:
            c.verdict = "candidate"
    candidates.sort(key=lambda x: x.total_score, reverse=True)
    yield ("done", candidates)


def _total_score(scores: dict) -> float:
    weights = {"evocation": 0.35, "memorability": 0.30, "story": 0.20, "collision": 0.15}
    total = sum(
        scores[k]["value"] * weights[k]
        for k in weights
        if k in scores and isinstance(scores.get(k), dict) and "value" in scores[k]
    )
    return round(total, 1)


def _check_single(name: str, api_url: str, api_key: str) -> dict[str, str]:
    domain = name.lower()
    tlds_param = "&".join(f"tlds={tld.lstrip('.')}" for tld in TLDS)
    url = (
        f"{api_url}/api/domains/available.json"
        f"?auth-userid=0&api-key={api_key}"
        f"&domain-name={domain}&{tlds_param}"
    )
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        result = {}
        for tld in TLDS:
            tld_key = tld.lstrip(".")
            status = data.get(tld_key, "unknown")
            result[tld_key] = (
                status.get("status", "unknown").lower()
                if isinstance(status, dict)
                else str(status).lower()
            )
        return result
    except Exception:
        return {tld.lstrip("."): "error" for tld in TLDS}


def availability_batch(names: list[str]) -> dict[str, dict[str, str]]:
    api_url = os.getenv("RESELLERCLUB_URL", "")
    api_key = os.getenv("RESELLERCLUB_API_KEY", "")
    if not api_key:
        return {n: {tld.lstrip("."): "unknown" for tld in TLDS} for n in names}
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_check_single, n, api_url, api_key): n for n in names}
        for f in as_completed(futures):
            results[futures[f]] = f.result()
    return results


def enrich_candidates(names: list[str], concept: str) -> list[CandidateResult]:
    candidates: list[CandidateResult] = []
    for name in names:
        rules, metrics = apply_rules(name)
        candidates.append(CandidateResult(
            name=name,
            flags=[{"rule": r.rule, "ok": r.ok} for r in rules],
            metrics=metrics,
        ))
    return candidates


def apply_scores(candidates: list[CandidateResult], concept: str):
    yield from score_stream(candidates, concept)


def run_pipeline(
    concept: str,
    n_candidates: int = 10,
    client: OpenAI | None = None,
    progress_callback=None,
) -> list[CandidateResult]:
    # Phase 1: Fast generation + rules
    if progress_callback:
        progress_callback("generating")
    names = generate_fast(concept, n=n_candidates)

    if progress_callback:
        progress_callback("filtering", len(names))
    candidates = enrich_candidates(names, concept)

    # Phase 2: Scoring + availability
    if progress_callback:
        progress_callback("evaluating", len(candidates))
    return apply_scores(candidates, concept)
