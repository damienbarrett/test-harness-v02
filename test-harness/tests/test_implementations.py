from harness.implementations import SKIP_DIRS, discover_implementations


def test_no_implementations_found(tmp_path):
    assert discover_implementations(tmp_path) == []


def test_skips_known_non_language_dirs(tmp_path):
    for name in SKIP_DIRS:
        (tmp_path / name / "component").mkdir(parents=True)
    assert discover_implementations(tmp_path) == []


def test_discovers_language_dirs_with_component_subdir(tmp_path):
    (tmp_path / "python" / "component").mkdir(parents=True)
    (tmp_path / "rust" / "component").mkdir(parents=True)
    assert discover_implementations(tmp_path) == ["python", "rust"]


def test_ignores_top_level_files_and_dirs_without_component(tmp_path):
    (tmp_path / "README.md").write_text("x")
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "javascript" / "component").mkdir(parents=True)
    assert discover_implementations(tmp_path) == ["javascript"]
