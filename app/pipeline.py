import json
import os
from dataclasses import dataclass, field

import requests
from openai import OpenAI

from prompts import (
    EVALUATION_PROMPT,
    GENERATION_PROMPT,
)
from rules import RULES, apply_rules, passes_filter

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


import re


def _parse_json(content: str) -> dict:
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


def _extract_candidates(content: str) -> list[dict]:
    names = re.findall(r'"name"\s*:\s*"([^"]+)"', content)
    rationales = re.findall(r'"rationale"\s*:\s*"([^"]+)"', content)
    return [{"name": n, "rationale": r} for n, r in zip(names, rationales)]


def _build_client() -> OpenAI:
    base_url = os.getenv("OPENCLAW_URL", "http://localhost:18789/v1")
    api_key = os.getenv("OPENCLAW_API_KEY", "sk-demo")
    return OpenAI(base_url=base_url, api_key=api_key)


def generate_candidates(concept: str, n: int = 10, client: OpenAI | None = None) -> list[dict]:
    if client is None:
        client = _build_client()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    prompt = GENERATION_PROMPT.format(n=n, concept=concept)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=2000,
    )
    content = response.choices[0].message.content
    try:
        data = _parse_json(content)
        return data.get("candidates", [])
    except (ValueError, json.JSONDecodeError):
        print(f"JSON parse failed, using regex fallback")
        return _extract_candidates(content)


def evaluate_candidate(name: str, concept: str, client: OpenAI | None = None) -> dict:
    if client is None:
        client = _build_client()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    prompt = EVALUATION_PROMPT.format(name=name, concept=concept)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Evalúa: {name}"},
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    content = response.choices[0].message.content
    return _parse_json(content)


def _total_score(scores: dict) -> float:
    weights = {"evocation": 0.35, "memorability": 0.30, "story": 0.20, "collision": 0.15}
    total = sum(scores[k]["value"] * weights[k] for k in weights)
    return round(total, 1)


def check_availability(name: str) -> dict[str, str]:
    api_url = os.getenv("RESELLERCLUB_URL", "https://test.httpapi.com")
    api_key = os.getenv("RESELLERCLUB_API_KEY", "")
    if not api_key:
        return {tld.lstrip("."): "unknown" for tld in TLDS}

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
            if isinstance(status, dict):
                result[tld_key] = status.get("status", "unknown").lower()
            else:
                result[tld_key] = str(status).lower()
        return result
    except Exception:
        return {tld.lstrip("."): "error" for tld in TLDS}


def run_pipeline(
    concept: str,
    n_candidates: int = 10,
    client: OpenAI | None = None,
    progress_callback=None,
) -> list[CandidateResult]:
    if client is None:
        client = _build_client()

    # Phase 1: Generate candidates
    if progress_callback:
        progress_callback("generating")
    raw = generate_candidates(concept, n=n_candidates, client=client)

    # Phase 2: Apply deterministic rules
    if progress_callback:
        progress_callback("filtering", len(raw))
    survivors = []
    for item in raw:
        name = item["name"].lower().strip()
        results, metrics = apply_rules(name)
        if passes_filter(results):
            survivors.append((name, item.get("rationale", ""), results, metrics))

    # Phase 3: LLM evaluation
    if progress_callback:
        progress_callback("evaluating", len(survivors))
    candidates: list[CandidateResult] = []
    for name, rationale, flags, metrics in survivors:
        try:
            scores = evaluate_candidate(name, concept, client=client)
            total = _total_score(scores)
        except Exception as e:
            candidates.append(CandidateResult(
                name=name, rationale=rationale,
                flags=[{"rule": r.rule, "ok": r.ok, "detail": r.detail} for r in flags],
                metrics=metrics,
                verdict="error", error=str(e),
            ))
            continue

        # Phase 4: Availability
        availability = check_availability(name)

        verdict = "candidate"
        if all(v in ("taken", "unavailable") for v in availability.values()):
            verdict = "unavailable"
        elif total < 3.0:
            verdict = "weak"

        candidates.append(CandidateResult(
            name=name,
            flags=[{"rule": r.rule, "ok": r.ok} for r in flags],
            metrics=metrics,
            scores={
                "evocation": scores.get("evocation", {}),
                "memorability": scores.get("memorability", {}),
                "story": scores.get("story", {}),
                "collision": scores.get("collision", {}),
            },
            total_score=total,
            availability=availability,
            verdict=verdict,
            rationale=rationale,
        ))

    # Sort by total_score desc
    candidates.sort(key=lambda c: c.total_score, reverse=True)
    return candidates
