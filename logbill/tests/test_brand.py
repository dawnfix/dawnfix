import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "logbill"
# Names that must only appear in brand.py (the dawnfix_core import path is a package, not a brand).
BRAND = re.compile(r"(?i)dawnfix(?!_core)|logbill\.report/")


def test_brand_names_live_in_one_module():
    offenders = []
    for f in SRC.glob("*.py"):
        if f.name in ("brand.py", "__init__.py"):
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if BRAND.search(line):
                offenders.append(f"{f.name}:{i}: {line.strip()}")
    assert offenders == []
