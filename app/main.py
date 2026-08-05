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


def _render_one(c, rank, scored):
    prefix = "🥇" if rank == 0 else "🥈" if rank == 1 else "🥉" if rank == 2 else "📌"
    label = f"{prefix} **{c.name}**"
    if scored:
        label += f" — {c.total_score}/5 — {c.verdict}"
    else:
        label += " — ⏳ pendiente"
    with st.expander(label, expanded=(rank == 0 and scored)):
        if scored:
            cols = st.columns(4)
            for col, key in zip(cols, ["evocation", "memorability", "story", "collision"]):
                s = c.scores.get(key, {})
                col.metric(key.capitalize(), f"{s.get('value', '?')}/5")
            for key in ["evocation", "memorability", "story", "collision"]:
                s = c.scores.get(key, {})
                if s.get("why"):
                    st.caption(f"**{key}**: {s['why']}")
        else:
            st.caption("Esperando evaluación...")

        flag_cols = st.columns(len(c.flags) if c.flags else 1)
        for col, f in zip(flag_cols, c.flags):
            icon = "✅" if f["ok"] else "⚠️"
            col.markdown(f"{icon} `{f['rule']}`")

        if scored and c.availability:
            st.markdown("**Disponibilidad:**")
            avail_cols = st.columns(len(TLDS))
            for col, tld in zip(avail_cols, TLDS):
                tld_key = tld.lstrip(".")
                s = c.availability.get(tld_key, "unknown")
                icon = "🟢" if s == "available" else "🔴" if s in ("taken", "unavailable") else "⚪"
                col.markdown(f"{icon} **{tld}**: {s}")

        if c.error:
            st.error(c.error)


def _render_list(candidates, scored_count):
    st.subheader(f"Resultados — {len(candidates)} candidatos")
    for i, c in enumerate(candidates):
        scored = i < scored_count
        _render_one(c, i, scored)


if st.button("Ejecutar Pipeline", use_container_width=True, disabled=not concept.strip()):
    with st.spinner("Generando nombres..."):
        names = generate_fast(concept.strip(), n=n_candidates)

    if not names:
        st.warning("No se pudieron generar nombres. Intenta con otro concepto.")
    else:
        candidates = enrich_candidates(names, concept.strip())

        container = st.empty()
        progress_bar = st.progress(0)
        status = st.empty()

        # Show all names initially, pending
        with container.container():
            _render_list(candidates, 0)

        # Score one by one, re-rendering after each
        for step in apply_scores(candidates, concept.strip()):
            if step[0] == "done":
                scored = step[1]
                break
            i, total, name = step
            progress_bar.progress(i / total)
            status.info(f"Evaluando {i}/{total} — {name} ✓")
            # Sort: scored first (by score desc), then unscored (original order)
            scored_names = {c.name for j, c in enumerate(candidates) if j < i}
            ordered = sorted(candidates, key=lambda c: (-c.total_score if c.name in scored_names else 999))
            with container.container():
                _render_list(ordered, i)

        progress_bar.empty()
        status.empty()
        # Final render
        with container.container():
            _render_list(scored, len(scored))

st.divider()
st.caption("Fast gen: OpenCode Zen · Scoring: OpenCode Go · Disponibilidad: ResellerClub")
