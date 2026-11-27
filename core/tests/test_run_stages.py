"""Each stage holds only its own secret: the agent stage refuses a host token, the publish stage
refuses the AI key, and so on; the AI settings and their one-release fallbacks."""
import pytest

from dawnfix_core.run import stages
from dawnfix_core.run.cli import main
from dawnfix_core.run.stages import StageError, ai_settings, check_stage_env

from .run_fakes import AI_KEY, ENTERPRISE, HOST_TOKEN

OLD_KEY = "ANTHROPIC_API_KEY"  # the deprecated fallback name, under test


@pytest.mark.parametrize("name", stages.HOST_TOKENS)
def test_agent_refuses_any_host_token(name):
    with pytest.raises(StageError, match="must not hold a repo host token"):
        check_stage_env("agent", {"DAWNFIX_AI_API_KEY": AI_KEY, name: HOST_TOKEN})


@pytest.mark.parametrize("name", ["AWS_SESSION_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "CIRCLE_OIDC_TOKEN_V2",
                                  "BITBUCKET_STEP_OIDC_TOKEN", "DAWNFIX_ENTERPRISE_KEY"])
def test_agent_refuses_cloud_credentials_oidc_and_the_enterprise_key(name):
    with pytest.raises(StageError):
        check_stage_env("agent", {"DAWNFIX_AI_API_KEY": AI_KEY, name: "x"})


@pytest.mark.parametrize("name", ["DAWNFIX_AI_API_KEY", OLD_KEY])
def test_publish_refuses_the_ai_key_under_either_name(name):
    with pytest.raises(StageError, match="must not hold the AI API key"):
        check_stage_env("publish", {"DAWNFIX_HOST_TOKEN": HOST_TOKEN, name: AI_KEY})


def test_the_matrix():
    ok = {
        "read": {"AWS_SESSION_TOKEN": "x", "ACTIONS_ID_TOKEN_REQUEST_URL": "x", "CI_JOB_TOKEN": "x"},
        "agent": {"DAWNFIX_AI_API_KEY": AI_KEY, "CI_JOB_TOKEN": "x"},
        "publish": {"DAWNFIX_HOST_TOKEN": HOST_TOKEN, "CI_JOB_TOKEN": "x"},
        "report": {"DAWNFIX_ENTERPRISE_KEY": ENTERPRISE, "CI_JOB_TOKEN": "x"},
    }
    for stage, env in ok.items():
        check_stage_env(stage, env)
    for stage, bad in {"read": "DAWNFIX_AI_API_KEY", "read ": "DAWNFIX_HOST_TOKEN", "report": "DAWNFIX_HOST_TOKEN",
                       "report ": OLD_KEY, "publish": "AWS_ACCESS_KEY_ID"}.items():
        with pytest.raises(StageError):
            check_stage_env(stage.strip(), {bad: "x"})


def test_ai_settings_defaults_and_fallbacks(capsys):
    assert ai_settings({"DAWNFIX_AI_API_KEY": AI_KEY}) == {"provider": "claude", "model": "sonnet", "key": AI_KEY}
    assert capsys.readouterr().err == ""
    s = ai_settings({OLD_KEY: AI_KEY, "DAWNFIX_MODEL": "opus"})
    assert s["key"] == AI_KEY and s["model"] == "opus"
    err = capsys.readouterr().err
    assert err.count("deprecated") == 2 and "DAWNFIX_AI_API_KEY" in err and "DAWNFIX_AI_MODEL" in err
    s = ai_settings({"DAWNFIX_AI_API_KEY": "new", OLD_KEY: "old", "DAWNFIX_AI_MODEL": "haiku", "DAWNFIX_MODEL": "opus"})
    assert (s["key"], s["model"]) == ("new", "haiku") and capsys.readouterr().err == ""


@pytest.mark.parametrize("env, msg", [
    ({}, "no AI API key"),
    ({"DAWNFIX_AI_API_KEY": "k", "DAWNFIX_AI_PROVIDER": "openai"}, "must be claude"),
    ({"DAWNFIX_AI_API_KEY": "k", "DAWNFIX_AI_MODEL": "x --dangerously-skip-permissions"}, "model name"),
])
def test_ai_settings_refusals(env, msg):
    with pytest.raises(StageError, match=msg):
        ai_settings(env)


def test_the_cli_refuses_before_doing_anything(tmp_path, capsys):
    rc = main(["agent", "--mode", "fix", "--dir", str(tmp_path), "--findings", str(tmp_path / "f.json"),
               "--out", str(tmp_path / "out")], env={"DAWNFIX_AI_API_KEY": AI_KEY, "GITHUB_TOKEN": HOST_TOKEN})
    err = capsys.readouterr().err
    assert rc == 2 and "the agent stage must not hold a repo host token (GITHUB_TOKEN)" in err
    assert HOST_TOKEN not in err and AI_KEY not in err and not (tmp_path / "out").exists()
    rc = main(["publish", "--artifact", str(tmp_path), "--findings", str(tmp_path / "f.json")],
              env={"DAWNFIX_HOST_TOKEN": HOST_TOKEN, OLD_KEY: AI_KEY})
    assert rc == 2 and "the publish stage must not hold the AI API key" in capsys.readouterr().err
    rc = main(["publish", "--artifact", str(tmp_path), "--findings", str(tmp_path / "f.json")], env={})
    assert rc == 2 and "no repo host token" in capsys.readouterr().err
