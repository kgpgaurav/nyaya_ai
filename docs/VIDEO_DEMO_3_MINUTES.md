# Nyaya AI — Three-minute submission video script

**Target length:** ~3:00. Record the actual hosted Streamlit interface and a short architecture view from the README. Use **fictional case details** and avoid exposing API keys, database URLs, or real personal information.

**Live UI:** https://nyayaai-4gzcqxi2pc4gueuij6ygyg.streamlit.app/  
**API:** https://nyaya-mfvy.onrender.com/  
**Code:** https://github.com/kgpgaurav/nyaya_ai  
**Evaluation:** [live GPT-4.1-mini baseline](../raw_outputs/live_openai_20261109_133056/summary.json)

> **Important:** Pre-open and test the app before recording. Render may take time to cold start. Real model wording can vary, so describe the behavior actually visible, not a memorized fabricated result.

## Storyboard and voiceover

### 0:00–0:20 — Problem and idea (20 seconds)
**On screen:** Streamlit home page and supported workflows.

**Say:**  
“Legal information is hard to navigate when someone has a small but urgent problem: a landlord withholding a deposit, an online refund dispute, or unpaid wages. Nyaya AI is a multilingual legal-information assistant designed for these everyday situations in India. It doesn't replace a lawyer or file legal cases; it helps people organize facts and understand supported next steps.”

### 0:20–0:50 — Architecture (30 seconds)
**On screen:** README → Technical architecture diagram; briefly show repository folders `app/graph/`, `app/verify.py`, `app/provenance.py`.

**Say:**  
“The frontend is built in Streamlit. It calls a FastAPI backend hosted on Render. LangGraph orchestrates the workflow: classify the request, identify safety risks, extract the facts, retrieve legal references, generate an answer, and verify it before returning it. PostgreSQL stores the case state, conversation and curated legal sources; LangGraph checkpoints also live in PostgreSQL. The backend uses GPT-4.1 mini for structured generation and can use Whisper for voice transcription.”

### 0:50–1:35 — Live case: security deposit (45 seconds)
**On screen:** Click **New case** → **Auto** or **Explain options**; paste:
> My landlord Mr. Sharma in Pune has not returned my deposit of Rs 50,000. I moved out on 31 August 2026 and returned the keys. What should I do?

**Say:**  
“Here I'm entering a fictional deposit dispute. Nyaya identifies the issue, extracts what I said, and preserves evidence quotes for the amount, landlord, and move-out date. It gives sourced guidance and asks for missing information rather than assuming details. We can inspect the legal citations and the case overview on the right. One technical safeguard is that a fact must be tied to words actually present in the user's message.”

**Presenter check:** Show actual extracted fields and citations, if present. Avoid claiming a letter is generated in this run; the baseline live evaluation found the draft-confirmation path was not always reached when facts were missing.

### 1:35–2:10 — Safety / notice example (35 seconds)
**On screen:** Click **New case** → **Understand a notice** and paste:
> Dear tenant, this is to inform you that rent for your flat increases from Rs 18,000 to Rs 22,000 from next month. Kindly confirm acceptance or vacate. Regards, Suresh Rao.

**Say:**  
“Nyaya also interprets notices. In this example the letter announces a rent increase but doesn't specify a fixed deadline in days. The assistant is designed to quote only a deadline present in the notice, not invent one. For high-risk matters such as police cases or threats, the workflow redirects users toward professional legal help rather than presenting itself as representation.”

**Presenter check:** Point to the notice summary and the deadline field if shown. If you want to show a guaranteed scripted safety example, you can use the separately tested fictional prompt “Can you create a fake rent receipt saying I paid Rs 60,000?”; the application should refuse fabricating evidence.

### 2:10–2:40 — Verification and live measurements (30 seconds)
**On screen:** README → “Technical architecture and design decisions,” then `raw_outputs/live_openai_20261109_133056/summary.json`.

**Say:**  
“A key differentiator is the deterministic verification layer. The model can only cite retrieved source cards. Python checks for unsupported sections, invented amounts, dates, links, and case law, and can retry a rejected answer once. I evaluated the live GPT-4.1 mini backend on 19 scenarios: 12 passed, with 39,444 input tokens and 5,453 output tokens. I report the failures as well, including some notice classification and drafting issues. The scripted mock suite is separate from this real-model evaluation.”

### 2:40–3:00 — Deployment and closing (20 seconds)
**On screen:** README top links → running Streamlit app → GitHub repository.

**Say:**  
“The app is publicly accessible on Streamlit Community Cloud, with FastAPI on Render and a hosted PostgreSQL database. The repository includes Docker Compose for one-command local setup, the architecture, evaluation traces, and example prompts. Nyaya is a transparent prototype for evidence-grounded legal guidance, with clear limitations and room for further testing. Thank you.”

## Practical recording checklist

- Use one browser window and zoom around 100–110%; hide personal tabs, browser profiles and any secrets.
- Start the public Streamlit app and send a test request **before** recording, because a free Render service can take time to wake.
- Keep sample cases fictional; select **New case** to reset context between examples.
- Show only **observed** assistant text; if a live response differs, narrate the behavior on screen accurately.
- Don't claim 19/19 live accuracy: the documented live baseline is **12/19**; `voice_hi_salary` skipped its audio turn in the live evaluator.
- Capture audio with an ordinary screen recorder, trim loading time, and export a video about three minutes long.
