"""Build the sample PR shown on the hosted /leastpriv page, from the tests' synthetic role
(tests/test_leastpriv.py: role app-worker in account 123456789012, every IAM and Access
Analyzer call answered by botocore's Stubber). No credentials, no network.

    .venv/bin/python sample/make_sample.py          # rewrite sample/sample.json
    .venv/bin/python sample/make_sample.py --check  # exit 1 if it is out of date

tests/test_sample.py runs --check. The Worker imports sample.json at build time
(worker/src/render/leastpriv.ts).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from dawnfix_leastpriv import cli  # noqa: E402
from dawnfix_leastpriv.guard import make_client  # noqa: E402
from tests.test_leastpriv import INLINE, NOW, ROLE, add_aa, add_iam  # noqa: E402

JSON = HERE / "sample.json"
NOTE = "Synthetic: the test suite's made-up role app-worker in account 123456789012. No real account."


def build() -> dict:
    session = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    iam, aa = make_client(session, "iam", "us-east-1"), make_client(session, "accessanalyzer", "us-east-1")
    st_iam, st_aa = Stubber(iam), Stubber(aa)
    add_iam(st_iam)
    add_aa(st_aa)
    st_iam.activate()
    st_aa.activate()
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        repo, out = Path(d) / "repo", Path(d) / "out"
        (repo / "iam").mkdir(parents=True)
        (repo / "iam" / "app.json").write_text(json.dumps(INLINE, indent=2) + "\n")
        os.chdir(repo)
        try:
            args = cli.parser().parse_args(["role", ROLE, "--days", "90", "--out", str(out),
                                            "--policy-file", "app=iam/app.json"])
            assert cli.cmd_role(args, iam=iam, aa=aa, sleep=lambda _: None, now=NOW) == 0
        finally:
            os.chdir(cwd)
            st_iam.deactivate()
            st_aa.deactivate()
        return {"note": NOTE, "pr_markdown": (out / "pr.md").read_text(), "patch": (out / "app.patch").read_text(),
                "patch_path": "iam/app.json", "report": json.loads((out / "report.json").read_text())}


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
