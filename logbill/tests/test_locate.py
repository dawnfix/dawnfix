import json

from logbill.cli import main
from logbill.locate import fragments, locate, locate_pattern
from tests.conftest import FIXTURES

REPO = FIXTURES / "repo"


def test_fragments_drop_tokens_levels_and_redactions():
    assert fragments("[DEBUG] cache lookup for order <Number-1> took <Number-2> ms") == ["cache lookup for order"]
    assert fragments("order accepted, sending confirmation to :email") == ["order accepted, sending confirmation to"]
    assert fragments('{"level":30,"queue":"<Token-1>","msg":"polling queue for new messages"}') == \
        ["polling queue for new messages"]
    assert fragments("START RequestId: <UUID-1> Version: $LATEST") == []


def test_locate_finds_python_and_js_lines():
    c = locate_pattern(REPO, "DEBUG cache lookup for order <Number-1> took <Number-2> ms")
    assert c and (c[0].file, c[0].line) == ("src/api/orders.py", 7)
    c = locate_pattern(REPO, '{"level":30,"queue":"<Token-1>","msg":"polling queue for new messages"}')
    assert [(x.file, x.line) for x in c] == [("worker/poll.js", 4)]  # node_modules is skipped
    c = locate_pattern(REPO, "heartbeat from worker <Number-1> still alive")
    assert c[0].file == "worker/poll.js" and c[0].line == 6


def test_locate_cli_reads_the_report(tmp_path, capsys):
    report = {"groups": [{"name": "/ecs/api", "region": "us-east-1", "patterns": [
        {"id": "a1", "text": "DEBUG cache lookup for order <Number-1> took <Number-2> ms", "monthly_usd": 9.0},
        {"id": "b2", "text": "nothing like this exists anywhere", "monthly_usd": 1.0}]}]}
    rp = tmp_path / "r.json"
    rp.write_text(json.dumps(report))
    res = locate(REPO, rp)
    assert [p["id"] for p in res] == ["a1", "b2"]
    assert res[0]["candidates"][0]["file"] == "src/api/orders.py" and not res[1]["candidates"]
    assert main(["locate", "--repo", str(REPO), "--report", str(rp)]) == 0
    out = capsys.readouterr().out
    assert "src/api/orders.py:7:" in out and "no source line found" in out


def test_fragment_starting_with_a_dash_is_not_a_flag(tmp_path):
    (tmp_path / "a.txt").write_text("--version flag was printed here\n")
    c = locate_pattern(tmp_path, "--version flag was printed here")
    assert c and c[0].file == "a.txt"
