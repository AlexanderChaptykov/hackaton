# Strategy agent

An AI agent that reads what a company already knows about itself (its products, current
strategies and results, competitors, and brand positioning) and writes an updated marketing
strategy, with every decision justified against the brand document and the data.

## Purpose

Writing a marketing strategy by hand means reading several documents, cross-checking results
against competitors and demand, and then checking every idea against the brand rules. That takes
days. This project does the first full draft in about a minute.

The goal is to make strategy creation about 10x faster and to raise its quality:

- **Speed.** One click or one command produces a complete strategy: what to keep, change, stop
  or add, with a plan and a monthly budget for each.
- **Quality.** Each strategy comes with its justification: exact quotes from the brand
  positioning document and the numbers from the data that support it. A reviewer can check the
  reasoning instead of taking it on trust.
- **Consistency.** Every company is analysed the same way, from the same five documents.

The 10x figure is the target, not a measured result. The output is a draft for a marketer to
review, not a final plan.

## How it works

```
data/<company>/*.md  ->  agent  ->  output/<company>/strategy.md
```

One agent (LangChain `create_agent` with an OpenAI model) has two tools:

| Tool | What it does |
|------|--------------|
| `lookup_data` | Returns one data file: company, strategies, products or competitors |
| `search_brand_positioning` | Keyword (BM25) search over `brand-positioning.md`, used to find the brand rules behind each decision |

The agent reads the data, decides on the strategies, looks up the brand rules that apply, and
returns a structured `Strategy` object (see `schema.py`), which is rendered to Markdown.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```
cp .env.example .env      # then put your OpenAI key in .env
uv sync
```

`.env` holds two settings:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra
```

## Usage

### Web page

```
uv run streamlit run app.py
```

1. **Choose a company.** The page lists every company folder under `data/`. You can read its
   input documents in the tabs below.
2. **Press "Create strategy".** A progress indicator shows three stages: document indexing,
   tool calling, generating answer. If the company was processed before, the saved strategy is
   reused.
3. **Read the strategy.** From there you can download it as Markdown, or press "Regenerate" to
   run the agent again.

### Command line

```
uv run agent.py Nordbean
```

Writes `output/Nordbean/strategy.md` and `output/Nordbean/strategy.json`. Add `--model <name>`
to use a different OpenAI model for one run.

## Adding a company

Create a folder under `data/` with these five files. `data/Nordbean` is a worked example with
mock data.

| File | Contents |
|------|----------|
| `company.md` | Name, region, products, how customers find the company, search queries, company weight |
| `strategies.md` | Current strategies with plan, budget and results, and the total budget |
| `products.md` | Description and demand for each product |
| `competitors.md` | Competitors, their weight, products, region and search positions |
| `brand-positioning.md` | Positioning, audiences, pillars, pricing principles, do / do not, priorities |

A folder missing any of these files does not appear in the company list.

## Project layout

| Path | Purpose |
|------|---------|
| `agent.py` | The agent, its two tools, the prompt, and the command line |
| `schema.py` | The `Strategy` output model and its Markdown rendering |
| `app.py` | The Streamlit web page |
| `data/` | Input: one folder per company |
| `output/` | Saved strategies, one folder per company; also the cache for the web page |

## Limitations

- **No automatic checking.** Nothing verifies that quotes are exact or that budgets add up to
  the total. The agent is instructed to do both, and a person should check.
- **Results vary.** Two runs on the same data can give different budget splits.
- **The cache does not notice data changes.** After editing a company's files, press
  "Regenerate" or delete its folder under `output/`.
- **Progress stages are approximate.** "Generating answer" can appear while the agent is still
  making follow-up tool calls, and for a saved strategy the stages are display only.
