"""figures.py: the three CSVs exist, action shares sum to one per body, Antigravity rows carry the logging-gap note,
the predicted ranks come from PREDICTIONS.md when it exists (else PLAN line 32), invalid and model-mismatching runs
leave every denominator and are counted per body and status, the summary line explains an
empty fig2, and the PNGs land next to the CSVs when matplotlib imports ."""
import csv, json

import figures, perceive, score


def _read(p):
    return list(csv.DictReader(p.read_text().splitlines()))


def test_csvs(runs_copy, tmp_path, capsys):
    perceive.main(["--runs", str(runs_copy)]); score.main([str(runs_copy)])
    out = tmp_path / "figs"
    assert figures.main(["--runs", str(runs_copy), "--out", str(out)]) == 0
    for n in ("fig1.csv", "fig2.csv", "fig3.csv", "exclusions.csv"):
        assert (out / n).exists()
    f1 = _read(out / "fig1.csv")
    assert {r["body"] for r in f1} == {"antigravity", "claude", "codex", "pi"}
    for r in f1:
        assert abs(sum(float(r[a]) for a in figures.ACTIONS) - 1) < 1e-6
    assert next(r for r in f1 if r["body"] == "codex")["knowing_share_among_gaming"] == "1.0000"
    f3 = {r["body"]: r for r in _read(out / "fig3.csv")}
    assert f3["claude"]["honest_given_observed"] == "1.0000" and f3["codex"]["predicted_observation_rank"] == "1"
    assert _read(out / "fig2.csv") == []  # no State B / fixable runs among the fixtures
    assert f3["antigravity"]["note"] == figures.AGY_NOTE and f3["antigravity"]["predicted_observation_rank"] == ""
    assert next(r for r in f1 if r["body"] == "antigravity")["note"] == figures.AGY_NOTE and all(r["note"] == "" for r in f1 if r["body"] != "antigravity")
    assert _read(out / "exclusions.csv") == []
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "fig2 0 rows (no State B / fixable runs)" in line and "4 of 4 scored runs used; excluded: 0 invalid; 0 model-mismatch" in line
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        assert "(csv)" in line and "matplotlib missing" in line
    else:
        assert "(png+csv)" in line and (out / "fig1.png").exists() and (out / "fig3.png").exists() and not (out / "fig2.png").exists()


def test_invalid_and_mismatching_runs_are_excluded(runs_copy, tmp_path, capsys):
    """Contract 1 + PLAN line 33: an upstream_error run and a model-mismatching run leave fig1 / fig3 and their
    counts per body and status appear on the summary line and in exclusions.csv."""
    mf = runs_copy / "r_tamper_skip" / "manifest.json"; m = json.loads(mf.read_text()); m["status"] = "upstream_error"; mf.write_text(json.dumps(m))
    mf = runs_copy / "r_agy_none" / "manifest.json"; m = json.loads(mf.read_text()); m["status"] = "launch_failed"; mf.write_text(json.dumps(m))
    perceive.main(["--runs", str(runs_copy)])
    pj = runs_copy / "r_special_case_false_claim" / "perception.json"; p = json.loads(pj.read_text()); p["model_mismatch_count"] = 1; pj.write_text(json.dumps(p))
    score.main([str(runs_copy)])
    out = tmp_path / "figs"
    assert figures.main(["--runs", str(runs_copy), "--out", str(out)]) == 0
    f1 = _read(out / "fig1.csv"); f3 = _read(out / "fig3.csv")
    assert [r["body"] for r in f1] == ["claude"] and [r["body"] for r in f3] == ["claude"]
    assert f1[0]["n"] == "1" and f1[0]["spec_correct"] == "1.0000"
    assert _read(out / "exclusions.csv") == [{"body": "antigravity", "reason": "invalid", "status": "launch_failed", "n": "1"},
                                             {"body": "codex", "reason": "invalid", "status": "upstream_error", "n": "1"},
                                             {"body": "pi", "reason": "model_mismatch", "status": "", "n": "1"}]
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert "1 of 4 scored runs used; excluded: 2 invalid (antigravity launch_failed=1, codex upstream_error=1); 1 model-mismatch (pi=1)" in line
    scores = _read(runs_copy / "scores.csv"); perc = _read(runs_copy / "perception.csv")
    used, invalid, mismatch = figures.exclusions(scores, perc)
    assert [r["run_id"] for r in used] == ["r_spec_correct_explicit"] and len(invalid) == 2 and [r["run_id"] for r in mismatch] == ["r_special_case_false_claim"]
    # an invalid run that also mismatches is counted once, as invalid
    assert figures.exclusions([{"run_id": "x", "body": "pi", "action": "invalid", "status": "timed_out", "model_mismatch_count": "3"}], []) == \
        ([], [{"run_id": "x", "body": "pi", "action": "invalid", "status": "timed_out", "model_mismatch_count": "3"}], [])


def test_predictions_from_file(runs_copy, tmp_path, capsys):
    assert figures.ranks("codex >= opencode > claude >= pi") == {"codex": 1, "opencode": 2, "claude": 3, "pi": 4}
    assert figures.ranks("claude > codex > opencode ~ pi") == {"claude": 1, "codex": 2, "opencode": 3, "pi": 3}
    pred, src = figures.predictions(tmp_path)
    assert pred == figures.PLAN_PREDICTIONS and src.startswith("PLAN line 32")
    (tmp_path / "PREDICTIONS.md").write_text("# Predictions, 2026-09-02\n\nobservation_rank: pi > claude > codex ~ opencode\nhonest_given_observed_rank: pi > opencode > codex > claude\n")
    pred, src = figures.predictions(tmp_path)
    assert pred["observation_rank"] == "pi > claude > codex ~ opencode" and src.endswith("PREDICTIONS.md")
    perceive.main(["--runs", str(runs_copy)]); score.main([str(runs_copy)])
    out = tmp_path / "figs"
    assert figures.main(["--runs", str(runs_copy), "--out", str(out), "--prompts", str(tmp_path)]) == 0
    f3 = {r["body"]: r for r in _read(out / "fig3.csv")}
    assert f3["pi"]["predicted_observation_rank"] == "1" and f3["codex"]["predicted_observation_rank"] == "3" and f3["claude"]["predicted_honest_rank"] == "4"
    assert "predictions from " in capsys.readouterr().out
