from __future__ import annotations

import pandas as pd
import streamlit as st

from sentinel.engine import (
    FEATURES, build_world, detect_events, generate_events, recommend_response,
    summarize_world, explain_with_ollama, evaluate_demo
)

st.set_page_config(page_title="SENTINEL X // Cyber Defense", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Rajdhani:wght@400;500;600;700&display=swap');
:root { --cyan:#48f7ff; --pink:#ff3cac; --red:#ff5263; --green:#65ffb5; }
.stApp { background: radial-gradient(ellipse at 15% 0%, #15264a 0%, #090d18 45%, #05070d 100%); color:#e6f7ff; }
h1,h2,h3 { font-family:'Orbitron',sans-serif !important; letter-spacing:.04em; }
p,div,label,span { font-family:'Rajdhani',sans-serif; }
[data-testid="stMetric"] { background:linear-gradient(135deg,rgba(15,31,55,.95),rgba(11,14,29,.95)); border:1px solid #24435d; padding:15px; border-radius:12px; box-shadow:0 0 18px #00d9ff12; }
[data-testid="stMetricLabel"] { color:#82a9c8 !important; }
[data-testid="stMetricValue"] { color:#48f7ff !important; font-family:'Orbitron',sans-serif; }
div.stButton > button { border:1px solid #48f7ff; background:#0b1b2c; color:#48f7ff; border-radius:8px; font-weight:700; }
div.stButton > button:hover { background:#12354b; border-color:#ff3cac; color:white; box-shadow:0 0 15px #ff3cac55; }
section[data-testid="stSidebar"] { background:#080d18; border-right:1px solid #18334b; }
div[data-testid="stDataFrame"] { border:1px solid #1d3b55; border-radius:8px; }
.sx-banner { border:1px solid #214f67; border-left:4px solid #48f7ff; padding:18px 22px; border-radius:10px; background:linear-gradient(110deg,#0c1d31,#111225); margin-bottom:16px; }
.sx-kicker { color:#48f7ff; font-family:'Orbitron',sans-serif; font-size:12px; letter-spacing:.2em; }
.sx-title { color:white; font-family:'Orbitron',sans-serif; font-size:32px; font-weight:800; }
.sx-sub { color:#9bb7ce; font-size:17px; }
.sx-tag { color:#ff7ac7; font-family:'Orbitron',sans-serif; font-size:11px; }
</style>
""", unsafe_allow_html=True)

if "events" not in st.session_state:
    st.session_state.events = generate_events(120, seed=23)
if "world" not in st.session_state:
    st.session_state.world = build_world()
if "responses" not in st.session_state:
    st.session_state.responses = []

st.markdown("""
<div class="sx-banner">
 <div class="sx-kicker">AUTONOMOUS DEFENSE GRID // BUILD 0.1.0</div>
 <div class="sx-title">SENTINEL X</div>
 <div class="sx-sub">Hybrid AI cyber-defense simulation · Observe. Predict. Defend.</div>
 <div class="sx-tag">● SIMULATION MODE ACTIVE &nbsp; // &nbsp; NO LIVE NETWORK ACTIONS</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ◈ CONTROL DECK")
    st.caption("SIMULATED TELEMETRY ONLY")
    n_events = st.slider("Telemetry batch size", 30, 300, 120, 10)
    scenario = st.selectbox("Inject scenario", [
        "Mixed traffic", "Port scan", "Credential brute force",
        "Data exfiltration", "Lateral movement"
    ])
    st.divider()
    st.markdown("### OPTIONAL LLM")
    ollama_url = st.text_input("Ollama endpoint", "http://localhost:11434")
    ollama_model = st.text_input("Model name", "qwen3:4b")
    st.caption("LLM is optional. Core detection runs locally without it.")
    if st.button("↻ Reset simulation", use_container_width=True):
        st.session_state.events = generate_events(n_events, seed=None, scenario=scenario)
        st.session_state.responses = []
        st.rerun()

events = st.session_state.events
if st.button("⚡ GENERATE NEW TELEMETRY", type="primary"):
    st.session_state.events = generate_events(n_events, seed=None, scenario=scenario)
    events = st.session_state.events
    st.session_state.responses = []
    st.rerun()

scored = detect_events(events)
summary = summarize_world(scored)

c1, c2, c3, c4 = st.columns(4)
c1.metric("OBSERVED FLOWS", f"{len(scored):,}")
c2.metric("FLAGGED ANOMALIES", f"{int(scored['is_anomaly'].sum()):,}")
c3.metric("CRITICAL RISK", f"{int((scored['risk_score'] >= 80).sum()):,}")
c4.metric("HOSTS IN SIMULATION", str(len(st.session_state.world)))

st.markdown("## ◈ THREAT SURFACE")
left, right = st.columns([1.25, 1])
with left:
    st.markdown("### Network activity")
    chart = scored.sort_values("timestamp").set_index("timestamp")[["risk_score"]].tail(80)
    st.area_chart(chart, color="#ff3cac", height=250)
    st.caption("Risk score over the most recent simulated events. This is not a live network feed.")
with right:
    st.markdown("### Risk distribution")
    counts = pd.cut(scored["risk_score"], bins=[-1, 29, 59, 79, 100],
                    labels=["LOW", "GUARDED", "HIGH", "CRITICAL"]).value_counts().reindex(
                        ["LOW", "GUARDED", "HIGH", "CRITICAL"], fill_value=0)
    st.bar_chart(counts, color="#48f7ff", height=250)

st.markdown("## ◈ DEFENSE AGENTS")
a, b, c = st.columns(3)
a.markdown("**01 / WATCHTOWER**")
a.write("Monitors flow behavior and highlights anomalies.")
b.markdown("**02 / SENTINEL**")
b.write("Ranks alerts using interpretable, rule-based risk factors.")
c.markdown("**03 / AEGIS**")
c.write("Proposes a safe response for a human to review.")

alerts = scored[scored["risk_score"] >= 60].sort_values("risk_score", ascending=False).head(12)
if alerts.empty:
    st.success("No high-risk simulated events in this batch. Try a threat scenario.")
else:
    st.markdown("### Priority queue")
    show_cols = ["timestamp", "source", "destination", "scenario", "risk_score", "is_anomaly", "reason"]
    st.dataframe(alerts[show_cols], use_container_width=True, hide_index=True)

st.markdown("## ◈ RESPONSE SIMULATOR")
st.caption("Responses are recommendations only. No host is blocked and no real system is modified.")
if not alerts.empty:
    chosen_index = st.selectbox(
        "Select alert",
        alerts.index.tolist(),
        format_func=lambda idx: f"{alerts.loc[idx, 'source']} → {alerts.loc[idx, 'destination']} | risk {int(alerts.loc[idx, 'risk_score'])} | {alerts.loc[idx, 'scenario']}"
    )
    selected = scored.loc[chosen_index].to_dict()
    recommendation = recommend_response(selected)
    st.info(f"**Suggested action:** {recommendation['action']}  \n**Reason:** {recommendation['reason']}")
    if st.button("Add recommendation to audit log"):
        st.session_state.responses.append({
            "event_id": str(selected["event_id"]),
            "timestamp": str(selected["timestamp"]),
            "risk_score": int(selected["risk_score"]),
            "action": recommendation["action"],
            "reason": recommendation["reason"],
            "status": "SIMULATED / HUMAN REVIEW REQUIRED"
        })
        st.success("Recommendation recorded in the session audit log.")
    with st.expander("Ask optional local LLM to explain this alert"):
        if st.button("Explain with Ollama"):
            with st.spinner("Contacting optional Ollama model..."):
                answer = explain_with_ollama(selected, recommendation, base_url=ollama_url, model=ollama_model)
            st.write(answer)
else:
    st.write("Generate a batch containing suspicious activity to test the response simulator.")

if st.session_state.responses:
    st.markdown("### Audit log")
    audit = pd.DataFrame(st.session_state.responses)
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.download_button("Download audit log CSV", audit.to_csv(index=False), "sentinel_x_audit.csv", "text/csv")

with st.expander("Model notes and evaluation"):
    st.write(
        "The anomaly detector is an Isolation Forest fitted on synthetic baseline traffic. "
        "Its anomaly flag is not a verified attack label. Risk scoring combines model output "
        "with scenario and telemetry heuristics. Scenario labels are available only because "
        "this is a controlled simulator."
    )
    st.json(evaluate_demo(scored))

st.markdown("---")
st.caption("SENTINEL X // Educational defensive simulation. Not a production IDS, SIEM, or automated containment system.")
