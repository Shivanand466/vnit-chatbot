# VNIT Chatbot -- container image (works on Hugging Face Spaces, and on any
# Docker host that sets $PORT, e.g. Render/Railway).
#
# Build: docker build -t vnit-chatbot .
# Run:   docker run -p 7860:7860 -e GENAI_API_KEY=<groq key> vnit-chatbot
#        then open http://localhost:7860/
#
# - CPU-only PyTorch: the default wheel bundles ~2.5GB of unused GPU libraries.
# - The search index is built during the image build from data/raw/, and the
#   embedding + reranker models are downloaded then too, so the running
#   container never needs to download anything.
# - Runs as a non-root user (uid 1000), as Hugging Face Spaces requires.
FROM python:3.11-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false
WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --user --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY --chown=user . .
RUN cd pipeline && python chunk.py && python build_index.py

EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
