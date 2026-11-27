import json
from pathlib import Path

from dawnfix_fleet.cli import main

from .conftest import FIXTURE_PATH

EXAMPLE = str(Path(__file__).resolve().parents[1] / "examples" / "fleet.yml")


def test_validate(capsys):
    assert main(["validate", "--config", EXAMPLE]) == 0
    assert capsys.readouterr().out.strip() == "ok: 2 clients, 3 accounts"


def test_validate_bad_config_exits_2(tmp_path, capsys):
    p = tmp_path / "fleet.yml"
    p.write_text("version: 1\nclients: {}\n")
    assert main(["validate", "--config", str(p)]) == 2
    assert "config" in capsys.readouterr().err


def test_check_a_summary(tmp_path):
    assert main(["check", str(FIXTURE_PATH)]) == 0
    bad = tmp_path / "s.json"
    doc = json.loads(FIXTURE_PATH.read_text())
    doc["accounts"][0]["env"] = "Somebody's prod"
    bad.write_text(json.dumps(doc))
    assert main(["check", str(bad)]) == 2


def test_collect_for_an_unknown_client_exits_2_without_calling_aws(capsys):
    assert main(["collect", "--client", "nosuchslug", "--config", EXAMPLE]) == 2


def test_bad_arguments_exit_2():
    assert main(["collect"]) == 2
    assert main(["frobnicate"]) == 2
