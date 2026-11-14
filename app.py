"""Web page for the strategy agent.

    uv run streamlit run app.py
"""

import streamlit as st

from agent import ROOT, create_strategy, list_companies, load_cached

st.set_page_config(page_title="Strategy agent", page_icon="📈", layout="centered")
state = st.session_state


def select_screen() -> None:
    st.title("Strategy agent")
    companies = list_companies()
    if not companies:
        st.warning("No companies found. Add a folder with the five input files under data/.")
        return

    company = st.selectbox("Company", companies)
    if load_cached(company):
        st.caption("A saved strategy exists for this company and will be shown without a new run.")

    if st.button("Create strategy", type="primary"):
        strategy = load_cached(company)
        if strategy is None:
            with st.spinner(f"Creating a strategy for {company}. This takes about a minute."):
                try:
                    strategy = create_strategy(company)
                except Exception as e:  # show any failure on the page instead of a stack trace
                    st.error(f"Could not create the strategy: {e}")
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
        with st.spinner(f"Creating a new strategy for {state.company}. This takes about a minute."):
            try:
                state.strategy = create_strategy(state.company)
            except Exception as e:
                st.error(f"Could not create the strategy: {e}")

    st.caption(state.company)
    st.markdown(state.strategy.to_markdown())
    st.download_button("Download as Markdown", state.strategy.to_markdown(),
                       file_name=f"{state.company}-strategy.md", mime="text/markdown")


if "strategy" in state:
    strategy_screen()
else:
    select_screen()
