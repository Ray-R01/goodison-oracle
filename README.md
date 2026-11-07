# The Goodison Oracle — Personal Dashboard 🔵

A personal Everton command centre with two possible verdicts only: **GLORIOUS** (best club in the world) or **DOOM** (worst club in the world).

## Sections
Overview · Match centre · Newsroom · Supporter pulse · AI pundit · Randomiser · Mood history · Settings.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Optional Streamlit Secrets
```toml
OPENAI_API_KEY = "your-api-key"
OPENAI_MODEL = "gpt-4.1-mini"
DASHBOARD_PASSWORD = "choose-a-long-password"
```
Never commit secrets. `DASHBOARD_PASSWORD` enables a simple password gate; it is not enterprise-grade authentication.

## Deploy
Push `app.py`, `requirements.txt`, `README.md` and `.gitignore` to a GitHub repository. Then connect it at https://share.streamlit.io/, select `app.py`, and deploy. Add secrets in the app's Settings → Secrets.

## OBS / Streamlabs
Use the deployed dashboard as a Browser Source if you want to display the full dashboard. A dedicated transparent compact overlay is a separate next step.

## Data caveats
ESPN's public scoreboard endpoint is not an official Everton API; RSS feeds and Reddit can be delayed or rate-limited. TextBlob is a rough sentiment heuristic, not a representative supporter poll. Mood history uses local SQLite and may reset on ephemeral cloud storage. This is an unofficial fan project, not affiliated with Everton FC.
