"""
Deploy the chatbot to a free Hugging Face Space (Docker).

GitHub can store the code but can't run a Python server; Hugging Face Spaces
can, for free (CPU, 16GB RAM). This script:
  1. creates the Space <your-hf-username>/vnit-chatbot (if it doesn't exist),
  2. stores the Groq key as a hidden Space *secret* (never in the code),
  3. restricts browser access to the Space's own page (ALLOWED_ORIGINS),
  4. uploads the project (the Space then builds the Dockerfile and starts).

Keys are read from files, never typed into commands or printed:
  %USERPROFILE%\\hf-token.txt   Hugging Face token with "write" permission
  %USERPROFILE%\\groq-key.txt   Groq API key
(or from HF_TOKEN / GROQ_API_KEY environment variables, as in GitHub Actions)

Run:  python deploy/deploy_to_hf.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACE_NAME = os.environ.get("HF_SPACE_NAME", "vnit-chatbot")

FRONT_MATTER = """---
title: VNIT Chatbot
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Answers questions about VNIT Nagpur from its website
---

"""

EXCLUDE = {".git", "__pycache__", "processed", ".github", "docs"}
EXCLUDE_SUFFIXES = {".bat", ".pyc"}


def _secret(env_name: str, file_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        path = Path.home() / file_name
        if not path.exists():
            sys.exit(f"Missing {env_name}: set it, or save it alone on one line in {path}")
        value = path.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    return value


def _copy_project(dest: Path):
    for item in ROOT.iterdir():
        if item.name in EXCLUDE:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=lambda d, names: [
                n for n in names if n in EXCLUDE or Path(n).suffix in EXCLUDE_SUFFIXES])
        elif item.suffix not in EXCLUDE_SUFFIXES:
            shutil.copy2(item, target)
    readme = dest / "README.md"
    readme.write_text(FRONT_MATTER + readme.read_text(encoding="utf-8"), encoding="utf-8")


def main():
    from huggingface_hub import HfApi

    token = _secret("HF_TOKEN", "hf-token.txt")
    groq_key = _secret("GROQ_API_KEY", "groq-key.txt")
    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/{SPACE_NAME}"
    site = f"https://{user.lower()}-{SPACE_NAME.lower()}.hf.space"

    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    api.add_space_secret(repo_id, "GENAI_API_KEY", groq_key)
    api.add_space_variable(repo_id, "ALLOWED_ORIGINS", site)
    print(f"Space ready: https://huggingface.co/spaces/{repo_id}")

    with tempfile.TemporaryDirectory() as tmp:
        _copy_project(Path(tmp))
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=tmp,
                          commit_message="Deploy VNIT chatbot")
    print(f"Uploaded. The Space now builds (about 10 minutes the first time), then runs at:\n  {site}")


if __name__ == "__main__":
    main()
