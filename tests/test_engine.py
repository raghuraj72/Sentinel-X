from sentinel.engine import generate_events, detect_events, recommend_response, evaluate_demo


def test_generator_returns_expected_fields():
    events = generate_events(25, seed=10)
    required = {
        "event_id", "timestamp", "source", "destination", "scenario",
        "duration_ms", "bytes_out", "bytes_in", "packets", "failed_logins",
        "unique_ports", "connection_rate"
    }
    assert required.issubset(set(events.columns))
    assert len(events) == 25


def test_detector_adds_scores():
    events = generate_events(40, seed=11)
    scored = detect_events(events)
    assert scored["risk_score"].between(0, 100).all()
    assert scored["is_anomaly"].isin([True, False]).all()
    assert scored["reason"].notna().all()


def test_response_is_review_only():
    response = recommend_response({"risk_score": 95, "scenario": "port_scan", "reason": "test"})
    assert "Escalate" in response["action"]
    assert "Human approval" in response["reason"]


def test_evaluation_is_scoped_to_demo():
    scored = detect_events(generate_events(30, seed=12))
    report = evaluate_demo(scored)
    assert "Synthetic demo labels only" in report["evaluation_scope"]
    assert 0 <= report["precision"] <= 1
    assert 0 <= report["recall"] <= 1
