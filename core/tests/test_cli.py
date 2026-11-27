import json

from dawnfix_core.cli import main
from tests.conftest import BASE_CONFIG, FakeSource, log_event, validate


def test_exit_codes_and_files(write_config, tmp_path, capsys):
    cfg = write_config()
    state, out = tmp_path / "state.json", tmp_path / "findings.json"
    args = ["tick", "--config", str(cfg), "--state", str(state), "--out", str(out)]
    assert main(args, sources=[FakeSource([log_event()])]) == 10
    validate(json.loads(out.read_text()), "findings.schema.json")
    assert state.exists()
    assert main(args, sources=[FakeSource([log_event()])]) == 0
    assert "0 new" in capsys.readouterr().err


def test_no_findings_exit_zero(write_config, tmp_path):
    args = ["tick", "--config", str(write_config()), "--state", str(tmp_path / "s.json"),
            "--out", str(tmp_path / "f.json")]
    assert main(args, sources=[FakeSource([])]) == 0


def test_dry_run_prints_ingest_and_writes_nothing(write_config, tmp_path, capsys):
    state, out = tmp_path / "state.json", tmp_path / "findings.json"
    code = main(["tick", "--config", str(write_config()), "--state", str(state), "--out", str(out), "--dry-run"],
                sources=[FakeSource([log_event(message="TypeError for jane@example.com")])])
    assert code == 10
    printed = json.loads(capsys.readouterr().out)
    validate(printed, "ingest.schema.json")
    assert printed["counts"]["new"] == 1 and "jane" not in json.dumps(printed)
    assert not state.exists() and not out.exists()


def test_ingest_out(write_config, tmp_path):
    ing = tmp_path / "ingest.json"
    main(["tick", "--config", str(write_config()), "--state", str(tmp_path / "s.json"),
          "--out", str(tmp_path / "f.json"), "--ingest-out", str(ing)], sources=[FakeSource([log_event()])])
    validate(json.loads(ing.read_text()), "ingest.schema.json")


def test_config_error_exit_2(write_config, tmp_path, capsys):
    cfg = write_config("version: 1\nsources: [{aws: {region: us-east-1}}]\n")
    assert main(["tick", "--config", str(cfg), "--state", str(tmp_path / "s.json")]) == 2
    assert "nothing to watch" in capsys.readouterr().err


def test_bad_window_exit_2(write_config, tmp_path):
    assert main(["tick", "--config", str(write_config()), "--state", str(tmp_path / "s"),
                 "--window-minutes", "0"]) == 2


def test_all_sources_failed_exit_1_and_state_untouched(write_config, tmp_path):
    state = tmp_path / "s.json"
    code = main(["tick", "--config", str(write_config()), "--state", str(state), "--out", str(tmp_path / "f.json")],
                sources=[FakeSource(fail="NoCredentialsError")])
    assert code == 1 and not state.exists()


def test_validate(write_config, capsys):
    assert main(["validate", "--config", str(write_config())]) == 0
    assert "ok" in capsys.readouterr().out


def test_config_json(write_config, capsys):
    cfg = write_config(BASE_CONFIG_WITH_TEST)
    assert main(["config", "--config", str(cfg), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["test"] == {"command": "npm test"}
    assert doc["autonomy"] == "diagnose" and doc["phi_mode"] is False
    assert set(doc["limits"]) >= {"fix_prs_per_day", "max_turns", "timeout_minutes", "max_findings"}
    assert doc["report"]["issues"] == "github"
    assert doc["schedule"] == "17 * * * *"


def test_config_json_without_test_command(write_config, capsys):
    assert main(["config", "--config", str(write_config()), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["test"] == {"command": None}


def test_config_plain(write_config, capsys):
    assert main(["config", "--config", str(write_config(BASE_CONFIG_WITH_TEST))]) == 0
    assert "test.command: npm test" in capsys.readouterr().out


def test_config_error_exit_2_for_config(write_config, capsys):
    cfg = write_config(BASE_CONFIG + "limits: { max_findings: 500 }\n")
    assert main(["config", "--config", str(cfg), "--json"]) == 2
    assert "max_findings" in capsys.readouterr().err


BASE_CONFIG_WITH_TEST = BASE_CONFIG + "test: { command: npm test }\n"
