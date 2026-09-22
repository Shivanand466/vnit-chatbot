# How to run the VNIT chatbot

A plain-language guide for starting the chatbot, demoing it, and fixing common problems.

---

## 1. One-time setup: your Groq key

The chatbot uses **Groq** (a free AI service) to write its answers. It needs a key, which works like a password.

The two old keys were pasted into a chat, so treat them as leaked. Do this once:

1. Go to **https://console.groq.com/keys** and log in.
2. **Delete both old keys** (click the bin icon next to each).
3. Click **Create API Key**, name it `vnit-chatbot`, and copy the key.
4. Open **Notepad**, paste the key (just the key, on one line), and save it as:
   `C:\Users\shiva\groq-key.txt`
   (In the Save dialog, set "Save as type" to **All files**.)

Never paste keys into chats, emails or code. Keep them only in these files:

| File | What it's for |
|---|---|
| `C:\Users\shiva\groq-key.txt` | Groq key, used to write answers |
| `C:\Users\shiva\vnit-secrets.txt` | Google Drive key, used only when refreshing documents |

---

## 2. Start the chatbot

1. Open the folder `VNIT-Website-Chatbot\vnit-chatbot`.
2. **Double-click `start_chatbot.bat`.**
3. A black window opens (that's the server; **leave it open**).
4. It loads the AI search models (about 30 seconds), then the chat page opens in your browser by itself at `http://127.0.0.1:8000/`.
5. Type a question and click **Ask**. Answers take a few seconds.

**To stop:** close the black window.

Each answer shows:
- **Sources**: the web pages or documents it used (click to check them).
- **mode**: `llm (...)` means the AI wrote the answer. `extractive (...)` means the AI couldn't be reached (no key, no internet), so it shows the best matching passages instead.

---

## 3. Good questions for a demo

These were checked against the real sources and answered correctly in testing:

| Question | Correct answer |
|---|---|
| How many undergraduate students does Civil Engineering enroll annually? | 120 per year |
| Tell me about the 5G lab and when was it announced | Announced 27 Oct 2023 at IMC-23 |
| What specializations does the Electrical Engineering M.Tech offer? | Integrated Power Systems; Power Electronics & Drives |
| Who is the current Director of VNIT? | Prof. (Dr.) Prem Lal Patel |
| What is the email of the Dean (Academic)? | deanacd@vnit.ac.in |
| When was the Mechanical Engineering department established? | 1960, with the institute |
| What tuition fee do SC/ST B.Tech students pay? | Nil |
| How much money does the Kotak Kanya Scholarship give per year? | ₹1.5 lakh |
| When do classes start for first year B.Tech students in Winter 2026? | 19 August 2026 |

Tip: ask one clear question at a time and mention the programme and year (e.g. "first year B.Tech", "Winter 2026"). Similar-looking documents are the chatbot's weak spot.

Also show one question it **can't** answer (for example: *"What is the hostel wifi password?"*). It says the information isn't in its sources instead of making something up. That's the most important feature: examiners like seeing that it doesn't hallucinate.

---

## 4. If something goes wrong

| What you see | What to do |
|---|---|
| The black window flashes and closes | Right-click `start_chatbot.bat` → *Edit*: check the Python path. Or ask for help with the error text. |
| "address already in use" | The chatbot is already running in another black window. Close all of them and try again. |
| Answers say `mode: extractive (no GENAI_API_KEY set)` | The key file is missing. Redo section 1, step 4. |
| `mode: extractive (LLM call failed: 401 ...)` | The key is wrong or deleted. Create a new one (section 1). |
| `mode: extractive (LLM call failed: 429 ...)` | Too many questions too fast for the free plan. Wait a minute. |
| No wifi at the venue | It still works in `extractive` mode (shows passages, not written answers). Consider using a phone hotspot. |
| The page says it can't reach the server | Check the black window is still open, then reload `http://127.0.0.1:8000/`. |
| "Too many questions - please wait a minute" | A safety limit (10 questions per minute per person). Wait a minute. |

---

## 5. Updating the chatbot's knowledge (optional, advanced)

The chatbot only knows what was downloaded. To refresh it later, open **Anaconda Prompt**, then:

```
cd C:\Users\shiva\OneDrive\Desktop\LIBRARY\FYP\VNIT-Website-Chatbot\vnit-chatbot\pipeline

REM 1. Refresh website pages
python recrawl.py

REM 2. Find and read new documents (notices, fee sheets...) - slow: about 1 minute per document
%USERPROFILE%\.venvs\vnit-pdf\Scripts\python.exe ingest_documents.py discover
%USERPROFILE%\.venvs\vnit-pdf\Scripts\python.exe ingest_documents.py convert

REM 3. Rebuild the search index
python chunk.py
python build_index.py

REM 4. Check quality
python evaluate.py
python fact_ranks.py
set GENAI_API_KEY=<paste key here only in this window>
python check_answers.py
```

---

## 6. What's in the folder

| Folder / file | What it is |
|---|---|
| `start_chatbot.bat` | Double-click to start |
| `frontend/index.html` | The chat page |
| `api/main.py` | The small server that answers questions |
| `pipeline/` | Everything that collects the website, reads documents and finds answers |
| `data/raw/` | The collected text: web pages and `doc_*.txt` documents |
| `data/processed/` | The search index built from that text |
| `data/documents/` | List of all documents found, and which were used or skipped |
| `APPLICATION.md` | Technical description of how it all works |
