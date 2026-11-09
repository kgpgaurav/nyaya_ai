## Quick start - OpenAI + Docker + Streamlit

Windows PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env  # replace OPENAI_API_KEY with your own key; never commit .env
docker compose up --build -d
docker compose ps
```

Streamlit: http://localhost:8501 ; FastAPI: http://localhost:8000 .
PostgreSQL 16 + pgvector, migrations and corpus seeding are managed automatically by Docker Compose. Stop without losing case data: `docker compose down`.

### Public Streamlit link for the application form

Streamlit Community Cloud runs **only the frontend**; it cannot run this repository's Docker Compose PostgreSQL and FastAPI services. First deploy a Postgres database with pgvector (e.g. Neon) and the FastAPI backend (e.g. Render using `render.yaml`, with `OPENAI_API_KEY` and `DATABASE_URL` set privately). Then create a Streamlit Community Cloud app from this repo, branch `main`, entrypoint `streamlit/app.py`, and set app secrets:

```toml
NYAYA_API_URL = "https://YOUR-DEPLOYED-FASTAPI-SERVICE.onrender.com"
```

You can submit the GitHub repository URL as your prototype even without a public hosted UI, because the application form explicitly accepts repository links. Unedited outputs are at [raw_outputs/mock](raw_outputs/mock/), and contain **scripted mock** evaluation, not measured OpenAI model accuracy.

---

# Nyaya

A conversational legal helper for ordinary people in India. You describe the problem by text or voice, in English, Hindi or Hinglish, and it helps you act on it:

- **Build your case**: turns a messy story into facts, a timeline and a list of proof, each fact tied to your exact words.
- **Explain your options**: plain-language rights and next steps, every legal claim linked to a checked source.
- **Draft a letter**: a demand letter or grievance complaint, written only after you confirm the facts.
- **Practise**: it plays the landlord, seller or employer so you can rehearse, with a coach tip after each reply.
- **Explain a notice**: paste a notice and get what it says, what it asks and its deadline, quoted from the notice itself.

It covers three everyday problems in depth: a **security deposit** a landlord won't return, a **refund** for a faulty or undelivered purchase, and **unpaid salary**. It also explains **notices**. Anything involving police, criminal cases, family law, court dates, threats or fabricated evidence is routed to a lawyer and free legal aid (NALSA 15100), not answered.

## Run it

### With Docker

```bash
cp .env.example .env              # set OPENAI_API_KEY
docker compose up --build         # db + migration/seed + API + Streamlit
```

Open http://localhost:8501 (Streamlit), or http://localhost:8000 (FastAPI).

To run the tests and the scripted evaluation inside Docker:

```bash
docker compose --profile test run --rm tests
```

For a fully local model, start Ollama as well, then set `LLM_PROVIDER=ollama` in `.env` and pull a model:

```bash
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

### Without Docker

You need Python 3.12 and Postgres 16 with the `pgvector` extension.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # set DATABASE_URL and an API key
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

### Deploy (free tiers)

1. Create a free Postgres database on [Neon](https://neon.tech) and copy its direct (not pooled) connection string. Neon supports `pgvector`.
2. On [Render](https://render.com), choose New > Blueprint and point it at this repository. `render.yaml` builds the Docker image and runs migrations and seeding on every start.
3. Set `DATABASE_URL` (the Neon string) and `OPENAI_API_KEY` when Render asks. Usage caps per case and per day are set in `render.yaml`.

Free Render services sleep when idle, so the first request after a while takes about a minute.

### Tests and evaluation

```bash
python -m pytest -q                       # 75 tests; needs a nyaya_test database (TEST_DATABASE_URL)
python scripts/evaluate.py                # 19 scripted scenarios -> raw_outputs/mock/
python scripts/evaluate.py --live         # same scenarios against the configured model -> raw_outputs/live_<provider>_<time>/
```

The scripted run uses a mock model that returns fixed answers from `tests/mock_llm.json`. Those answers deliberately include the mistakes real models make: invented judgments, repealed Acts, made-up deadlines, wrong section numbers and prompt injection. The run proves that the checks catch them. It says nothing about how good a real model is; that is what `--live` is for. Every run writes one JSON file per scenario (inputs, replies, citations, model calls, tokens, latency, pass/fail per check), any drafts as `.txt`, and a `summary.json`.

## Switching models

All model access goes through one adapter (`app/llm.py`), built with LangChain's `init_chat_model`. Change `.env` and restart:

| `LLM_PROVIDER` | Key | Default model |
|---|---|---|
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `openai` | `OPENAI_API_KEY` | `gpt-4.1-mini` |
| `gemini` | `GOOGLE_API_KEY` | `gemini-2.5-flash` |
| `ollama` | none | `qwen2.5:7b-instruct` |
| `mock` | none | scripted answers for tests |

`LLM_MODEL` overrides the default. Voice uses `STT_PROVIDER=openai` (Whisper via OPENAI_API_KEY), `groq`, or `sarvam` (Saaras, better on Indian languages). Retrieval uses Postgres full-text search by default. Set `EMBEDDING_PROVIDER` to `openai`, `gemini` or `ollama` to add pgvector similarity on top.

## How it works

```
ingest -> guard -> ┬ canned reply (danger, lawyer referral, fabrication, out of scope)
                   ├ notice    (explain a notice, quote its deadline)
                   ├ practice  (role-play + coach tip, checked)
                   └ extract -> ┬ draft  (pause for fact confirmation -> letter)
                                └ retrieve -> compose -> verify -> respond
                                                 ^          |
                                                 └─ retry ──┘ (once)
```

- **LangGraph** runs the conversation as a graph. Its Postgres checkpointer keeps each case's state, so a case survives restarts. Drafting uses `interrupt()`: the graph pauses until you confirm or edit the facts.
- **FastAPI** serves the API and a plain HTML/JS front end with a microphone button.
- **Postgres** holds cases, messages, facts, timeline events, drafts, the source corpus (full-text index plus a pgvector column), a log of every model call with tokens and latency, and evaluation runs.

What the model does and what code does:

| Step | Model | Code |
|---|---|---|
| Classify problem, intent and risk | yes | Keyword rules can force danger and fabrication stops even if the model misses them |
| Extract facts | yes | A fact is kept only if its quote is an exact substring of your message and its value is inside the quote. Contradictions are queried, not overwritten |
| Choose sources | no | Cards filtered by problem type, effective date and review date |
| Explain | yes | Every point is re-checked (see below). A failed answer is retried once, then replaced by "I can't confirm that" |
| Draft | facts paragraphs only | Template, headings, demand and the "rules that may apply" list are fixed text. Any paragraph with an amount, period or legal rule not in your facts is dropped |
| Notice deadlines | finds the quote | Kept only if it is word for word in the notice |

## Avoiding invented law

Models confidently invent sections, Acts and judgments. Nyaya never lets model text about law reach the user unchecked:

1. **A small checked corpus** (`app/data/sources.json`, 16 cards). Each card has the citation, a plain summary in English and Hindi, an official or primary link, the date it took effect, the date it was checked, a review-by date and caveats. Expired or not-yet-in-force cards are never shown.
2. **The model can only cite card IDs** it was given.
3. **A verifier in plain code** (`app/verify.py`) drops any point that:
   - cites a card it wasn't given
   - names a section, rule, Act or Code (English or Hindi) that its cited cards don't contain
   - states a time period, rupee amount, phone number or website not found in its cited cards or your own facts
   - mentions any court judgment
   - states a legal rule ("must", "entitled", "illegal") with no source at all
4. **No case law at all.** The corpus has none, so any case name is removed.

Two real examples of why this matters, both caught while building the corpus:
- The Payment of Wages Act, 1936 was repealed when the Code on Wages came into force on 21 November 2025. A model trained before then will cite the old Act.
- Consumer complaints moved from e-Daakhil to e-Jagriti on 1 January 2025.

## What it doesn't do

- It doesn't cover all of Indian law: only the problems above, and only what the 16 cards say. State rent laws, state wage rules and limitation periods for civil suits are flagged as "ask a lawyer", not answered.
- The keyword checks are regular expressions. A cleverly worded legal claim with no section number, amount or keyword can get past them; a real model run will find cases like this.
- Fact extraction can miss facts or attach a real quote to the wrong field. Quotes prove where a fact came from, not that it is true.
- Hindi act names are checked against a fixed list of aliases. An unlisted Hindi act name is not detected.
- Drafts are first-contact letters, not court pleadings or lawyer-issued legal notices. Nothing is ever sent for you.
- Hinglish drafts are written in English.
- Text is stored unencrypted in Postgres. Cases expire after `SESSION_TTL_HOURS` (default 72), and "Delete my data" removes the case and its graph checkpoints. Messages are sent to whichever model provider you configure.
- The source links were checked on 9 November 2026. Cards expire on their `review_by` date and must be rechecked before then.

## Layout

```
app/
  main.py          FastAPI routes, sessions, budgets, syncing graph state to tables
  graph/           LangGraph state, nodes, prompts and wiring
  llm.py           provider adapter and scripted mock
  verify.py        citation and claim checker
  provenance.py    exact-quote checks for facts
  rules.py         keyword risk rules
  corpus.py        loading and retrieving source cards
  drafts.py        letter templates and Word export
  stt.py           Groq Whisper, Sarvam, mock
  domains.py       fields and follow-up questions per problem type
  texts.py         fixed replies in English, Hindi and Hinglish
  data/sources.json
  static/          front end
migrations/        Alembic
scripts/evaluate.py
tests/             pytest suite, cases.json, mock_llm.json
```
