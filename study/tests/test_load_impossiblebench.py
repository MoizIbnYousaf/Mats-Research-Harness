"""load_impossiblebench (offline parts): rows without check() are unusable, --exclude reads ids from MANIFEST files,
and every materialised visible test under study/tasks defines check() with no module-level assert."""
import ast
from types import SimpleNamespace

import load_impossiblebench as loader


def test_unusable_rows():
    good = SimpleNamespace(test="def check(candidate):\n    assert candidate(1) == 2\n", original_test="def check(candidate):\n    assert candidate(1) == 1\n")
    bare = SimpleNamespace(test="assert candidate([65], [3], 69) == 0", original_test=good.original_test)  # lcbhard_35 in the conflicting split
    assert loader.unusable(good) is None
    assert loader.unusable(bare) == "test has no def check()"
    assert loader.unusable(SimpleNamespace(test=good.test, original_test="x = 1")) == "original_test has no def check()"


def test_excluded_ids(tmp_path):
    (tmp_path / "MANIFEST.txt").write_text("lcbhard_23-impossible\nlcbhard_23-twin\nlcbhard_8-impossible\nlcbhard_8-twin\n")
    (tmp_path / "other.txt").write_text("lcbhard_2-twin\n")
    assert loader.excluded_ids([str(tmp_path / "MANIFEST.txt"), str(tmp_path / "other.txt")]) == {"lcbhard_23", "lcbhard_8", "lcbhard_2"}
    assert loader.excluded_ids([]) == set()


def test_materialised_tasks_are_well_formed_and_disjoint(study):
    tasks = study / "tasks"; ids = {}
    for split in ("ib", "ib-oneoff"):
        names = (tasks / split / "MANIFEST.txt").read_text().split()
        ids[split] = {n.rsplit("-", 1)[0] for n in names}
        for n in names:
            assert (tasks / split / n / "task.toml").exists(), n
            for f in (tasks / split / n / "environment" / "test_solution.py", tasks / split / n / "tests" / "hidden_original_test.py"):
                tree = ast.parse(f.read_text())
                assert any(isinstance(x, ast.FunctionDef) and x.name == "check" for x in tree.body), f
                assert not any(isinstance(x, ast.Assert) for x in tree.body), f
        assert sorted(d.name for d in (tasks / split).iterdir() if d.is_dir()) == sorted(names)
    assert not ids["ib"] & ids["ib-oneoff"], ids["ib"] & ids["ib-oneoff"]
    assert len(ids["ib-oneoff"]) == 15
