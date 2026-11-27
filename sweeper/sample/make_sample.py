"""Build the sample teardown plan shown on the hosted /sweeper/sample page, from the tests'
synthetic worlds (tests/test_scan.py: a Beanstalk stack replaced on 2026-09-01;
tests/test_leftovers.py: a stopped instance, an idle NAT gateway, a classic ELB, idle RDS),
account 123456789012, every AWS call answered by botocore's Stubber. No credentials, no network.

    .venv/bin/python sample/make_sample.py          # rewrite sample/sample.json
    .venv/bin/python sample/make_sample.py --check  # exit 1 if it is out of date

tests/test_sample.py runs --check. The Worker imports sample.json at build time
(worker/src/render/sweeper.ts).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from dawnfix_sweeper import plan as pl  # noqa: E402
from dawnfix_sweeper.guard import make_client  # noqa: E402
from dawnfix_sweeper.pricing import Prices  # noqa: E402
from dawnfix_sweeper.scan import Scanner  # noqa: E402
from tests import test_leftovers, test_scan  # noqa: E402
from tests.conftest import SERVICES  # noqa: E402

JSON = HERE / "sample.json"
NOTE = "Synthetic: the test suite's made-up account 123456789012 and example.com zone. No real account."
R = "us-east-1"


def _scan(world):
    session = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name=R)
    clients, stubs = {}, {}
    for s in SERVICES:
        clients[(s, R)] = make_client(session, s, R)
        stubs[s] = Stubber(clients[(s, R)])
    world(stubs)
    for st in stubs.values():
        st.activate()
    try:
        return Scanner(session, [R], test_scan.BEFORE, {}, Prices.load(), None, clients=clients,
                       now=test_leftovers.NOW).run()
    finally:
        for st in stubs.values():
            st.deactivate()


def build() -> dict:
    a, b = _scan(test_scan.world), _scan(test_leftovers.world)
    items = sorted(a["items"] + b["items"], key=lambda i: (i.phase, i.region, i.id))
    result = {"account": a["account"], "items": items, "errors": a["errors"] + b["errors"],
              "notes": sorted(set(a["notes"] + b["notes"]))}
    doc = pl.build(result, before=test_scan.BEFORE, regions=[R], tags={}, prices_meta=Prices.load().meta(),
                   now=test_leftovers.NOW)
    return {"note": NOTE, "plan": doc, "markdown": pl.markdown(doc)}


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
