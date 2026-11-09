# Nyaya AI — Indian Legal Guidance Assistant

Nyaya AI is a multilingual conversational legal-information assistant for everyday issues in India. It builds a structured case from a user's narrative, retrieves a small curated set of legal source cards, verifies generated legal statements, and supports notice interpretation, practice, and fact-confirmed letter drafting. **It is not a lawyer, legal representation, or an automatic filing service.**

## Live application and project links

| Resource | URL |
|---|---|
| **Public Streamlit app** | https://nyayaai-4gzcqxi2pc4gueuij6ygyg.streamlit.app/ |
| **FastAPI backend on Render** | https://nyaya-mfvy.onrender.com/ |
| API health | https://nyaya-mfvy.onrender.com/health |
| Interactive API docs | https://nyaya-mfvy.onrender.com/api/docs |
| Source and tests | https://github.com/kgpgaurav/nyaya_ai |
| Live OpenAI evaluation | [Raw result summary](raw_outputs/live_openai_20261109_133056/summary.json) |

The application is hosted using **Streamlit Community Cloud → Render (FastAPI) → hosted PostgreSQL/pgvector (Neon)**. The cloud backend may need a cold start after inactivity.

## Run locally: Docker Desktop (recommended)

**Prerequisites:** Git, Docker Desktop with Compose running, an OpenAI API key with active credits. Docker provides Python, PostgreSQL, migrations, FastAPI and Streamlit; you **do not need to activate a Windows venv** for this path. Local hosting still needs internet for the OpenAI API.

Open **Windows CMD** in a working directory:

~~~cmd
git clone https://github.com/kgpgaurav/nyaya_ai.git
cd nyaya_ai
copy .env.example .env
notepad .env
~~~

Set `OPENAI_API_KEY` to your private key. Suggested configuration in `.env`:

~~~dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=YOUR_PRIVATE_KEY
STT_PROVIDER=openai
STT_MODEL=whisper-1
EMBEDDING_PROVIDER=none
COOKIE_SECURE=false
~~~

Leave the Compose database URL configured for the Docker service `db` (the hostname works **inside** Compose, not from Windows). **Never commit your `.env` or API key.**

~~~cmd
docker compose up --build -d
docker compose ps -a
~~~

| Local service | URL / expected state |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI | http://localhost:8000 |
| Health endpoint | http://localhost:8000/health |
| Swagger API docs | http://localhost:8000/api/docs |
| `db`, `api`, `streamlit` | Running / healthy |
| `migrate` | Exited (0) — completed migrations and seeding; **not** a server |

Troubleshoot with `docker compose logs --tail=100 migrate`, `docker compose logs --tail=100 api`, and `docker compose logs --tail=100 streamlit`.

**Run scripted tests and evaluation:**

~~~cmd
docker compose --profile test run --rm tests
~~~

**Run real OpenAI evaluation on Windows CMD** (makes billable API calls; stores JSON files on the host):

~~~cmd
docker compose --profile test run --rm -v "%cd%\raw_outputs:/srv/raw_outputs" tests python scripts/evaluate.py --live --out /srv/raw_outputs
~~~

In **PowerShell**, substitute the bind mount with `-v "${PWD}/raw_outputs:/srv/raw_outputs"`.

Files appear under `raw_outputs/live_openai_YYYYMMDD_HHMMSS/`. To stop services **without deleting stored database data**:

~~~cmd
docker compose down
~~~

Avoid `docker compose down -v` unless you deliberately want to delete the database volume.

### Local Python venv (alternative)

For running scripts without Docker, you must also configure a reachable PostgreSQL 16 instance with pgvector; the Compose hostname `db` is not reachable from the Windows host by default. Install `requirements-dev.txt` for backend/evaluation and `streamlit/requirements.txt` for Streamlit. Windows async Psycopg may require `WindowsSelectorEventLoopPolicy`. The supported one-command setup is Docker Compose above.

## Deploying the hosted application

1. **Neon PostgreSQL:** Create a database, run `CREATE EXTENSION IF NOT EXISTS vector;`, and securely copy its **direct/non-pooled** connection string.
2. **Render backend:** Use **New → Blueprint** with this repository. The included [render.yaml](render.yaml) runs `sh /srv/scripts/render_start.sh`, which applies Alembic migrations, seeds legal source cards, and launches Uvicorn. Set `DATABASE_URL` and `OPENAI_API_KEY` as private environment variables. Verify `/health` and `/api/config` before connecting the frontend.
3. **Streamlit Community Cloud:** Deploy repository `kgpgaurav/nyaya_ai`, branch `main`, Python entrypoint `streamlit/app.py`, Python 3.12. Under app **Secrets**, set:

~~~toml
NYAYA_API_URL = "https://nyaya-mfvy.onrender.com"
~~~

4. Open the public Streamlit URL and test **New case**, cited answer, notice, voice recording, fact confirmation where enough facts are available, and case deletion. This is required even after the Render health check passes. **Your local Docker Desktop can remain stopped once both hosted services work.**

## Example inputs and how the model responds

These are **illustrative behaviors, not guaranteed verbatim model answers**. Use fictitious information when demonstrating the public app. Click **New case** between independent examples; choose the indicated mode in the sidebar.

| Scenario | Mode and example prompt | Expected application behavior |
|---|---|---|
| **Rental deposit** | **Auto:** “My landlord in Pune kept my Rs 50,000 deposit. I moved out on 31 August 2026 and returned the keys. What are my options?” | Classifies a deposit dispute; extracts amount and date with quoted evidence; offers cautious, cited next steps and asks for missing tenancy details. |
| **Defective purchase** | **Auto:** “I paid Rs 12,000 for an online mixer grinder on 2 October. It was faulty on day one, and the seller refuses a refund. What should I do?” | Classifies a consumer-refund issue, requests invoice/order details, and provides supported grievance options with relevant source cards. |
| **Unpaid wages** | **Auto:** “BrightTech Solutions has not paid my Rs 35,000 salary for September and October 2026.” | Identifies employer, amount and unpaid period; offers sourced wage-related guidance and follow-up questions rather than a guaranteed outcome. |
| **No explicit notice deadline** | **Understand a notice:** “Dear tenant, rent increases from Rs 18,000 to Rs 22,000 next month. Confirm or vacate.” | Summarizes the notice and does not invent a precise calendar deadline where the text supplies none. |
| **Fake evidence request** | **Auto:** “Can you create a fake rent receipt saying I paid Rs 60,000?” | Refuses to fabricate records and points toward genuine evidence. |
| **Criminal/police matter** | **Auto:** “Police say an FIR was filed against me. What should I do?” | Refers the user to legal counsel and free legal-aid information, rather than handling an unsupported criminal-law workflow. |
| **Letter drafting** | **Draft a letter:** “Please draft a request for return of my deposit.” | Collects required facts, pauses for explicit confirmation when sufficient information exists, then generates a draft for download. An incomplete case **will not** draft immediately. |
| **Hindi input** | **Auto:** “मेरे मकान मालिक ने 40,000 रुपये की डिपॉज़िट वापस नहीं की। अब क्या करूं?” | Detects Hindi, extracts quoted facts, and responds in Hindi when classification succeeds. |
| **Voice input** | Record a short Hindi or English case description using **Voice recording**. | STT transcribes audio through the configured provider; the transcript is then processed by the same graph. Audio needs separate hands-on testing. |

**Known observed limitations:** In the 2026-11-09 GPT-4.1-mini live evaluation, `deposit_en_full` did not enter pending confirmation because required fields remained missing; the cheque-bounce example extracted “within 15 days of receipt” but classified the notice generically and omitted the Section 138 citation. Don't claim these paths are fully reliable without retesting.

### Evaluation evidence

The scripted mock fixture suite and live-model evaluation measure **different things**: mock responses test deterministic filtering, whereas live responses vary. For the run [live_openai_20261109_133056](raw_outputs/live_openai_20261109_133056/summary.json), **12/19 scenarios passed (63.2%)**, with **39,444 input tokens**, **5,453 output tokens**, **2,105 ms median** model-call latency and **3,465 ms p90**. The live voice fixture skipped its scripted audio turn, so that pass does **not** validate live transcription.

## Technical architecture and design decisions

### Component and request flow

~~~text
Browser / microphone
      |
      v
Streamlit (streamlit/app.py) -- HTTP requests + session cookies --> FastAPI (app/main.py)
                                                                |
                                                    Validation, budgets, sessions
                                                                |
                                                                v
                                                          LangGraph workflow
                                                                |
        +------------------------+------------------------------+--------------------+
        |                        |                              |                    |
   Safety / routing        Case fact extraction          Notice reading       Practice mode
        |                        |                              |                    |
        |                        v                              |                    |
        |                Retrieval (Postgres)                  |                    |
        |                        |                              |                    |
        |                  LLM composition                     |                    |
        |                        |                              |                    |
        |              Deterministic verification <------------+--------------------+
        |                   |         |
        |            accepted       rejected --> one retry / safe fallback
        |                   |
        +-------------------+--------------------> API response with citations
                                |
                         Draft requested?
                                |
                       Missing facts? Ask user
                                |
                       Fact confirmation gate
                                |
                       TXT / DOCX download
~~~ 

**1. Frontend and API.** Streamlit renders case history, mode/language selectors, a microphone input, extracted facts, citations, and draft downloads. Its client uses a cookie-preserving HTTP session to call FastAPI's `/api/case`, `/api/case/messages`, `/api/case/voice`, `/api/case/confirm`, `/api/case/export` and deletion endpoints. FastAPI manages case/session lifecycle, validates inputs, records model usage and enforces per-case/day call limits.

**2. LangGraph orchestration.** The graph follows `ingest → guard → [canned/referral | notice | practice | extract → (draft or retrieve → compose → verify → respond)]`. `verify` can route back to `compose` for **one retry**. The graph checkpointer is stored in PostgreSQL, preserving multi-turn context. Drafting uses a LangGraph `interrupt()` so it cannot proceed until facts are explicitly confirmed.

**3. Model operations versus deterministic code.** An LLM performs structured triage, possible risk classification, fact extraction, notice summaries, coaching and answer composition. Pydantic validates structured output. Deterministic Python code checks exact user quotes, detects conflicts, retrieves allowed source cards, enforces legal-source restrictions, quotes deadlines, controls draft gates, and filters unsafe/unsupported output. The LLM is **not** allowed to invent citations or unilaterally authorize drafting.

**4. Data model.** PostgreSQL holds case sessions, messages, facts, timeline events, drafts and generated documents, legal source cards, and model-call metadata (provider/model, tokens, latency, errors). SQLAlchemy and Psycopg provide database access. Alembic handles schema upgrades; the startup seed populates the legal corpus. The schema includes pgvector support, but the default `EMBEDDING_PROVIDER=none` uses regular full-text retrieval rather than an embedding API.

**5. Provenance and law verification.** `app/provenance.py` only accepts extracted facts when the claimed value occurs inside an **exact user-quoted span**; conflicting values should be reconciled rather than silently overwritten. `app/corpus.py` retrieves curated, dated legal source cards. `app/verify.py` rejects answer points with missing/unknown source IDs, source-unsupported acts or section numbers, invented rupee amounts, deadlines, phone numbers or links, and citations to court judgments outside the corpus. A failed composition can be retried once; when verifiable support is inadequate the assistant should hedge instead of inventing legal rules. These checks reduce, but do not eliminate, hallucination risk.

**6. Drafts and user control.** When draft requirements are satisfied, `app/graph/nodes.py` pauses and asks the user to confirm or edit extracted fields. Only after confirmation does `app/drafts.py` render a letter; the user can download TXT or DOCX. The system **does not send or file legal documents automatically**.

**7. Speech and model adapters.** `app/stt.py` performs speech-to-text with the configured provider (OpenAI Whisper is the sample deployment setting). `app/llm.py` abstracts OpenAI/Groq/Gemini/Ollama providers using LangChain and records model usage. This allows swapping models without changing the graph, while maintaining the same verification stages.

**8. Deployment boundaries.** Docker Compose runs `db`, one-shot `migrate`, `api`, and `streamlit` locally. In the public deployment the browser uses Streamlit Community Cloud, FastAPI runs as a Render Docker web service, and persistent PostgreSQL is hosted separately. Secrets belong in Render env vars and Streamlit secrets, **not in Git**.

### Important limitations

Nyaya covers a constrained set of Indian civil/consumer/employment topics with a small curated corpus, not every legal jurisdiction or current rule. State-specific tenancy and employment rules require care. Quote-based facts show **where text came from**, not independent truth. Regex-based verification has gaps; LLM classification may still misclassify notices or fail to flag injection. PostgreSQL case content is not application-level encrypted; avoid real confidential details in public demos, and restrict access/spending before any broader release.

---

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
