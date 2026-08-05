import time
import streamlit as st

from pipeline import generate_fast, enrich_candidates, apply_scores, TLDS
from rules import RULES

st.set_page_config(page_title="Domain Validator", page_icon="🔍", layout="wide")
st.title("Domain Validator")
st.caption("PoC — Generación y evaluación de nombres de dominio con IA")

concept = st.text_input(
    "Concepto",
    placeholder="Ej: fintech de microcréditos para pymes",
)
n_candidates = st.slider("Candidatos", 5, 20, 15)
st.caption("Reglas: " + ", ".join(f"`{r}`" for r in RULES))


def _render_candidates(candidates: list, title: str):
    st.subheader(title)
    for i, c in enumerate(candidates):
        prefix = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
        has_scores = any(
            isinstance(c.scores.get(k), dict) and c.scores[k].get("value")
            for k in ["evocation", "memorability", "story", "collision"]
        )
        label = f"{prefix} **{c.name}**"
        if has_scores:
            label += f" — {c.total_score}/5 — {c.verdict}"
        with st.expander(label, expanded=(i == 0)):
            if has_scores:
                cols = st.columns(4)
                for col, key in zip(cols, ["evocation", "memorability", "story", "collision"]):
                    s = c.scores.get(key, {})
                    col.metric(key.capitalize(), f"{s.get('value', '?')}/5")
                for key in ["evocation", "memorability", "story", "collision"]:
                    s = c.scores.get(key, {})
                    if s.get("why"):
                        st.caption(f"**{key}**: {s['why']}")

            flag_cols = st.columns(len(c.flags) if c.flags else 1)
            for col, f in zip(flag_cols, c.flags):
                icon = "✅" if f["ok"] else "⚠️"
                col.markdown(f"{icon} `{f['rule']}`")

            if c.availability:
                st.markdown("**Disponibilidad:**")
                avail_cols = st.columns(len(TLDS))
                for col, tld in zip(avail_cols, TLDS):
                    tld_key = tld.lstrip(".")
                    s = c.availability.get(tld_key, "unknown")
                    icon = "🟢" if s == "available" else "🔴" if s in ("taken", "unavailable") else "⚪"
                    col.markdown(f"{icon} **{tld}**: {s}")

            if c.error:
                st.error(c.error)


if st.button("Ejecutar Pipeline", use_container_width=True, disabled=not concept.strip()):
    # Phase 1: Generate names fast
    with st.spinner(f"Generando {n_candidates} nombres..."):
        names = generate_fast(concept.strip(), n=n_candidates)

    if not names:
        st.warning("No se pudieron generar nombres. Intenta con otro concepto.")
    else:
        # Show names immediately with rules
        candidates = enrich_candidates(names, concept.strip())
        _render_candidates(candidates, f"Resultados — {len(candidates)} candidatos")

        # Phase 2: Score + availability
        status = st.empty()
        status.info("Calculando scores y disponibilidad...")
        scored = apply_scores(candidates, concept.strip())
        status.empty()

        _render_candidates(scored, f"Resultados — {len(scored)} candidatos evaluados")

st.divider()
st.caption("Fast gen: OpenCode Zen · Scoring: OpenCode Go · Disponibilidad: ResellerClub")
