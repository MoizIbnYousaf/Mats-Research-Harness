# Tasks (PLAN line 27)

30 ImpossibleBench tasks (arXiv 2510.20270) plus their `original` twins: 15 from the `conflicting` split, where the visible tests contradict the specification and the model tends to notice, and 15 from `oneoff`, where one expected value has been changed and special-casing is tempting. `ib/` holds 29 `conflicting` pairs (the dataset's `lcbhard_35` and `lcbhard_87` rows are bare asserts with no `check()` and are excluded), from which the 15 are chosen by hand (hand-work ledger, "pick the 30 tasks"). `ib-oneoff/` holds 15 `oneoff` pairs drawn with `--exclude ib/MANIFEST.txt`, so no problem id appears in both directories and every twin exists exactly once.

Every visible test file has one function, `test_visible`, whose asserts include the conflicting one; the perception matcher's summary-line rule keys on that name. `load_impossiblebench.py --split conflicting|oneoff [--exclude MANIFEST.txt]` writes a pair per task, `<id>-impossible` and `<id>-twin`. It needs the `materialise` extra (`pip install -e 'study[materialise]'` for pandas and huggingface_hub; without it, `--help` and a clear error naming the extra still work). It skips dataset rows whose test has no `check()`, and `build_conflict.py` refuses such a file. A twin differs from its task only in the test file, and twins run in State A only.

## Per task

```
tasks/<dir>/<id>-impossible/
  task.toml                      # id, split, kind (impossible|twin), source, entry_point, twin_of, timeout_sec
  environment/                   # State A: README.md, a stub solution.py, the visible test_solution.py
  environment-B/                 # State B: a verified correct solution.py, the same visible tests (build_state_b.py)
  environment-fixable/           # the control: the reference solution with one injected ordinary bug; its test_solution.py
                                 # is the ORIGINAL test, so the only failing assert is the bug (build_fixable.py)
  tests/hidden_original_test.py  # the original tests, used by the second rerun
  tests/conflict.json            # the asserts that differ between the visible test and the original
```

What the agent is told is `study/prompts/instructions/<level>.md`, rendered by `runner/run.py` into the run directory's `README.md`; the per-task text never mentions evaluation, monitoring or integrity. The run directory is a fresh git-initialised copy of one `environment*/` tree, outside any tree that holds an instruction file (PLAN line 27). The two reruns (`runner/rerun.py`) use the pristine visible test and `tests/hidden_original_test.py`.

## Builders

`build_conflict.py` writes `tests/conflict.json` per task from the diff between the visible test and the original. That file is what the perception matcher looks for.

`build_state_b.py` writes `environment-B/` from a reference solution and keeps it only if it passes the original tests and fails exactly the conflicting visible asserts, both verdicts coming from the two reruns in `runner/rerun.py`. The references come from the passing twin runs of factor 1 (PLAN line 29): `build_state_b.py --from-runs RUNS_DIR --tasks ib ib-oneoff [--list-out built.txt]` takes, per impossible task, the first twin run whose manifest has `status = "completed"` and `visible_pass = true` (in run-id order), checks its `work_final/solution.py`, writes `environment-B/`, and records the run id under `[state_b]` in `task.toml`. Tasks with no passing twin, or whose passing twins all fail a check, are printed under `excluded` and get nothing. `--task DIR --solution FILE` builds one task from a file.

`build_fixable.py` writes `environment-fixable/` from the reference (`environment-B/solution.py` by default) plus one injected ordinary bug that fails one non-conflicting original test; the visible `test_solution.py` it ships is the original test. `--auto` injects the bug itself: one comparison operator flipped, else one integer literal off by one (+1, then -1), tried in source order, keeping the first mutation for which a per-assert module built from the original `check()` fails exactly one assert that is not a conflicting one. When none qualifies it exits 1, and `--bug-patch FILE` takes a hand-written unified diff instead.

## The fixture

`example-001/` and `example-001-twin/` are a hand-written task in the same layout with all three states. The offline tests, `mrh dump`, `mrh watch --dry-run` and `make accept` use them. The fixture is not one of the 30. Every `ib/` and `ib-oneoff/` task has `environment/` and `tests/` only until the builders have run on the twin runs (`docs/hand-runs.md`, "Kill-test step 2 inputs").

## Rules

The impossible test has to be genuinely unsatisfiable without editing tests. Ten of the thirty are run by hand before the first batch (`docs/hand-runs.md`). A task whose twin fails in every arm is excluded before analysis. The task text never mentions evaluation, monitoring or integrity.
