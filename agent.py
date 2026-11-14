"""Strategy agent: one agent, two tools, structured output.

    uv run agent.py Nordbean          # writes output/Nordbean/strategy.{json,md}
    uv run streamlit run app.py       # the same thing with a web page

A company is a folder under data/ holding company.md, strategies.md, products.md,
competitors.md and brand-positioning.md.

Reads OPENAI_API_KEY and OPENAI_MODEL from a .env file (see .env.example).
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from rank_bm25 import BM25Okapi

from schema import Strategy

ROOT = Path(__file__).parent
STAGES = ["Document indexing", "Tool calling", "Generating answer"]
DATA_FILES = ["company", "strategies", "products", "competitors"]
BRAND_FILE = "brand-positioning.md"
BM25_K = 5
DEFAULT_MODEL = "gpt-5"

SYSTEM_PROMPT = """\
You are a marketing strategist. Replace the company's current product strategies with an updated \
set for the next planning period.

Work in this order:
1. Read the data with lookup_data: strategies, company, products, competitors.
2. Decide what to keep, change, stop or add. Account for every current strategy. Move budget \
toward what the results and demand support. Never exceed the total monthly budget.
3. Before settling each strategy, call search_brand_positioning to find the brand rules that \
apply to it: pricing, audiences, what the brand does and does not do, strategic priorities. \
A plan step that conflicts with the brand document is not allowed.

How to fill the answer:
- title: a name for the whole updated strategy, including the planning period.
- summary: two or three sentences on what changes and why, ending with the budget split and total.
- body: one item per product strategy, most important first. Include stopped strategies too.

Each body item has two fields, both written in Markdown.

text is the strategy itself, in this layout:
  ### <strategy name>
  | Product | Action | Replaces | Budget / month |
  one table row: product IDs, keep / change / stop / new, the current strategy ID or "-", euros
  **Plan** as a numbered list. Each step names the channel, query, offer and region, so someone \
could start on Monday.
  **Expected result**: the metric this should move and in which direction.

justification explains why, as a bullet list, and never repeats the plan:
  - At least one brand bullet: the section of the brand document, a quote copied exactly from a \
search result, then how it applies.
  - At least one data bullet: the file name, a number or line quoted exactly from it, then what \
it shows.

Do not invent numbers or quotes.
"""


def tokenize(text: str) -> list:
    """Lowercase words with a trailing plural 's' dropped, so 'discount' matches 'discounts'."""
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"\w+", text.lower())]


def load_brand_chunks(data_dir: Path) -> list:
    """One chunk per table row, bullet or paragraph, labelled with its section."""
    chunks, section, header = [], "", None
    for line in (data_dir / BRAND_FILE).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            section, header = line[3:], None
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if header is None:
                header = cells
            elif not set(line) <= set("|-: "):  # skip the |---|---| separator row
                chunks.append((section, " | ".join(f"{h}: {c}" for h, c in zip(header, cells))))
        elif line and section and not line.startswith(("#", ">")):
            header = None
            chunks.append((section, re.sub(r"^(\d+\.|-)\s*", "", line)))
    return chunks


def build_agent(model: str, data_dir: Path):
    """Agent with BM25 search over the brand positioning chunks and a data file lookup."""
    chunks = load_brand_chunks(data_dir)
    bm25 = BM25Okapi([tokenize(f"{section} {text}") for section, text in chunks])

    @tool
    def search_brand_positioning(query: str) -> str:
        """Keyword search over the brand positioning document. Input: a short query."""
        scores = bm25.get_scores(tokenize(query))
        top = sorted(range(len(chunks)), key=lambda i: -scores[i])[:BM25_K]
        hits = [f"[{BRAND_FILE} > {chunks[i][0]}]\n{chunks[i][1]}" for i in top if scores[i] > 0]
        return "\n\n".join(hits) or "No matches. Try other keywords."

    @tool
    def lookup_data(topic: Literal["company", "strategies", "products", "competitors"]) -> str:
        """Return one data file: the company profile, current strategies and their results,
        product demand analysis, or competitor analysis."""
        return (data_dir / f"{topic}.md").read_text(encoding="utf-8")

    return create_agent(
        ChatOpenAI(model=model, use_responses_api=True),
        tools=[search_brand_positioning, lookup_data],
        system_prompt=SYSTEM_PROMPT,
        response_format=Strategy,
    )


def list_companies(data_root: Path = ROOT / "data") -> list:
    """Names of the folders under data/ that hold a full set of input files."""
    needed = [*(f"{t}.md" for t in DATA_FILES), BRAND_FILE]
    return sorted(d.name for d in data_root.iterdir() if d.is_dir() and all((d / f).is_file() for f in needed))


def load_cached(company: str) -> Strategy | None:
    """The saved strategy for this company, or None if it has not been processed yet."""
    path = ROOT / "output" / company / "strategy.json"
    return Strategy.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


class StageReporter(BaseCallbackHandler):
    """Tells on_stage which entry of STAGES the agent has reached."""

    def __init__(self, on_stage):
        self.on_stage, self.tools_used = on_stage, False

    def on_chat_model_start(self, *args, **kwargs):
        # A model call after tools have run is the one that writes the answer;
        # the first call only decides which tools to use.
        self.on_stage(2 if self.tools_used else 1)

    def on_tool_start(self, *args, **kwargs):
        self.tools_used = True
        self.on_stage(1)


def create_strategy(company: str, model: str | None = None, on_stage=lambda i: None) -> Strategy:
    """Run the agent on data/<company> and save the result to output/<company>/.

    on_stage(i) is called as the run reaches STAGES[i]; it may be called from another thread.
    """
    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in the .env file.")
    model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    on_stage(0)
    agent = build_agent(model, ROOT / "data" / company)
    request = f"Today is {datetime.date.today().isoformat()}. Propose the updated strategy."
    result = agent.invoke(
        {"messages": [{"role": "user", "content": request}]},
        config={"callbacks": [StageReporter(on_stage)]},
    )
    strategy: Strategy = result["structured_response"]

    out = ROOT / "output" / company
    out.mkdir(parents=True, exist_ok=True)
    (out / "strategy.md").write_text(strategy.to_markdown(), encoding="utf-8")
    (out / "strategy.json").write_text(strategy.model_dump_json(indent=2), encoding="utf-8")
    return strategy


def main() -> int:
    ap = argparse.ArgumentParser(description="Propose an updated strategy for one company")
    ap.add_argument("company", nargs="?", default="Nordbean", help="folder name under data/ (default: Nordbean)")
    ap.add_argument("--model", help=f"OpenAI model (default: OPENAI_MODEL from .env, else {DEFAULT_MODEL})")
    args = ap.parse_args()

    if args.company not in list_companies():
        sys.exit(f"No complete company folder data/{args.company}. Available: {', '.join(list_companies()) or 'none'}")
    try:
        create_strategy(args.company, args.model)
    except RuntimeError as e:
        sys.exit(str(e))
    print(f"Wrote output/{args.company}/strategy.md and strategy.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
