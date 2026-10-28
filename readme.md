# Fake Job Post Detector

Paste a job ad and get a scam-risk score, red flags, and advice.
Built with Streamlit + Gemini Flash + rule-based checks.

## Run locally
    pip install -r requirements.txt
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then add your key
    streamlit run app.py
