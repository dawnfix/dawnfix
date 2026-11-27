"""dawnfix run report: the Enterprise POSTs, skipped quietly with the standard line."""
import json

from dawnfix_core.run.context import detect
from dawnfix_core.run.report import NEED_KEY, run_report

from .run_fakes import ENTERPRISE, FakeHttp

CTX = detect({"CIRCLECI": "true", "CIRCLE_REPOSITORY_URL": "git@github.com:octo/shop-api.git", "CIRCLE_BUILD_NUM": "77"})


def test_without_a_key_the_enterprise_line_and_nothing_sent(tmp_path, capsys):
    (tmp_path / "ingest.json").write_text("{}")
    http = FakeHttp()
    assert run_report(env={}, ctx=CTX, http=http, ingest=tmp_path / "ingest.json") == 0
    assert capsys.readouterr().err == NEED_KEY["ingest"] + "\n" and http.calls == []
    assert NEED_KEY["prs"].startswith("Hosted PR tracking needs an Enterprise key. Contact ")


def test_ingest_and_opened_prs(tmp_path, capsys):
    (tmp_path / "ingest.json").write_text('{"schema":"dawnfix.ingest/1"}')
    (tmp_path / "opened.json").write_text(json.dumps({"opened": [{"fingerprint": "1997f26556fdd1c5", "url": "u"}]}))
    http = FakeHttp({("POST", "/v1/ingest"): (201, {}), ("POST", "/v1/prs"): (200, {})})
    assert run_report(env={"DAWNFIX_ENTERPRISE_KEY": ENTERPRISE}, ctx=CTX, http=http, ingest=tmp_path / "ingest.json",
                      opened=tmp_path / "opened.json") == 0
    err = capsys.readouterr().err
    assert "tick recorded" in err and "PR state open recorded" in err and ENTERPRISE not in err
    ingest, prs = http.calls
    assert ingest["url"] == "https://dawnfix.dev/v1/ingest" and ingest["body"] == b'{"schema":"dawnfix.ingest/1"}'
    assert ingest["headers"]["Authorization"] == f"Bearer {ENTERPRISE}"
    assert ingest["headers"]["X-Dawnfix-Repo"] == "octo/shop-api" and ingest["headers"]["X-Dawnfix-Run"] == "77"
    assert json.loads(prs["body"]) == {"fingerprint": "1997f26556fdd1c5", "pr_url": "u", "state": "open"}


def test_pr_state_refused_key_and_http_base(capsys):
    http = FakeHttp({("POST", "/v1/prs"): (403, {})})
    env = {"DAWNFIX_ENTERPRISE_KEY": ENTERPRISE}
    assert run_report(env=env, ctx=CTX, http=http, pr_state="merged", branch="dawnfix/1997f26556fdd1c5", pr_url="u") == 0
    assert json.loads(http.calls[0]["body"])["state"] == "merged" and NEED_KEY["prs"] in capsys.readouterr().err
    assert run_report(env=env, ctx=CTX, http=FakeHttp(), pr_state="closed", branch="dawnfix/setup") == 0
    assert "not a dawnfix fix branch" in capsys.readouterr().err
    http = FakeHttp()
    assert run_report(env={**env, "DAWNFIX_INGEST_URL": "http://x"}, ctx=CTX, http=http, pr_state="closed",
                      branch="dawnfix/1997f26556fdd1c5") == 0
    assert http.calls == [] and "https" in capsys.readouterr().err
    assert run_report(env={"DAWNFIX_ENTERPRISE_KEY": "bad key!"}, ctx=CTX, http=http, pr_state="closed") == 0
    assert http.calls == []
