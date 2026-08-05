import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests
from openai import OpenAI

from prompts import (
    BATCH_EVALUATION_PROMPT,
    GENERATION_PROMPT,
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
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=8000,
    )
    content = response.choices[0].message.content
    if not content:
        finish = response.choices[0].finish_reason
        raise ValueError(f"LLM returned empty response (finish_reason={finish})")
    try:
        data = _parse_json(content)
        return data.get("candidates", [])
    except (ValueError, json.JSONDecodeError):
        return _extract_candidates(content)


def evaluate_batch(names: list[str], concept: str, client: OpenAI | None = None) -> dict[str, dict]:
    if not names:
        return {}
    if client is None:
        client = _build_client()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    names_str = "\n".join(f"- {n}" for n in names)
    prompt = BATCH_EVALUATION_PROMPT.format(names=names_str, concept=concept)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )
    content = response.choices[0].message.content
    if not content:
        return {n: {} for n in names}
    try:
        data = _parse_json(content)
        return data.get("evaluations", {})
    except (ValueError, json.JSONDecodeError):
        # Fallback: extract per-name scores via regex
        result = {}
        for name in names:
            pattern = rf'"{re.escape(name)}"\s*:\s*\{{[^}}]+\}}'
            match = re.search(pattern, content)
            if match:
                try:
                    result[name] = json.loads(match.group().split(":", 1)[1].strip())
                except (json.JSONDecodeError, TypeError):
                    result[name] = {}
            else:
                result[name] = {}
        return result


def _total_score(scores: dict) -> float:
    weights = {"evocation": 0.35, "memorability": 0.30, "story": 0.20, "collision": 0.15}
    total = sum(scores[k]["value"] * weights[k] for k in weights if k in scores and isinstance(scores[k], dict) and "value" in scores[k])
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
            if isinstance(status, dict):
                result[tld_key] = status.get("status", "unknown").lower()
            else:
                result[tld_key] = str(status).lower()
        return result
    except Exception:
        return {tld.lstrip("."): "error" for tld in TLDS}


def check_availability_batch(names: list[str]) -> dict[str, dict[str, str]]:
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


def run_pipeline(
    concept: str,
    n_candidates: int = 10,
    client: OpenAI | None = None,
    progress_callback=None,
) -> list[CandidateResult]:
    if client is None:
        client = _build_client()

    if progress_callback:
        progress_callback("generating")
    raw = generate_candidates(concept, n=n_candidates, client=client)

    if progress_callback:
        progress_callback("filtering", len(raw))
    survivors = []
    for item in raw:
        name = item["name"].lower().strip()
        results, metrics = apply_rules(name)
        if passes_filter(results):
            survivors.append((name, item.get("rationale", ""), results, metrics))

    if not survivors:
        return []

    # Batch evaluation — 1 LLM call for all survivors
    if progress_callback:
        progress_callback("evaluating", len(survivors))
    names = [s[0] for s in survivors]
    try:
        all_scores = evaluate_batch(names, concept, client=client)
    except Exception as e:
        return [CandidateResult(name=s[0], rationale=s[1],
            flags=[{"rule": r.rule, "ok": r.ok, "detail": r.detail} for r in s[2]],
            metrics=s[3], verdict="error", error=str(e)) for s in survivors]

    # Parallel availability checks
    if progress_callback:
        progress_callback("availability", len(survivors))
    all_avail = check_availability_batch(names)

    candidates: list[CandidateResult] = []
    for name, rationale, flags, metrics in survivors:
        scores = all_scores.get(name, {})
        total = _total_score(scores) if scores else 0.0
        availability = all_avail.get(name, {})

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

    candidates.sort(key=lambda c: c.total_score, reverse=True)
    return candidates
