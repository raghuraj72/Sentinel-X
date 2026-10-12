from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import requests
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = [
    "duration_ms", "bytes_out", "bytes_in", "packets",
    "failed_logins", "unique_ports", "connection_rate"
]

SCENARIOS = ["normal", "port_scan", "brute_force", "data_exfiltration", "lateral_movement"]


def build_world():
    return [
        {"host": "EDGE-01", "role": "Gateway", "zone": "Perimeter", "status": "ONLINE"},
        {"host": "AUTH-02", "role": "Identity", "zone": "Core", "status": "ONLINE"},
        {"host": "APP-03", "role": "Application", "zone": "Core", "status": "ONLINE"},
        {"host": "DB-04", "role": "Database", "zone": "Restricted", "status": "ONLINE"},
        {"host": "WORK-05", "role": "Workstation", "zone": "Endpoint", "status": "ONLINE"},
        {"host": "FILE-06", "role": "File server", "zone": "Restricted", "status": "ONLINE"},
    ]


def _sample_row(rng, scenario, timestamp, i):
    if scenario == "normal":
        row = {
            "duration_ms": int(rng.lognormal(5.0, .55)),
            "bytes_out": int(rng.lognormal(8.0, .8)),
            "bytes_in": int(rng.lognormal(8.3, .8)),
            "packets": int(max(1, rng.lognormal(3.2, .5))),
            "failed_logins": int(rng.choice([0, 0, 0, 0, 1])),
            "unique_ports": int(rng.choice([1, 1, 1, 2, 3])),
            "connection_rate": round(float(rng.uniform(.1, 8)), 2),
        }
    elif scenario == "port_scan":
        row = {
            "duration_ms": int(rng.integers(10, 400)),
            "bytes_out": int(rng.integers(30, 1200)),
            "bytes_in": int(rng.integers(0, 500)),
            "packets": int(rng.integers(30, 500)),
            "failed_logins": 0,
            "unique_ports": int(rng.integers(20, 150)),
            "connection_rate": round(float(rng.uniform(25, 180)), 2),
        }
    elif scenario == "brute_force":
        row = {
            "duration_ms": int(rng.integers(100, 2000)),
            "bytes_out": int(rng.integers(100, 2500)),
            "bytes_in": int(rng.integers(100, 3000)),
            "packets": int(rng.integers(10, 180)),
            "failed_logins": int(rng.integers(8, 80)),
            "unique_ports": int(rng.integers(1, 4)),
            "connection_rate": round(float(rng.uniform(15, 100)), 2),
        }
    elif scenario == "data_exfiltration":
        row = {
            "duration_ms": int(rng.integers(5000, 90000)),
            "bytes_out": int(rng.integers(1_000_000, 30_000_000)),
            "bytes_in": int(rng.integers(100, 50000)),
            "packets": int(rng.integers(1000, 40000)),
            "failed_logins": 0,
            "unique_ports": int(rng.integers(1, 5)),
            "connection_rate": round(float(rng.uniform(1, 20)), 2),
        }
    else:  # lateral_movement
        row = {
            "duration_ms": int(rng.integers(100, 8000)),
            "bytes_out": int(rng.integers(2000, 250000)),
            "bytes_in": int(rng.integers(1000, 150000)),
            "packets": int(rng.integers(100, 4000)),
            "failed_logins": int(rng.integers(1, 15)),
            "unique_ports": int(rng.integers(3, 15)),
            "connection_rate": round(float(rng.uniform(8, 55)), 2),
        }
    return row


def generate_events(n=120, seed=None, scenario="Mixed traffic"):
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    hosts = ["EDGE-01", "AUTH-02", "APP-03", "DB-04", "WORK-05", "FILE-06"]
    now = datetime.now(timezone.utc)
    rows = []
    mapping = {
        "Mixed traffic": None,
        "Port scan": "port_scan",
        "Credential brute force": "brute_force",
        "Data exfiltration": "data_exfiltration",
        "Lateral movement": "lateral_movement",
    }
    forced = mapping.get(scenario)
    for i in range(int(n)):
        if forced:
            chosen = forced if rng.random() < .68 else "normal"
        else:
            chosen = rng.choice(SCENARIOS, p=[.78, .07, .06, .04, .05])
        src = py_rng.choice(hosts)
        dst = py_rng.choice([h for h in hosts if h != src])
        row = _sample_row(rng, chosen, now, i)
        row.update({
            "event_id": f"EVT-{now.strftime('%H%M%S')}-{i:04d}",
            "timestamp": now - timedelta(seconds=int((n-i)*rng.integers(1, 8))),
            "source": src,
            "destination": dst,
            "scenario": chosen,
        })
        rows.append(row)
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def _fit_baseline(seed=7):
    rng = np.random.default_rng(seed)
    rows = [_sample_row(rng, "normal", None, i) for i in range(800)]
    baseline = pd.DataFrame(rows)[FEATURES]
    model = IsolationForest(n_estimators=120, contamination=0.08, random_state=seed)
    model.fit(baseline)
    return model


_MODEL = None


def detect_events(events: pd.DataFrame) -> pd.DataFrame:
    global _MODEL
    result = events.copy()
    if result.empty:
        result["anomaly_score"] = []
        result["is_anomaly"] = []
        result["risk_score"] = []
        result["reason"] = []
        return result
    if _MODEL is None:
        _MODEL = _fit_baseline()
    x = result[FEATURES].astype(float)
    raw = _MODEL.decision_function(x)
    # Lower Isolation Forest decision_function values are more abnormal.
    lo, hi = float(np.min(raw)), float(np.max(raw))
    normalized = (raw - lo) / (hi - lo + 1e-9)
    anomaly_strength = 1.0 - normalized
    result["anomaly_score"] = np.round(anomaly_strength, 3)
    result["is_anomaly"] = _MODEL.predict(x) == -1

    risks, reasons = [], []
    for i, row in result.iterrows():
        points, why = 0, []
        if row["scenario"] == "port_scan" or row["unique_ports"] >= 20:
            points += 35; why.append("high port diversity")
        if row["failed_logins"] >= 8:
            points += 35; why.append("repeated authentication failures")
        if row["bytes_out"] >= 1_000_000 and row["bytes_out"] > row["bytes_in"] * 8:
            points += 45; why.append("unusually high outbound transfer")
        if row["scenario"] == "lateral_movement":
            points += 25; why.append("lateral-movement scenario")
        if row["connection_rate"] >= 30:
            points += 15; why.append("high connection rate")
        points += int(float(row["anomaly_score"]) * 25)
        if bool(row["is_anomaly"]):
            points += 10
        risks.append(min(100, points))
        reasons.append("; ".join(why) if why else ("model flagged unusual telemetry" if row["is_anomaly"] else "no strong indicator"))
    result["risk_score"] = risks
    result["reason"] = reasons
    return result


def recommend_response(event):
    score = int(event.get("risk_score", 0))
    scenario = str(event.get("scenario", "unknown"))
    if score >= 85:
        action = "Escalate to incident responder; review temporary isolation"
    elif scenario == "brute_force":
        action = "Review authentication logs; consider rate limiting and MFA checks"
    elif scenario == "port_scan":
        action = "Inspect source host and review firewall telemetry"
    elif scenario == "data_exfiltration":
        action = "Validate outbound transfer with data owner; preserve relevant logs"
    elif scenario == "lateral_movement":
        action = "Review identity events and east-west connections"
    elif score >= 60:
        action = "Queue for analyst triage and gather additional telemetry"
    else:
        action = "Continue monitoring; no containment suggested"
    return {
        "action": action,
        "reason": f"Risk score {score}/100; scenario={scenario}; indicators={event.get('reason', 'not available')}. Human approval is required."
    }


def summarize_world(events):
    if events.empty:
        return {"events": 0, "anomalies": 0, "critical": 0}
    return {
        "events": int(len(events)),
        "anomalies": int(events["is_anomaly"].sum()),
        "critical": int((events["risk_score"] >= 80).sum()),
    }


def evaluate_demo(events):
    """Report metrics only for synthetic scenario labels; not real-world performance."""
    if events.empty:
        return {"note": "No events available."}
    known_attack = events["scenario"] != "normal"
    predicted = events["risk_score"] >= 60
    tp = int((known_attack & predicted).sum())
    fp = int((~known_attack & predicted).sum())
    fn = int((known_attack & ~predicted).sum())
    tn = int((~known_attack & ~predicted).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "evaluation_scope": "Synthetic demo labels only; not a real-world benchmark.",
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "precision": round(precision, 3), "recall": round(recall, 3),
    }


def explain_with_ollama(event, recommendation, base_url="http://localhost:11434", model="qwen3:4b"):
    """Optional local LLM explanation. Detection remains usable without Ollama."""
    prompt = (
        "You are a defensive cybersecurity assistant explaining a simulated alert. "
        "Use only the supplied facts. Do not claim certainty or recommend destructive action. "
        "Give: summary, evidence, uncertainty, safe next checks. This is a simulation.\n\n"
        f"Alert: {dict(event)}\nSuggested response: {recommendation}"
    )
    try:
        response = requests.post(
            base_url.rstrip("/") + "/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=25,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "Ollama returned no message.")
    except requests.RequestException as exc:
        return (
            "Optional LLM unavailable. Start Ollama, pull the selected model, and try again. "
            f"Technical detail: {exc}"
        )
    except (ValueError, AttributeError):
        return "Ollama returned an unexpected response. Core detection is still available."
