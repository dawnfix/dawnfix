"""Brand, org and URL strings live in brand.py only (inside src/)."""
from pathlib import Path

from dawnfix_parity import brand

SRC = Path(__file__).resolve().parent.parent / "src" / "dawnfix_parity"
# Files outside src/ that repeat brand strings because they cannot import Python.
NON_PYTHON_COPIES = ["action.yml", "examples/workflow.yml", "README.md"]


def test_brand_strings_only_in_brand_module():
    needles = [brand.PRODUCT_NAME, brand.ORG_NAME, brand.DOCS_URL, f"github.com/{brand.GITHUB_ORG}", "Dawnfix"]
    # Lowercase "dawnfix" is allowed: the schema id dawnfix.parity/1 and the dawnfix_core package.
    for f in SRC.glob("*.py"):
        if f.name in ("brand.py", "__init__.py"):
            continue
        text = f.read_text()
        for n in needles:
            assert n not in text, f"{f.name} hard-codes {n!r}; import it from brand.py"


def test_non_python_copies_exist():
    root = SRC.parent.parent
    for rel in NON_PYTHON_COPIES:
        assert (root / rel).is_file(), rel
