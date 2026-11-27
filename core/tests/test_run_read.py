"""dawnfix run read: the tick for any CI, its artifact and outputs.env."""
import json

from dawnfix_core.run.cli import main
from tests.conftest import FakeSource, log_event

from .run_fakes import AI_KEY


def outputs(d):
    return dict(line.split("=", 1) for line in (d / "outputs.env").read_text().splitlines())


def test_first_run_is_a_baseline_then_new_errors_wake_the_agent(write_config, tmp_path, capsys):
    cfg, state, out = write_config(), tmp_path / "state.json", tmp_path / "out"
    args = ["read", "--config", str(cfg), "--state", str(state), "--out", str(out)]
    assert main(args, env={}, sources=[FakeSource([log_event()])]) == 0
    assert "running as --baseline" in capsys.readouterr().err
    assert outputs(out)["has_new"] == "false" and state.exists()
    assert main(args, env={}, sources=[FakeSource([log_event(message="TypeError: new one")])]) == 0
    o = outputs(out)
    assert o["has_new"] == "true" and o["autonomy"] == "diagnose" and o["issues"] == "github"
    assert json.loads((out / "findings.json").read_text())["summary"]["new"] == 1
    assert (out / "ingest.json").exists() and json.loads((out / "config.json").read_text())["autonomy"] == "diagnose"


def test_read_refuses_the_ai_key_and_a_config_error_is_2(write_config, tmp_path, capsys):
    args = ["read", "--config", str(write_config()), "--state", str(tmp_path / "s"), "--out", str(tmp_path / "o")]
    assert main(args, env={"DAWNFIX_AI_API_KEY": AI_KEY}, sources=[FakeSource([])]) == 2
    assert "read stage must not hold the AI API key" in capsys.readouterr().err
    bad = write_config("version: 1\nsources: [{aws: {region: us-east-1}}]\n")
    assert main(["read", "--config", str(bad), "--state", str(tmp_path / "s"), "--out", str(tmp_path / "o")],
                env={}, sources=[FakeSource([])]) == 2


def test_the_dawnfix_command_dispatches_run(write_config, tmp_path, monkeypatch):
    from dawnfix_core.cli import main as dawnfix
    monkeypatch.setattr("os.environ", {})
    assert dawnfix(["run", "read", "--config", str(write_config()), "--state", str(tmp_path / "s"),
                    "--out", str(tmp_path / "o"), "--baseline"], sources=[FakeSource([])]) == 0


def _fixture(tmp_path):
    f = tmp_path / "fixture.json"
    f.write_text(json.dumps({"schema": "dawnfix.read-fixture/1", "source_id": "aws:us-east-1", "events": [
        {"service": "shop-api", "route": "/users/:id", "method": "GET", "status": 500, "count": 3,
         "message": "TypeError: 'NoneType' object is not subscriptable"}]}))
    return f


def test_the_read_fixture_is_refused_unless_explicitly_allowed(write_config, tmp_path, capsys):
    args = ["read", "--config", str(write_config()), "--state", str(tmp_path / "s"), "--out", str(tmp_path / "o")]
    assert main(args, env={"DAWNFIX_READ_FIXTURE": str(_fixture(tmp_path))}) == 2
    assert "test-only input" in capsys.readouterr().err
    assert not (tmp_path / "o" / "findings.json").exists()


def test_the_read_fixture_yields_a_new_finding_never_a_baseline(write_config, tmp_path, capsys):
    out = tmp_path / "o"
    args = ["read", "--config", str(write_config()), "--state", str(tmp_path / "s"), "--out", str(out)]
    env = {"DAWNFIX_READ_FIXTURE": str(_fixture(tmp_path)), "DAWNFIX_ALLOW_READ_FIXTURE": "1"}
    assert main(args, env=env) == 0
    err = capsys.readouterr().err
    assert "TEST ONLY" in err and "baseline" not in err
    o = outputs(out)
    assert o["has_new"] == "true" and o["fixture"] == "true"
    f = json.loads((out / "findings.json").read_text())["findings"]
    assert len(f) == 1 and f[0]["route"] == "/users/:id" and f[0]["status"] == "new"
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert main(args, env={**env, "DAWNFIX_READ_FIXTURE": str(bad)}) == 2
