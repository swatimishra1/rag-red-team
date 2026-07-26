"""
Core RAG loop: retrieve from Chroma, then generate with Llama 3.3 70B via Groq.

Groq's API is OpenAI-compatible, so we reuse the `openai` Python client and
just point it at Groq's endpoint. Groq's free tier requires no credit card.

Exposes `ask()`, which returns both the answer AND the retrieval debug info
(scores, sources) so you can log evidence for each test case, not just the
final answer.

Requires GROQ_API_KEY to be set in your environment.
Get a free key at: https://console.groq.com/keys
"""

from __future__ import annotations

import os

import chromadb
from openai import OpenAI

DB_DIR = "chroma_db"
COLLECTION_NAME = "help_center"
MODEL = "llama-3.3-70b-versatile"
RELEVANCE_THRESHOLD = 0.5  # similarity below this = "not relevant"
TOP_K = 3

_client = chromadb.PersistentClient(path=DB_DIR)
_collection = _client.get_collection(COLLECTION_NAME)

# Groq exposes an OpenAI-compatible endpoint, so the same client works —
# just point base_url at Groq and use a Groq key instead of an OpenAI key.
_llm = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

with open("system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """Return top_k chunks with cosine similarity scores (higher = closer)."""
    results = _collection.query(query_texts=[query], n_results=top_k)

    hits = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        similarity = 1 - distance  # cosine distance -> similarity
        hits.append({
            "text": doc,
            "source": meta["source"],
            "similarity": round(similarity, 3),
        })
    return hits


def ask(query: str, conversation_history: list[dict] | None = None,
        extra_system_note: str = "") -> dict:
    """
    Run one turn of the RAG loop.

    conversation_history: prior turns as [{"role": "user"/"assistant", "content": str}, ...]
    extra_system_note: optional extra instruction appended to the system prompt
                        (used by the jailbreak/injection tests to simulate context).

    Returns dict with: answer, retrieved (list of chunks+scores), used_context (bool)
    """
    retrieved = retrieve(query)
    relevant = [r for r in retrieved if r["similarity"] >= RELEVANCE_THRESHOLD]

    context_block = "\n\n---\n\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in retrieved
    )

    system = SYSTEM_PROMPT
    if extra_system_note:
        system += "\n\n" + extra_system_note

    messages = [{"role": "system", "content": system}]
    messages.extend(conversation_history or [])
    messages.append({
        "role": "user",
        "content": (
            f"Context retrieved from the help center:\n\n{context_block}\n\n"
            f"---\n\nCustomer question: {query}"
        ),
    })

    response = _llm.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=messages,
    )

    answer = response.choices[0].message.content

    return {
        "answer": answer,
        "retrieved": retrieved,
        "used_relevant_context": len(relevant) > 0,
    }


if __name__ == "__main__":
    # Quick manual smoke test.
    result = ask("What's your refund window?")
    print("ANSWER:\n", result["answer"])
    print("\nRETRIEVED:")
    for r in result["retrieved"]:
        print(f"  {r['source']}  similarity={r['similarity']}")
