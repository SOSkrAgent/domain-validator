import streamlit as st

from pipeline import run_pipeline, TLDS
from rules import RULES

st.set_page_config(page_title="Domain Validator", page_icon="🔍", layout="wide")
st.title("Domain Validator")
st.caption("PoC — Generación y evaluación de nombres de dominio con IA")

concept = st.text_input(
    "Concepto",
    placeholder="Ej: fintech de microcréditos para pymes",
    value=st.session_state.get("concept", ""),
)
st.session_state["concept"] = concept

col1, col2 = st.columns(2)
with col1:
    n_candidates = st.slider("Candidatos a generar", 5, 20, 10)
with col2:
    st.markdown("")
    st.markdown("**Reglas aplicadas:** " + ", ".join(f"`{r}`" for r in RULES))

if st.button("Ejecutar Pipeline", use_container_width=True, disabled=not concept.strip()):
    progress = st.empty()
    status = st.empty()
    results_container = st.container()

    def on_progress(phase, count=0):
        labels = {
            "generating": f"🧠 Generando {n_candidates} candidatos con LLM...",
            "filtering": f"🔍 Aplicando reglas determinísticas a {count} candidatos...",
            "evaluating": f"📊 Evaluando {count} sobrevivientes con LLM...",
        }
        status.info(labels.get(phase, phase))

    with st.spinner("Ejecutando pipeline..."):
        candidates = run_pipeline(concept, n_candidates=n_candidates, progress_callback=on_progress)

    progress.empty()
    status.empty()

    if not candidates:
        st.warning("Ningún candidato sobrevivió el filtro. Prueba con otro concepto.")
    else:
        st.subheader(f"Resultados — {len(candidates)} candidatos evaluados")

        for i, c in enumerate(candidates):
            with st.expander(
                f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '📌'} "
                f"**{c.name}** — {c.total_score}/5 — {c.verdict}",
                expanded=(i == 0),
            ):
                # Scores row
                cols = st.columns(4)
                score_keys = ["evocation", "memorability", "story", "collision"]
                for col, key in zip(cols, score_keys):
                    s = c.scores.get(key, {})
                    val = s.get("value", "?")
                    col.metric(key.capitalize(), f"{val}/5")

                # Score details
                with st.container():
                    for key in score_keys:
                        s = c.scores.get(key, {})
                        if s.get("why"):
                            st.caption(f"**{key}**: {s['why']}")

                # Rule flags
                st.markdown("**Flags:**")
                flag_cols = st.columns(len(c.flags) if c.flags else 1)
                for col, f in zip(flag_cols, c.flags):
                    icon = "✅" if f["ok"] else "❌"
                    col.markdown(f"{icon} `{f['rule']}`")

                # Availability
                st.markdown("**Disponibilidad:**")
                avail_cols = st.columns(len(TLDS))
                for col, tld in zip(avail_cols, TLDS):
                    tld_key = tld.lstrip(".")
                    status_text = c.availability.get(tld_key, "unknown")
                    icon = "🟢" if status_text == "available" else "🔴" if status_text in ("taken", "unavailable") else "⚪"
                    col.markdown(f"{icon} **{tld}**: {status_text}")

                if c.error:
                    st.error(f"Error: {c.error}")

st.divider()
st.caption("Reglas determinísticas: español • LLM vía OpenClaw • Disponibilidad vía ResellerClub")
