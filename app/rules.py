import re
from dataclasses import dataclass, field


@dataclass
class RuleResult:
    rule: str
    ok: bool
    detail: str = ""


RULES = [
    "digraph-ambiguity",
    "bv-ambiguity",
    "seseo-ambiguity",
    "qui-vs-k",
    "foreign-ending",
    "syllables",
]


def _syllable_count(name: str) -> int:
    name = name.lower()
    count = 0
    prev_vowel = False
    for ch in name:
        is_vowel = ch in "aeiouáéíóúüy"
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return max(count, 1)


def apply_rules(name: str) -> tuple[list[RuleResult], dict]:
    results: list[RuleResult] = []

    # digraph-ambiguity: ll/y sound the same — having either creates ambiguity
    ok = not bool(re.search(r"ll|y", name.lower()))
    results.append(RuleResult(
        rule="digraph-ambiguity", ok=ok,
        detail="" if ok else "contiene 'll' o 'y' — /ʝ/ tiene dos grafías, quien oye no sabe cuál escribir"
    ))

    # bv-ambiguity: b and v sound the same
    lower = name.lower()
    has_b = "b" in lower
    has_v = "v" in lower
    bv_ok = not (has_b and has_v)
    results.append(RuleResult(
        rule="bv-ambiguity", ok=bv_ok,
        detail="" if bv_ok else "contiene 'b' y 'v' — suenan igual, quien oye no sabe cuál usar"
    ))

    # seseo-ambiguity: ce/ci, s, z sound the same in LatAm — ambiguous only if 2+ coexist
    has_s = "s" in lower
    has_z = "z" in lower
    has_ceci = bool(re.search(r"c[ei]", lower))
    seseo_sources = sum([has_s, has_z, has_ceci])
    seseo_ok = seseo_sources <= 1
    results.append(RuleResult(
        rule="seseo-ambiguity", ok=seseo_ok,
        detail="" if seseo_ok else "contiene múltiples grafías para /s/ (s, z, ce/ci) — quien oye no sabe cuál escribir"
    ))

    # qui-vs-k: 'qui' is native Spanish, 'k' is a loan
    qui_ok = "k" not in lower
    results.append(RuleResult(
        rule="qui-vs-k", ok=qui_ok,
        detail="" if qui_ok else "contiene 'k' — grafía no nativa del español"
    ))

    # foreign-ending: Spanish doesn't end in -rk, -ck, -th, etc.
    foreign_ok = not bool(re.search(r"(rk|ck|th|sh|ph|gh|ng)$", lower))
    results.append(RuleResult(
        rule="foreign-ending", ok=foreign_ok,
        detail="" if foreign_ok else "terminación extranjera (-rk, -ck, -th, -sh, -ph, -gh, -ng)"
    ))

    # syllables: more than 3 is harder to dictate
    n = _syllable_count(name)
    syl_ok = n <= 3
    results.append(RuleResult(
        rule="syllables", ok=syl_ok,
        detail="" if syl_ok else f"{n} sílabas — más de 3 se dicta peor"
    ))

    metrics = {
        "syllables": n,
        "length": len(name),
        "dictable": all(r.ok for r in results[:-1]),
        "spanish_phonetic": all(r.ok for r in results),
    }
    return results, metrics


# Rules that block (hard filter)
BLOCK_RULES = {"qui-vs-k", "foreign-ending", "syllables"}


def passes_filter(results: list[RuleResult]) -> bool:
    return all(r.ok for r in results if r.rule in BLOCK_RULES)
