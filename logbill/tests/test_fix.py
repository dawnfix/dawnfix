import io
import json

import pytest
from dawnfix_core.sources.aws import ReadOnlyViolation

from logbill import cli
from logbill.awsread import WRITE_OPERATIONS
from logbill.fix import apply, command, confirm_apply, targets_from_report
from tests.scenario import GROUPS


class Tty(io.StringIO):
    def isatty(self):
        return True


def _no_aws(*a, **k):
    pytest.fail("no AWS client may be built")


def test_fix_from_report_prints_commands_and_touches_no_aws(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "_session", _no_aws)
    monkeypatch.setattr(cli, "make_client", _no_aws)
    rp = tmp_path / "r.json"
    rp.write_text(json.dumps({"groups": [
        {"name": "/ecs/api prod", "region": "eu-central-1", "never_expires": True},
        {"name": "/kept", "region": "eu-central-1", "never_expires": False}]}))
    assert cli.main(["fix", "--retention-days", "30", "--report", str(rp)]) == 0
    out = capsys.readouterr().out
    assert ("aws logs put-retention-policy --region eu-central-1 --log-group-name '/ecs/api prod' "
            "--retention-in-days 30") in out
    assert "/kept" not in out


def test_fix_live_without_apply_only_reads(factory, capsys, monkeypatch):
    monkeypatch.setattr(cli, "_session", lambda profile: object())
    monkeypatch.setattr(cli, "_factory", lambda session: factory)
    monkeypatch.setattr(cli, "make_client", _no_aws)  # the write path builds its client here
    factory.stub("logs").add_response("describe_log_groups", {"logGroups": GROUPS})
    assert cli.main(["fix", "--retention-days", "90", "--regions", "us-east-1"]) == 0
    assert factory.ops == ["DescribeLogGroups"]
    assert "PutRetentionPolicy" not in factory.ops
    out = capsys.readouterr().out
    assert out.count("put-retention-policy") == 1 and "/ecs/api-prod" in out


def test_apply_without_a_terminal_changes_nothing(factory, capsys, monkeypatch):
    monkeypatch.setattr(cli, "_session", lambda profile: object())
    monkeypatch.setattr(cli, "_factory", lambda session: factory)
    monkeypatch.setattr(cli, "make_client", _no_aws)
    monkeypatch.setattr("sys.stdin", io.StringIO("apply 1\n"))  # piped, not typed
    factory.stub("logs").add_response("describe_log_groups", {"logGroups": GROUPS})
    assert cli.main(["fix", "--regions", "us-east-1", "--apply"]) == 1
    assert factory.ops == ["DescribeLogGroups"]


def test_confirmation_must_be_typed_exactly():
    assert confirm_apply(2, 30, stdin=Tty("apply 2\n"), stdout=io.StringIO()) is True
    assert confirm_apply(2, 30, stdin=Tty("yes\n"), stdout=io.StringIO()) is False
    assert confirm_apply(2, 30, stdin=Tty("apply 3\n"), stdout=io.StringIO()) is False


def test_apply_uses_a_client_that_can_only_put_retention(factory):
    def make_write(region, allowed):
        assert allowed == WRITE_OPERATIONS
        return factory("logs", region, allowed)

    factory.stub("logs", allowed=WRITE_OPERATIONS).add_response(
        "put_retention_policy", {}, {"logGroupName": "/a", "retentionInDays": 30})
    res = apply(make_write, [("us-east-1", "/a")], 30)
    assert res == [{"region": "us-east-1", "group": "/a", "ok": True}]
    w = factory("logs", "us-east-1", WRITE_OPERATIONS)
    factory.stub("logs", allowed=WRITE_OPERATIONS).add_response("delete_log_group", {})
    with pytest.raises(ReadOnlyViolation):
        w.delete_log_group(logGroupName="/a")


def test_command_quotes_and_profile():
    assert command("us-east-1", "a;rm -rf /", 30, "prod") == \
        "aws logs put-retention-policy --region us-east-1 --log-group-name 'a;rm -rf /' --retention-in-days 30 --profile prod"
    assert targets_from_report({"groups": [{"name": "x", "region": "r", "never_expires": True}]}, {"y"}) == []


def test_bad_retention_value_is_rejected(capsys):
    assert cli.main(["fix", "--retention-days", "31", "--report", "x.json"]) == 2
