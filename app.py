import json
import os
import re

import google.generativeai as genai
import streamlit as st

# ----------------------------- CONFIG ---------------------------------
# Change this if Google renames/retires the model. Check the Gemini docs.
MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(page_title="Fake Job Post Detector", page_icon="🕵️", layout="centered")


def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY")


# ------------------------ STEP 1: RULE-BASED CHECK ---------------------
# (regex pattern, explanation, points added to risk)
RULES = [
    (r"registration fee|security deposit|processing fee|training fee|pay .{0,20}(fee|deposit)",
     "Asks you to pay money (fee/deposit). Real employers never charge applicants.", 35),
    (r"whatsapp|telegram",
     "Hiring is done through WhatsApp/Telegram instead of an official channel.", 20),
    (r"@(gmail|yahoo|hotmail|outlook)\.com",
     "Uses a free personal email instead of a company domain.", 20),
    (r"no experience (needed|required)|no interview|no qualification",
     "Promises a job with no experience/interview.", 15),
    (r"earn .{0,15}(per day|daily|weekly)|guaranteed (income|salary|profit)|easy money",
     "Unrealistic or guaranteed income claims.", 25),
    (r"urgent(ly)? (hiring|required)|limited (seats|slots|vacancies)|apply (immediately|today only)",
     "Uses urgency/pressure to make you act fast.", 10),
    (r"bank account|cnic|passport|id card|credit card|otp|password",
     "Asks for sensitive personal or financial details upfront.", 30),
    (r"work from home.{0,40}(data entry|typing|form filling)|data entry.{0,40}work from home",
     "Classic 'work from home data entry' scam pattern.", 15),
    (r"send (money|payment)|wire transfer|western union|easypaisa|jazzcash",
     "Mentions sending money or mobile-wallet payments.", 25),
]


def rule_based_check(text: str):
    flags, score = [], 0
    for pattern, message, points in RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            flags.append(message)
            score += points
    return min(score, 100), flags


# ------------------------ STEP 2: AI ANALYSIS --------------------------
PROMPT = """You are an expert in detecting recruitment/job scams.
Analyze the job posting below and respond ONLY with valid JSON in this exact shape:
{{
  "scam_score": <integer 0-100, higher = more likely a scam>,
  "verdict": "<Likely Genuine | Suspicious | Likely Scam>",
  "red_flags": ["short explanation", "..."],
  "green_flags": ["short explanation", "..."],
  "advice": "<2-3 sentences of practical advice for the applicant>"
}}

Consider: unrealistic pay, upfront fees, vague company details, personal emails,
chat-app-only communication, poor grammar, urgency, requests for sensitive data,
and whether the role/requirements make sense.

JOB POSTING:
\"\"\"
{job_text}
\"\"\"
"""


def ai_analysis(job_text: str, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        MODEL_NAME,
        generation_config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    response = model.generate_content(PROMPT.format(job_text=job_text[:8000]))
    raw = response.text.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ------------------------ STEP 3: COMBINE ------------------------------
def final_verdict(score: int) -> tuple[str, str]:
    if score >= 65:
        return "🚨 Likely Scam", "red"
    if score >= 35:
        return "⚠️ Suspicious", "orange"
    return "✅ Likely Genuine", "green"


# ----------------------------- UI --------------------------------------
st.title("🕵️ Fake Job Post Detector")
st.caption("Paste a job ad or message. The app checks it with rules + AI and explains the red flags.")

job_text = st.text_area("Job post / message", height=250,
                        placeholder="Paste the full job description, WhatsApp message, or email here...")

col1, col2 = st.columns([1, 3])
analyze = col1.button("Analyze", type="primary")
col2.caption("Tip: include the contact email/number and any payment details.")

if analyze:
    if len(job_text.strip()) < 40:
        st.warning("Please paste a longer job post (at least a few sentences).")
        st.stop()

    api_key = get_api_key()
    if not api_key:
        st.error("Gemini API key not found. Add GEMINI_API_KEY to .streamlit/secrets.toml")
        st.stop()

    rule_score, rule_flags = rule_based_check(job_text)

    with st.spinner("Analyzing..."):
        try:
            ai = ai_analysis(job_text, api_key)
        except Exception as e:
            st.error(f"AI analysis failed: {e}")
            st.stop()

    ai_score = int(ai.get("scam_score", 0))
    # Weighted blend: AI judgment 65%, hard rules 35%
    final_score = round(0.65 * ai_score + 0.35 * rule_score)
    label, color = final_verdict(final_score)

    st.subheader(label)
    st.progress(final_score / 100, text=f"Scam risk: {final_score}/100")

    m1, m2 = st.columns(2)
    m1.metric("AI score", f"{ai_score}/100")
    m2.metric("Rule-based score", f"{rule_score}/100")

    st.markdown("### 🚩 Red flags")
    all_flags = list(dict.fromkeys(rule_flags + ai.get("red_flags", [])))
    if all_flags:
        for f in all_flags:
            st.markdown(f"- {f}")
    else:
        st.write("No major red flags found.")

    if ai.get("green_flags"):
        st.markdown("### ✅ Positive signs")
        for g in ai["green_flags"]:
            st.markdown(f"- {g}")

    st.markdown("### 💡 Advice")
    st.info(ai.get("advice", "Verify the company independently before sharing any details."))

    st.caption("This tool gives an estimate, not a guarantee. Always verify the company on its official website.")
