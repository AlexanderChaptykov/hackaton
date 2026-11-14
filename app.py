"""Web page for the strategy agent.

    uv run streamlit run app.py
"""

import threading
import time

import streamlit as st

import agent
from agent import ROOT, STAGES, list_companies, load_cached

st.set_page_config(page_title="Strategy agent", page_icon="📈", layout="centered")
state = st.session_state
MIN_STAGE_SECONDS = 2  # every stage stays on screen at least this long


def generate(company: str, use_cache: bool = True):
    """Get the strategy behind a progress indicator. Returns it, or None after showing an error.

    A saved strategy is loaded instead of running the agent, but the stages are still shown.
    """
    run = {"stage": 0}

    def work():
        try:
            run["strategy"] = (use_cache and load_cached(company)) or agent.create_strategy(
                company, on_stage=lambda i: run.update(stage=max(run["stage"], i)))
        except Exception as e:  # shown on the page below instead of a stack trace
            run["error"] = e

    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    slot = st.empty()
    shown, since = 0, time.monotonic()
    while shown < len(STAGES) and "error" not in run:
        lines = [("✅" if i < shown else "⏳" if i == shown else "▫️") + f" {i + 1}. {name}"
                 for i, name in enumerate(STAGES)]
        with slot.container():
            st.progress(shown / len(STAGES), text=f"Step {shown + 1} of {len(STAGES)}: {STAGES[shown]}")
            st.markdown("  \n".join(lines))
        # Move on once the agent is past this stage and it has been visible long enough.
        reached = run["stage"] if worker.is_alive() else len(STAGES)
        if reached > shown and time.monotonic() - since >= MIN_STAGE_SECONDS:
            shown, since = shown + 1, time.monotonic()
        else:
            time.sleep(0.1)
    slot.empty()

    if "error" in run:
        st.error(f"Could not create the strategy: {run['error']}")
        return None
    return run["strategy"]


def select_screen() -> None:
    st.title("Strategy agent")
    companies = list_companies()
    if not companies:
        st.warning("No companies found. Add a folder with the five input files under data/.")
        return

    company = st.selectbox("Company", companies)
    # if load_cached(company):
    #     st.caption("A saved strategy exists for this company and will be reused.")

    if st.button("Create strategy", type="primary"):
        strategy = generate(company)
        if strategy is None:
            return
        state.company, state.strategy = company, strategy
        st.rerun()

    st.subheader("Input documents")
    docs = sorted((ROOT / "data" / company).glob("*.md"))
    for tab, doc in zip(st.tabs([d.stem for d in docs]), docs):
        tab.markdown(doc.read_text(encoding="utf-8"))


def strategy_screen() -> None:
    back, regenerate = st.columns([1, 1])
    if back.button("← Choose another company"):
        del state.strategy
        st.rerun()
    if regenerate.button("Regenerate", help="Run the agent again and replace the saved strategy"):
        state.strategy = generate(state.company, use_cache=False) or state.strategy

    st.caption(state.company)
    st.markdown(state.strategy.to_markdown())
    st.download_button("Download as Markdown", state.strategy.to_markdown(),
                       file_name=f"{state.company}-strategy.md", mime="text/markdown")


if "strategy" in state:
    strategy_screen()
else:
    select_screen()
