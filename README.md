# Resell App — Agentic AI Price Prediction

A multi-agent AI system that analyzes product images and finds comparable listings on Kleinanzeigen (a German marketplace) to suggest a reasonable resale price based on market data.

Built with [CrewAI](https://www.crewai.com/) and powered by OpenAI-compatible LLMs.

---

## What It Does

1. **Image Analysis** — Extracts product attributes (name, brand, model, color, condition) from product photos using a vision LLM.
2. **Search Query Generation** — Builds optimized German search queries for Kleinanzeigen.
3. **Market Scraping** — Scrapes Kleinanzeigen for similar listings and collects prices.
4. **Result Evaluation** — Compares scraped listings against the analyzed product and calculates match quality.
5. **Price Calculation** — Reports a suggested resale price with median, min, and max range.

The system runs an iterative refinement loop (up to 3 iterations), improving search queries based on evaluation feedback until sufficient matching listings are found.

---

## Input Requirements

This application requires **product image URLs** as input.

- URLs can be HTTP/HTTPS links (e.g., from Kleinanzeigen CDN or other image hosting)
- Multiple image URLs can be provided for better analysis (up to 4 recommended)
- Images should show the product clearly from different angles

**Configure image URLs in:**
- `src/resell_app/main.py` — Update the `image_urls` list in the `run()` function
- Or pass via trigger payload when using `trigger()`

---

## Project Structure

```
├── pyproject.toml                  # Project config and dependencies
├── requirements.txt                # pip-installable dependencies
├── .env                            # Environment variables (API keys, model config)
├── knowledge/
│   └── user_preference.txt         # User preference context for agents
├── src/resell_app/
│   ├── main.py                     # Entry point and CLI
│   ├── crew.py                     # CrewAI agent and task definitions
│   ├── workflow.py                 # Iterative pipeline orchestrator
│   ├── market_search.py            # Kleinanzeigen scraper
│   ├── price_calculation.py        # Price statistics and calculation
│   ├── config/
│   │   ├── agents.yaml             # Agent role/goal/backstory definitions
│   │   └── tasks.yaml              # Task descriptions and expected outputs
│   └── tools/
│       ├── custom_tool.py          # Custom CrewAI tools
│       ├── file_read_tool.py       # UTF-8 file reader tool
│       ├── metrics_tools.py        # Evaluation metrics tool
│       └── vision_tool.py          # Qwen vision LLM tool for image analysis
├── Kleinanzeigen_Data/             # Scraped marketplace data
├── Output_Folder/                  # Timestamped run results
├── item_price.json                 # Latest price summary (root level)
├── image_analysis.json             # Latest image analysis output
├── search_query.json               # Latest search query
├── query_evaluation.json           # Latest evaluation result
└── listing_data.json               # Latest listing data
```

---

## Agents

| Agent | Role | Defined In |
|-------|------|------------|
| **Image Analyzer** | Extracts product details from photos using Qwen Vision | `config/agents.yaml`, `tools/vision_tool.py` |
| **Search Query Generator** | Creates optimized German search queries for Kleinanzeigen | `config/agents.yaml`, `workflow.py` |
| **Search List Evaluator** | Evaluates scraped listings against image analysis with quantitative metrics | `config/agents.yaml`, `price_calculation.py` |

---

## Quick Start

### Requirements

- Python 3.10–3.13
- An OpenAI-compatible API key and endpoint (configured in `.env`)

### Setup

```powershell
cd "Resell App"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Configure Environment

Create a `.env` file in the project root with:

```
OPENAI_BASE_URL=https://your-api-endpoint
OPENAI_API_KEY=your-api-key
MODEL=your-text-model
Image_MODEL=your-vision-model
```

### Run

```powershell
python -m resell_app.main
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m resell_app.main` | Run the full price analysis pipeline |
| `python -m resell_app.main train <iterations> <filename>` | Train agents with feedback |
| `python -m resell_app.main test <iterations> <llm_model>` | Test crew performance |
| `python -m resell_app.main replay <task_id>` | Replay a previous execution |

---

## Output Files

Each run creates a timestamped folder in `Output_Folder/research_YYYYMMDD_HHMMSS/`:

| File | Contents |
|------|----------|
| `final_result.json` | Full run details and final recommendation |
| `evaluation_*.json` | Per-iteration evaluation details |
| `image_analysis.json` | Parsed image attributes |

Root-level files are updated with the latest run results:
- `item_price.json` — Price summary (name, condition, description, range, median)
- `image_analysis.json` — Image analysis output
- `search_query.json` — Search query used
- `query_evaluation.json` — Evaluation results
- `listing_data.json` — Scraped listing data

---

## Configuration

| What to Change | Where |
|----------------|-------|
| Agent roles and behavior | `src/resell_app/config/agents.yaml` |
| Task descriptions and prompts | `src/resell_app/config/tasks.yaml` |
| Pricing logic | `src/resell_app/price_calculation.py` |
| Scraper behavior | `src/resell_app/market_search.py` |
| LLM model selection | `.env` file |

---

## Known Issues

- The Kleinanzeigen scraper may be rate-limited or blocked; consider adding delays between requests.
- API costs can add up for large runs — monitor your usage.

---

## Author

Developed by Lokeshwar Nareshkumar Jakhar.
