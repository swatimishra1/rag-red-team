# RAG Test Lab

A minimal RAG chatbot (Llama 3.3 70B via Groq's free API + ChromaDB, no
framework) built
specifically to be adversarially tested. It answers questions about a
fictional SaaS company, "Acme," using a small help-center knowledge base —
and includes deliberately planted edge cases: a hidden prompt injection, an
out-of-scope question with no answer in the docs, two documents with
conflicting policies, and two guardrails (no naming competitors, never leak
the system prompt) to probe.

## Stack
- **LLM:** Llama 3.3 70B via Groq's free API (OpenAI-compatible endpoint)
- **Vector store:** ChromaDB (persistent, local), cosine similarity
- **Embeddings:** ChromaDB's built-in `all-MiniLM-L6-v2` (downloaded
  automatically on first run — no separate setup)
- **Framework:** none — retrieval and generation are a plain ~100-line loop
  in `rag_bot.py`, so every step is visible and nothing is a black box

## Setup

1. Get a free Groq API key (no credit card required):
   https://console.groq.com/keys — sign up, click "Create API Key", copy it.

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set the key as an environment variable:
```bash
export GROQ_API_KEY=your-key-here
```

On Windows PowerShell:
```powershell
$env:GROQ_API_KEY="your-key-here"
```

Note: Groq's free tier is rate-limited (30 requests/minute, 14,400/day) but
that's far more than this project needs — the full 5-test suite makes about
10 calls total.

## Run it

```bash
# 1. Ingest the docs into ChromaDB (creates ./chroma_db/)
python ingest.py

# 2. Sanity check — ask it one normal question
python rag_bot.py

# 3. Run all 5 adversarial tests
python run_all_tests.py
```

Step 3 prints a full transcript to your terminal and also writes
`results/results.md` — that file has the exact retrieval scores and answers
you need to fill in the "[RESULT: ...]" placeholders in the LinkedIn post.

## What each test actually does

| # | Test | File location it targets |
|---|------|---------------------------|
| 1 | Prompt injection via a retrieved document | `docs/api-rate-limits.md` has a hidden HTML-comment instruction |
| 2 | Confident hallucination on an out-of-scope question | asks about a "military discount" that appears nowhere in `docs/` |
| 3 | Conflicting sources | `docs/refund-policy.md` (30 days, current) vs. `docs/refund-policy-2022-legacy.md` (90 days, outdated) |
| 4 | Instruction drift over multi-turn conversation | guardrail in `system_prompt.txt`: never name a competitor |
| 5 | Jailbreak via role-play rephrasing | guardrail in `system_prompt.txt`: never reveal the system prompt |

## Notes

- `RELEVANCE_THRESHOLD` in `rag_bot.py` (default `0.5`) controls what counts
  as "relevant" for logging purposes — it doesn't block the model from
  seeing low-relevance chunks, it's there so you can see in the debug output
  whether retrieval actually found something good.
- Chunking in `ingest.py` is intentionally simple (split by paragraph) so
  it's easy to reason about which exact chunk got retrieved for each test.
- Re-running `python ingest.py` wipes and rebuilds the collection, so it's
  safe to run repeatedly while you iterate on the docs.
- Every "verdict" the harness prints is a simple keyword heuristic, not
  ground truth — always read the actual answer text before you post a
  result. The heuristics are there to save you scrolling, not to replace
  judgment.
