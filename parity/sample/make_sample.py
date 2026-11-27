"""Build the sample output shown on the hosted /parity page, from the tests' synthetic
two-account world (tests/conftest.py: accounts 111111111111 and 222222222222, a made-up
"shop" app, every AWS call answered by botocore's Stubber). No credentials, no network.

    .venv/bin/python sample/make_sample.py          # rewrite sample/sample.json
    .venv/bin/python sample/make_sample.py --check  # exit 1 if it is out of date

tests/test_sample.py runs --check, so a report change that is not regenerated here fails
the tests. The Worker imports sample.json at build time (worker/src/render/parity.ts).
"""
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402

from dawnfix_parity.cli import run  # noqa: E402
from tests.conftest import CONFIG, NOW, PLANTED, REGION, World  # noqa: E402

JSON = HERE / "sample.json"
NOTE = ("Synthetic: the test suite's made-up 'shop' app in two made-up accounts (111111111111, "
        "222222222222). No real account.")


def _world():
    session = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name=REGION)
    return World(session)


def _run(argv, lookups=True):
    w = _world()
    w.queue_env("dev", lookups=lookups)
    w.queue_env("prod", lookups=lookups)
    out, err = io.StringIO(), io.StringIO()
    code = run(argv, aws_factory=w.factory, now=NOW, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def build() -> dict:
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / ".parity.yml"
        cfg.write_text(CONFIG)
        _, diff_text, _ = _run(["-c", str(cfg), "diff", "--left", "dev", "--right", "prod"])
        _, inventory_text, _ = _run(["-c", str(cfg), "inventory"], lookups=False)
        summary, ingest = Path(d) / "summary.md", Path(d) / "ingest.json"
        _run(["-c", str(cfg), "check", "--left", "dev", "--right", "prod", "--inventory",
              "--summary", str(summary), "--ingest-out", str(ingest)])
        doc = {"note": NOTE, "diff_text": diff_text, "inventory_text": inventory_text,
               "summary_markdown": summary.read_text(), "ingest": json.loads(ingest.read_text())}
    text = json.dumps(doc)
    for v in PLANTED.values():
        assert v not in text, "a planted value reached the sample"
    return doc


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    want = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if "--check" in argv:
        if not JSON.is_file() or JSON.read_text() != want:
            print("sample/sample.json is out of date: run sample/make_sample.py", file=sys.stderr)
            return 1
        return 0
    JSON.write_text(want)
    print(f"wrote {JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
