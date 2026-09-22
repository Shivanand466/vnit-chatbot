"""
Retrieve the top-k most relevant chunks for a question, with citations.
This is the retrieval half of RAG; answer composition (an LLM turning these
passages into a natural-language answer) is handled separately by generate.py.

UPDATE (2026-09-21): build_index.py can now produce two kinds of index --
real sentence embeddings (preferred, when sentence-transformers + model
download succeeded) or TF-IDF (fallback). retrieve() below reads whichever
one is actually on disk (data["type"]) and uses the matching similarity
method, so nothing else in the pipeline (agent.py, generate.py, api/main.py)
needs to know or care which kind of index it's talking to.
"""
import argparse
import pickle
from pathlib import Path

from sklearn.metrics.pairwise import cosine_similarity

INDEX_PATH = Path(__file__).parent.parent / "data" / "processed" / "index.pkl"

# Cache the loaded embedding model across calls within one process -- agent.py
# calls retrieve() once per sub-question, and reloading a sentence-transformers
# model from disk every time would be slow for no benefit (the model itself
# doesn't change between calls).
_embedding_model_cache = {}


_index_cache = {"mtime": None, "data": None}


def load_index():
    """Load index.pkl, reusing the in-memory copy unless the file changed on disk."""
    mtime = INDEX_PATH.stat().st_mtime
    if _index_cache["mtime"] != mtime:
        with INDEX_PATH.open("rb") as f:
            _index_cache["data"] = pickle.load(f)
        _index_cache["mtime"] = mtime
    return _index_cache["data"]


def _get_embedding_model(model_name: str):
    if model_name not in _embedding_model_cache:
        from sentence_transformers import SentenceTransformer
        _embedding_model_cache[model_name] = SentenceTransformer(model_name)
    return _embedding_model_cache[model_name]


# Weighted reciprocal-rank fusion of embedding and keyword rankings. Tuned on
# fact_ranks.py + evaluate.py (2026-09-22): keyword weight 0.5, K=30 put the
# answer-bearing chunk in the top 3 for 10/13 facts (embeddings alone: 8/13;
# equal weights: 8/13) with benchmark 18/19 (embeddings alone: 17/19).
RRF_K = 30
KEYWORD_WEIGHT = 0.5


def _fuse(embedding_scores, keyword_scores):
    """Combine two rankings by rank position rather than raw score, since the
    scores live on different scales (embeddings ~0.3-0.8, TF-IDF ~0-0.3)."""
    import numpy as np

    def ranks(scores):
        r = np.empty(len(scores), dtype=int)
        r[scores.argsort()[::-1]] = np.arange(1, len(scores) + 1)
        return r

    fused = 1.0 / (RRF_K + ranks(embedding_scores)) + KEYWORD_WEIGHT / (RRF_K + ranks(keyword_scores))
    return fused.argsort()[::-1]


# Reranking: hybrid search quickly picks RERANK_POOL candidates, then a
# cross-encoder reads each (question, passage) pair together and re-orders
# them. Measured 2026-09-22 with 41 documents added to the 81 web pages:
# without it, documents crowded web-page answers down the list (Registrar
# rank 10, Electrical M.Tech rank 5; benchmark 16/19); with it every
# answer-bearing chunk present ranked 1st bar one (rank 4), benchmark 18/19.
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_POOL = 30
_reranker = {"model": None, "failed": False}


def _rerank(question, chunks, candidate_ids):
    """Re-order candidates with the cross-encoder; if it can't be loaded
    (e.g. first run without internet), keep the original order."""
    if _reranker["failed"]:
        return candidate_ids
    if _reranker["model"] is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker["model"] = CrossEncoder(RERANK_MODEL)
        except Exception as e:
            print(f"[rerank] disabled, couldn't load {RERANK_MODEL}: {type(e).__name__}: {e}")
            _reranker["failed"] = True
            return candidate_ids
    pairs = [(question, f"{chunks[i]['title']}. {chunks[i]['text']}") for i in candidate_ids]
    scores = _reranker["model"].predict(pairs)
    return [candidate_ids[j] for j in sorted(range(len(candidate_ids)), key=lambda j: -scores[j])]


def retrieve(question: str, k: int = 3):
    data = load_index()
    chunks = data["chunks"]
    index_type = data.get("type", "tfidf")  # older index.pkl files predate this key -- treat as tfidf

    if index_type == "embeddings":
        model = _get_embedding_model(data["model_name"])
        q_vec = model.encode([question], normalize_embeddings=True)
        sims = cosine_similarity(q_vec, data["embeddings"])[0]
        if "tfidf_matrix" in data:
            keyword = cosine_similarity(data["tfidf_vectorizer"].transform([question]), data["tfidf_matrix"])[0]
            ranked = _rerank(question, chunks, list(_fuse(sims, keyword)[:RERANK_POOL]))[:k]
        else:
            ranked = sims.argsort()[::-1][:k]
    else:
        vectorizer, matrix = data["vectorizer"], data["matrix"]
        q_vec = vectorizer.transform([question])
        sims = cosine_similarity(q_vec, matrix)[0]
        ranked = sims.argsort()[::-1][:k]

    results = []
    for idx in ranked:
        c = chunks[idx]
        results.append({
            "score": float(sims[idx]),
            "text": c["text"],
            "title": c["title"],
            "source_url": c["source_url"],
            "fetched": c.get("fetched", ""),
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=3)
    args = parser.parse_args()

    results = retrieve(args.question, args.k)
    print(f"\nQ: {args.question}\n")
    for r in results:
        print(f"[score {r['score']:.3f}] {r['title']} — {r['source_url']}")
        print(f"  {r['text'][:300]}{'...' if len(r['text']) > 300 else ''}\n")


if __name__ == "__main__":
    main()
