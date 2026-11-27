"""Redaction: no secret value, token in a URL, bearer header or credential shape is printed."""
from dawnfix_core.run.cli import main
from dawnfix_core.run.gitsafe import GitError, git
from dawnfix_core.run.scrub import REDACT, Redactor, say

from .run_fakes import AI_KEY, ENTERPRISE, HOST_TOKEN


def test_values_and_their_url_encoding():
    r = Redactor()
    r.add("hunter2-secret+/=")
    assert r("a hunter2-secret+/= b hunter2-secret%2B%2F%3D c") == "a *** b *** c"
    r.add("")
    r.add("abc")  # too short to be a secret; never blank out common text
    assert r("abc") == "abc"


def test_shapes_urls_and_headers():
    r = Redactor()
    line = (f"push https://x-access-token:{HOST_TOKEN}@github.com/o/r.git; key {AI_KEY}; "
            f"Authorization: Bearer {ENTERPRISE}; aws {'AKIA' + 'Q' * 16}")
    out = r(line)
    for s in (HOST_TOKEN, AI_KEY, ENTERPRISE, "AKIA" + "Q" * 16):
        assert s not in out
    assert "https://***@github.com/o/r.git" in out
    assert r("a token budget of 3") == "a token budget of 3"


def test_say_scrubs_registered_values(capsys):
    REDACT.add("registered-value-1234")
    say("the value is registered-value-1234")
    assert capsys.readouterr().err == "the value is ***\n"


def test_git_errors_never_show_the_push_url_token(tmp_path):
    git("init", "-q", cwd=tmp_path)
    try:
        git("push", f"https://x-access-token:{HOST_TOKEN}@127.0.0.1:9/o/r.git", "HEAD", cwd=tmp_path)
    except GitError as e:
        assert HOST_TOKEN not in str(e)
    else:
        raise AssertionError("push to nowhere succeeded")


def test_every_secret_in_the_environment_is_registered(capsys):
    main(["context"], env={"DAWNFIX_HOST_TOKEN": "my-unusual-host-token", "DAWNFIX_ENTERPRISE_KEY": "my-ent-key-1"})
    capsys.readouterr()
    say("my-unusual-host-token and my-ent-key-1")
    assert capsys.readouterr().err == "*** and ***\n"
