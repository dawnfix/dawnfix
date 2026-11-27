"""Build the sample deploy comment shown on the hosted /receipt page, from the tests' synthetic
Cost Explorer series (tests/test_receipt.py: a deploy on 2026-10-20 that tripled NAT Gateway
data processing), answered by botocore's Stubber. No credentials, no network.

    .venv/bin/python sample/make_sample.py          # rewrite sample/sample.json
    .venv/bin/python sample/make_sample.py --check  # exit 1 if it is out of date

tests/test_sample.py runs --check. The Worker imports sample.json at build time
(worker/src/render/receipt.ts).
"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from dawnfix_receipt import cli  # noqa: E402
from dawnfix_receipt.guard import make_client  # noqa: E402
from tests.test_receipt import A, B, FINAL_NOW, args, expected_req, series  # noqa: E402

JSON = HERE / "sample.json"
NOTE = "Synthetic: the test suite's made-up Cost Explorer series for one deploy. No real account."


def _run(now, results, start, end, ingest):
    session = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    ce = make_client(session, "ce")
    st = Stubber(ce)
    if results is not None:
        st.add_response("get_cost_and_usage", {"ResultsByTime": results}, expected_req(start, end))
    st.activate()
    out = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            assert cli.run(args("--ingest-out", str(ingest)), ce=ce, now=now) == 0
    finally:
        st.deactivate()
    return out.getvalue()


def build() -> dict:
    with tempfile.TemporaryDirectory() as d:
        provisional = _run(datetime(2026, 10, 23, 6, tzinfo=timezone.utc), series(B, A[:1]), "2026-10-17",
                           "2026-10-22", Path(d) / "p.json")
        ingest = Path(d) / "f.json"
        final = _run(FINAL_NOW, series(B, A), "2026-10-17", "2026-10-24", ingest)
        return {"note": NOTE, "comment_markdown": final, "provisional_markdown": provisional,
                "ingest": json.loads(ingest.read_text())}


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
