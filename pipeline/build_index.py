"""
Build a retrieval index over the chunked pages -- real sentence embeddings
if available, TF-IDF if not.

UPDATE (2026-09-21, see EXPERIMENTS-LOG.md / RUNBOOK-5-REAL-EMBEDDINGS.md):
this used to be TF-IDF-only, because Claude's own sandbox and device-bridge
tooling can't reach huggingface.co to download embedding model weights
(confirmed blocked, repeatedly). But that block is specific to Claude's own
tools -- Shivanand's machine has real, working internet (confirmed in every
REPORT*.md: it reaches vnit.ac.in and Groq's API directly), so
sentence-transformers' model download should work fine when this script is
actually run there. This function now tries that first and only falls back
to TF-IDF if it can't -- no separate "embeddings mode" flag to remember,
it just uses the better option when it's available.

Two things worth knowing about the fallback:
1. If sentence-transformers isn't installed, or the model download fails
   (network, disk, whatever), this prints exactly why and falls back to
   TF-IDF automatically -- the pipeline never just breaks.
2. Cheap static word-vector averaging was tried as a lighter-weight
   alternative to a real transformer model (see EXPERIMENTS-LOG.md) and
   scored far worse than TF-IDF (4/19 and 13/19 vs TF-IDF's 18/19) -- so
   the fallback here is TF-IDF, not word vectors. A real sentence-transformer
   model is the only tested option that has a real chance of beating TF-IDF;
   word-vector averaging isn't a good middle ground, it's worse than doing
   nothing extra at all.

TF-IDF TUNING (2026-09-21, see REPORT2.md): once the corpus grew from 19
hand-picked pages to the real 79-page crawl (noisy real-world HTML), the
original vectorizer settings' benchmark hit-rate dropped from 100% to 74%.
`min_df=2` (drop single-chunk rare terms) and `sublinear_tf=True` (dampen
repeated-phrase inflation) recovered that to 18/19 = 95%. Kept as the
fallback vectorizer's settings.
"""
import json
import pickle
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"
INDEX_PATH = PROCESSED_DIR / "index.pkl"

# A small, well-regarded general-purpose sentence embedding model (~80MB,
# 384-dim). Good default for a first real-embeddings attempt: fast enough to
# run on a laptop CPU (no GPU needed), no API key needed (fully local once
# downloaded), and widely used so there's plenty of documentation if
# something goes wrong.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _indexed_text(chunk):
    # The title goes into every chunk's indexed text: many documents are
    # near-identical apart from their title (18 hostel fee sheets that differ
    # only in "FIRST YEAR BOYS" vs "SECOND YEAR GIRLS"; a dozen academic
    # calendars differing only in term and year). Measured: answer-bearing
    # chunk in top 3 rose from 11/18 to 12/18 facts.
    return f"{chunk['title']}. {chunk['text']}"


def _build_tfidf_index(chunks):
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [_indexed_text(c) for c in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_df=0.9,
        min_df=2,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    print(f"[TF-IDF] Indexed {len(chunks)} chunks (vocab size {len(vectorizer.vocabulary_)})")
    return {"type": "tfidf", "vectorizer": vectorizer, "matrix": matrix, "chunks": chunks}


def _build_embeddings_index(chunks):
    from sentence_transformers import SentenceTransformer

    print(f"[embeddings] Loading {EMBEDDING_MODEL_NAME} (downloads the model the first time this runs)...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    texts = [_indexed_text(c) for c in chunks]
    print(f"[embeddings] Encoding {len(chunks)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    print(f"[embeddings] Indexed {len(chunks)} chunks (dim {embeddings.shape[1]})")
    return {
        "type": "embeddings",
        "model_name": EMBEDDING_MODEL_NAME,
        "embeddings": embeddings,
        "chunks": chunks,
    }


def _predownload_reranker():
    """Fetch query.py's reranker model now, so the chatbot's first question
    never waits on (or fails for lack of) a download."""
    from query import RERANK_MODEL
    try:
        from sentence_transformers import CrossEncoder
        CrossEncoder(RERANK_MODEL)
        print(f"[rerank] {RERANK_MODEL} ready")
    except Exception as e:
        print(f"[rerank] couldn't download {RERANK_MODEL} ({type(e).__name__}: {e}); "
              f"search will work without reranking")


def main():
    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    try:
        index = _build_embeddings_index(chunks)
        # Hybrid search: keep a keyword (TF-IDF) index alongside the embeddings,
        # so exact words like "Registrar" still count when the embedding model
        # ranks a vaguer passage higher. query.py fuses the two rankings.
        tfidf = _build_tfidf_index(chunks)
        index["tfidf_vectorizer"], index["tfidf_matrix"] = tfidf["vectorizer"], tfidf["matrix"]
        _predownload_reranker()
    except ImportError as e:
        print(f"[fallback] sentence-transformers not installed ({e}). "
              f"Run: pip install sentence-transformers. Falling back to TF-IDF for now.")
        index = _build_tfidf_index(chunks)
    except Exception as e:
        print(f"[fallback] Couldn't build a real embeddings index ({type(e).__name__}: {e}). "
              f"This is usually a network problem downloading the model. Falling back to TF-IDF for now.")
        index = _build_tfidf_index(chunks)

    with INDEX_PATH.open("wb") as f:
        pickle.dump(index, f)
    print(f"Saved {index['type']} index -> {INDEX_PATH}")


if __name__ == "__main__":
    main()
