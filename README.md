# Versight — AI Pre-Editor (prototype)

This is a working prototype of the **AI pre-editor**, one of Versight's two
core differentiators (alongside the template intelligence system). It's a
standalone FastAPI service + demo UI so it can be exercised on its own before
being wired into the Model B middleware (JIRA / SVN / Enovia / Word).

## What it checks

A document (SOP, work instruction, change notice, or generic) goes through
four passes:

1. **Readability** — Flesch-Kincaid grade level, average sentence length,
   passive-voice detection, long-sentence flagging. Pure rule-based, no
   network call, runs instantly.
2. **Terminology compliance** — checks the text against a configurable
   glossary of non-standard/ambiguous terms → preferred terms (e.g. "should"
   → "must", "as needed" → "per the interval specified in..."). Also
   rule-based.
3. **Structure / template compliance** — confirms the document contains the
   required sections for its type (e.g. an SOP needs Purpose, Scope,
   Definitions, Responsibilities, Required Materials, Safety Precautions,
   Procedure, References, Revision History) and that they appear in order.
4. **AI review** — a Claude call that's told what the rule-based passes
   already found, and asked to focus on what they can't catch: procedural
   ambiguity, safety-relevant gaps, and internal inconsistency. This is the
   pass that would catch something like a single run-on step that buries a
   quality-hold escalation path inside a torque-check instruction.

Everything is combined into one scored report (0–100) with a plain-language
summary.

## Project layout

```
versight-ai-preeditor/
├── backend/
│   ├── main.py            FastAPI app (POST /analyze, GET /health)
│   ├── models.py          Pydantic request/response schemas
│   ├── readability.py     Flesch-Kincaid, passive voice, sentence length
│   ├── terminology.py     Glossary-based compliance checking
│   ├── structure.py       Template/section checking
│   ├── ai_review.py       Claude API call for clarity/ambiguity/safety
│   ├── config/
│   │   ├── manufacturing_glossary.json   sample controlled vocabulary
│   │   └── sop_template.json             required sections per doc type
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html          single-page demo UI (vanilla JS, no build step)
└── README.md
```

## Running it locally

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY (skip this if you only want rule-based checks)

uvicorn main:app --reload
```

Then open **http://localhost:8000/** — the FastAPI app serves the demo UI
directly, so there's nothing else to run. Paste a document, pick a document
type, and click Analyze.

Without an API key set, `/analyze` still works — it just returns an empty
`ai_suggestions` list and the score reflects only the rule-based checks. You
can also force this per-request with `"skip_ai_review": true` in the request
body (the demo UI has a checkbox for this).

## Deploying it so other people can use it

This is a real backend service (not a static page), so it needs an actual
host — Render and Railway both work well for a small FastAPI + Docker app
and have usable free tiers. Config files for both are already in this repo:

- `Dockerfile` — builds the service; both platforms can build from it directly.
- `render.yaml` — a Render Blueprint. In the Render dashboard: **New → Blueprint**,
  point it at this repo (or upload it), and it picks up the service definition,
  build, and health check automatically.
- `railway.json` — Railway reads this automatically once you deploy the repo
  with **New Project → Deploy from repo** (or `railway up` from the CLI).

Either way, the one thing you must set by hand in the platform's dashboard is
the **`ANTHROPIC_API_KEY`** environment variable — it's deliberately left out
of both config files so it never ends up committed anywhere.

### Before you flip it public: cost and abuse protection

Every `/analyze` call that isn't `skip_ai_review: true` spends *your*
Anthropic API key, not the caller's. Once this has a public URL, that's true
for every visitor, not just you. Two things are already built in to bound
that:

- **Rate limiting** (`rate_limit.py`) — caps AI-reviewed requests per client
  IP: `RATE_LIMIT_MAX_REQUESTS` (default 20) per `RATE_LIMIT_WINDOW_SECONDS`
  (default 3600). It's in-memory and per-instance, which is fine for a single
  free-tier dyno; it resets on redeploy and won't hold up across multiple
  instances, but that's the right amount of protection for a demo.
- **Request size cap** (`MAX_TEXT_LENGTH`, default 20000 chars) — stops one
  oversized paste from blowing up token spend on a single call.

Both are environment variables (see `render.yaml` / set directly in
Railway's dashboard) so you can tighten or loosen them without a code change.
For anything beyond a demo — real design-partner usage — the next step up is
a per-user API key or invite-gated access rather than an open rate limit.

### API

`POST /analyze`

```json
{
  "text": "...",
  "document_type": "SOP",
  "glossary_overrides": {"custom term": "preferred term"},
  "required_sections": ["Purpose", "Scope", "Procedure"],
  "skip_ai_review": false
}
```

Returns readability metrics, terminology issues, structure results, AI
suggestions, an overall 0–100 score, and a one-line summary. See
`backend/models.py` for the full response schema, or hit `/docs` for the
interactive OpenAPI page FastAPI generates automatically.

## Customizing for a real manufacturing floor

- **Glossary**: `backend/config/manufacturing_glossary.json` is a starting
  sample (weak modals, vague quantities, non-standard PPE phrasing). Swap in
  the actual controlled vocabulary / style guide terms once you have them —
  this is the piece that should eventually sync from wherever the real style
  guide lives.
- **Templates**: `backend/config/sop_template.json` holds the required
  section list per document type. Add real document types and section lists
  as they're finalized.
- **Model**: `ai_review.py` defaults to `claude-sonnet-4-5`; override with
  `VERSIGHT_MODEL` in `.env` if needed.

## Where this fits into the bigger Versight architecture

Per the three-app design (Next.js web, FastAPI backend, Tauri/Rust desktop
agent), this backend is the FastAPI piece and can be mounted as-is behind the
Next.js frontend later — the `/analyze` endpoint is the seam. The desktop
agent would be the thing watching SVN/Enovia checkouts and calling this
endpoint automatically before a document goes back upstream.

Two natural next steps once this is validated on real documents:

1. Score the report against a named rubric instead of the ad-hoc weighting
   in `compute_overall_score()` — this is a good place to plug in something
   like the DQF-M heuristics if you want the tool and the thesis to share a
   scoring language.
2. Add a `/analyze/batch` endpoint so a whole document set can be scored at
   once, which is what you'd want for the "10-15 manufacturer discovery
   conversations" demo — a before/after score across a real customer's
   existing SOP library is a much stronger pitch than a single-document demo.
