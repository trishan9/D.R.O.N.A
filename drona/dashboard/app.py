"""
D.R.O.N.A. Anti-Anchoring Advising Dashboard.

Streamlit web interface for the advising intelligence layer.

Anti-anchoring design (C2 research contribution):
  - Pathways displayed in equal-width COLUMNS, not a ranked list.
    The first column is not visually "better" - equal visual weight for all.
  - "Show N pathways" slider defaults to 3. Showing one would anchor the student.
  - Bias flags appear ABOVE the response, not below - the student sees the
    cognitive context before reading the answer.
  - Citation tier is always shown - Nepal-sourced data is visually distinct.
  - Previous queries shown in a history panel - students can compare responses
    across different phrasings, reducing confirmation bias from a single answer.

Run with:
    streamlit run drona/dashboard/app.py

Optional: set DRONA_OLLAMA_MODEL in .env to switch LLM.
"""

import streamlit as st

from drona.dashboard.components import (
    render_bias_flags,
    render_pathway_columns,
    render_refusal_banner,
    render_session_stats,
)
from drona.dashboard.session_bridge import SessionBridge
from drona.utils.logging import setup_logging
from drona.utils.settings import settings

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DRONA - Academic Advisor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup_logging("WARNING")  # suppress loguru output in the Streamlit UI

# ── Session bridge ─────────────────────────────────────────────────────────────

bridge = SessionBridge(st.session_state)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/robot.svg",
        width=60,
    )
    st.title("DRONA")
    st.caption("Demonstration-learned Robotic Oracle for Nurturing Aspirations")
    st.divider()

    st.markdown("#### Your Profile")
    year = st.selectbox(
        "Year of study", options=[None, 1, 2, 3, 4],
        format_func=lambda x: "Not specified" if x is None else f"Year {x}",
    )
    modules_input = st.text_input(
        "Completed modules (comma-separated)",
        placeholder="e.g. 4001COMP, 4002COMP",
        help="Module codes from your Softwarica transcript.",
    )
    skills_input = st.text_input(
        "Your skills (comma-separated)",
        placeholder="e.g. Python, SQL, React",
    )
    geography = st.radio(
        "Job market preference",
        options=["any", "nepal", "regional", "international"],
        format_func=lambda x: {
            "any": "Open to anywhere",
            "nepal": "Nepal (preferred)",
            "regional": "South Asia",
            "international": "International",
        }[x],
        horizontal=True,
    )
    max_pathways = st.slider(
        "Pathways to show",
        min_value=2, max_value=4, value=3,
        help="Anti-anchoring: always show multiple options. Min 2.",
    )

    bridge.set_profile(
        year=year,
        completed_modules=[m.strip() for m in modules_input.split(",") if m.strip()],
        skills=[s.strip() for s in skills_input.split(",") if s.strip()],
        geography=geography,
    )

    st.divider()
    if bridge.query_count > 0:
        render_session_stats(bridge.stats())
    if st.button("Clear history", use_container_width=True):
        bridge.clear_history()
        st.rerun()

# ── Main content ───────────────────────────────────────────────────────────────

st.markdown("## Career Advising")
st.markdown(
    "Ask about career pathways, required skills, or how your Softwarica modules "
    "prepare you for the Nepali and international job market."
)

# Anti-anchoring notice
with st.expander("About this advisor", expanded=False):
    st.markdown(
        """
        **DRONA** uses a bias-aware advising pipeline designed to counter common
        cognitive biases in career decision-making:

        | Bias | What it is | How DRONA counters it |
        |------|-----------|----------------------|
        | **Anchoring** | Fixating on the first option | Always shows 2-4 pathways in equal columns |
        | **Availability** | Over-weighting vivid examples | Grounds answers in broad market data |
        | **Confirmation** | Seeking validation of beliefs | Presents balanced evidence pro and con |
        | **Loss aversion** | Framing around avoiding negatives | Reframes around positive goals |
        | **Consistency** | Commitment to prior choices | Normalises direction changes |
        | **Dunning-Kruger** | Mis-calibrated self-assessment | Anchors assessment to observable evidence |

        All responses cite Nepali market data first (where available) with international
        context for comparison. Data sources: Nepali job portals, O*NET, Softwarica modules.
        """
    )

# ── Query input ────────────────────────────────────────────────────────────────

with st.form("query_form", clear_on_submit=True):
    query_text = st.text_area(
        "Your question",
        placeholder=(
            "e.g. What career paths are open to a BSc Computing graduate in Kathmandu? "
            "I'm interested in data science but worried about job availability."
        ),
        height=100,
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button(
        "Ask DRONA", type="primary", use_container_width=True
    )

if submitted and query_text.strip():
    with st.spinner("Retrieving and generating response…"):
        response = bridge.submit(query_text.strip(), max_pathways=max_pathways)

    # ── Response display ───────────────────────────────────────────────────────

    st.divider()

    if response.refusal:
        render_refusal_banner(response)
    else:
        # Bias flags FIRST (before the answer - students see context first)
        if response.bias_flags:
            render_bias_flags(response.bias_flags)

        st.markdown(f"#### Summary\n{response.summary}")

        if response.speak_text and response.speak_text != response.summary:
            st.info(f"🤖 *\"{response.speak_text}\"*")

        st.markdown("#### Career Pathways")
        st.caption(
            f"Showing {len(response.pathways)} pathway{'s' if len(response.pathways) != 1 else ''} "
            f"in equal columns - no ranking implied."
        )
        render_pathway_columns(response.pathways)

        if response.generation_time_ms is not None:
            st.caption(f"Generated in {response.generation_time_ms}ms · "
                       f"Model: `{settings.ollama_model}`")

elif submitted and not query_text.strip():
    st.warning("Please enter a question before submitting.")

# ── History panel ──────────────────────────────────────────────────────────────

if bridge.history:
    st.divider()
    with st.expander(
        f"Query history ({bridge.query_count} question{'s' if bridge.query_count != 1 else ''})",
        expanded=False,
    ):
        for entry in reversed(bridge.history):
            st.markdown(f"**Q{entry.query_number}:** {entry.query_text}")
            r = entry.response
            if r.refusal:
                st.error(f"Refusal: {r.refusal_reason}")
            else:
                titles = ", ".join(p.pathway_title for p in r.pathways)
                bias_str = (
                    " · Biases: " + ", ".join(f.bias_type for f in r.bias_flags)
                    if r.bias_flags else ""
                )
                st.caption(f"Pathways: {titles}{bias_str}")
            st.divider()
