import io

import pytest
import yaml

from dawnfix_parity.cli import EXIT_AWS, EXIT_CONFIG, EXIT_DRIFT, EXIT_GUARD, EXIT_OK, run
from tests.conftest import NOW


def cli(world, config_file, *args, summary=None):
    out, err = io.StringIO(), io.StringIO()
    argv = ["-c", str(config_file), *args]
    if summary is not None:
        argv += ["--summary", str(summary)]
    code = run(argv, aws_factory=world.factory, now=NOW, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_check_exits_1_on_drift_and_writes_summary(world, config_file, tmp_path):
    world.queue_env("dev")
    world.queue_env("prod")
    summary = tmp_path / "summary.md"
    summary.write_text("earlier step\n")
    code, out, err = cli(world, config_file, "check", "--left", "dev", "--right", "prod", summary=summary)
    assert code == EXIT_DRIFT, err
    md = summary.read_text()
    assert md.startswith("earlier step\n")          # appended, not overwritten
    assert "## Dawnfix Parity: `dev` vs `prod`" in md
    assert "| FAIL | type mismatch | `ssm:API_KEY` |" in md
    assert "PLANTED" not in md + out + err
    assert "finding(s) fail the check" in out


def test_check_passes_when_only_allowed_or_not_failing(world, config_file):
    world.queue_env("dev")
    world.queue_env("prod")
    code, out, _ = cli(world, config_file, "check", "--left", "dev", "--right", "prod",
                       "--fail-on", "value_shared")
    assert code == EXIT_OK and "check: pass" in out


def test_check_can_fail_on_inventory_flags(world, config_file):
    world.queue_env("dev")
    world.queue_env("prod")
    code, _, err = cli(world, config_file, "check", "--left", "dev", "--right", "prod",
                       "--fail-on", "rotation_overdue")
    assert code == EXIT_DRIFT and "prod shop/prod/stripe: rotation_overdue" in err


def test_diff_exits_0_even_with_drift(world, config_file):
    world.queue_env("dev")
    world.queue_env("prod")
    code, out, _ = cli(world, config_file, "diff", "--left", "dev", "--right", "prod")
    assert code == EXIT_OK and "missing in prod:" in out


@pytest.mark.parametrize("args, msg", [
    (["check", "--left", "dev", "--right", "dev"], "must differ"),
    (["check", "--left", "dev", "--right", "staging"], "unknown environment"),
    (["check", "--left", "dev", "--right", "prod", "--fail-on", "nope"], "unknown nope"),
])
def test_usage_errors_exit_2(world, config_file, args, msg):
    code, _, err = cli(world, config_file, *args)
    assert code == EXIT_CONFIG and msg in err


def test_missing_config_and_bad_args(world, tmp_path):
    code, _, err = cli(world, tmp_path / "nope.yml", "validate")
    assert code == EXIT_CONFIG and "config not found" in err
    assert run(["frobnicate"], err=io.StringIO(), out=io.StringIO()) == EXIT_CONFIG


def test_validate(world, config_file):
    code, out, _ = cli(world, config_file, "validate")
    assert code == EXIT_OK and "ok (dev, prod)" in out


def test_aws_error_exits_3_without_message(world, config_file):
    world.stub("dev", "ssm").add_client_error("describe_parameters", "AccessDeniedException",
                                              "User arn:aws:iam::1:user/x is not authorized SECRET-ECHO")
    code, out, err = cli(world, config_file, "diff", "--left", "dev", "--right", "prod")
    assert code == EXIT_AWS
    assert "ssm:DescribeParameters: AccessDeniedException" in err and "SECRET-ECHO" not in err


def test_expired_token_hint(world, config_file):
    world.stub("dev", "ssm").add_client_error("describe_parameters", "ExpiredTokenException")
    code, _, err = cli(world, config_file, "inventory")
    assert code == EXIT_AWS and "aws sso login" in err


def test_read_only_violation_exits_4(world, config_file, monkeypatch):
    import dawnfix_parity.collect as collect

    def evil(env, aws, hasher=None):
        aws.client("ssm").put_parameter(Name="/x", Value="y", Type="String")

    monkeypatch.setattr(collect, "collect_stores", evil)
    world.stub("dev", "ssm")
    code, _, err = cli(world, config_file, "diff", "--left", "dev", "--right", "prod")
    assert code == EXIT_GUARD and "refused AWS call PutParameter" in err
