from pathlib import Path


def test_all_examples_compile():
    examples = Path(__file__).resolve().parents[1] / "examples"
    python_files = sorted(examples.rglob("*.py"))
    assert python_files, "No example programs found"

    for path in python_files:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
