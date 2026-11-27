"""No secret in any text sent to the repo host: by value (this stage), by hash (earlier
stages, so publish never holds the AI key), and by credential shape."""
import hashlib
import json

from dawnfix_core.run.context import detect
from dawnfix_core.run.guard import MARK, GuardedHost, TextGuard, hashes_of, load_hashes, secret_values, write_hashes
from dawnfix_core.run.hosts import GitHubAdapter

from .run_fakes import AI_KEY, ENTERPRISE, HOST_TOKEN, FakeHttp

CTX = detect({"DAWNFIX_REPO": "octo/shop-api", "DAWNFIX_REPO_HOST": "github"})


def guarded():
    http = FakeHttp({("POST", "/repos/octo/shop-api/labels"): (201, {}),
                     ("POST", "/repos/octo/shop-api/issues/41/labels"): (200, []),
                     ("POST", "/repos/octo/shop-api/issues/9/comments"): (201, {}),
                     ("POST", "/repos/octo/shop-api/issues"): (201, {"number": 9, "html_url": "u9"}),
                     ("POST", "/repos/octo/shop-api/pulls"): (201, {"number": 41, "html_url": "u41"}),
                     ("GET", "/repos/octo/shop-api"): (200, {"default_branch": "main"})})
    # The publish stage: its own token by value; the AI key only as a hash from the agent stage.
    guard = TextGuard(values=[HOST_TOKEN], hashes=hashes_of([AI_KEY, "corp-internal-secret-42"]))
    return GuardedHost(GitHubAdapter(CTX, HOST_TOKEN, http), guard), http


def sent(http):
    return " ".join((c["body"] or b"").decode() for c in http.calls if c["method"] == "POST")


def test_a_planted_ai_key_in_an_issue_body_is_redacted_by_hash():
    host, http = guarded()
    host.open_issue("dawnfix: x", f"## Cause\nthe key is {AI_KEY}.\nalso corp-internal-secret-42\n")
    body = json.loads([c for c in http.calls if c["path"] == "/repos/octo/shop-api/issues"][0]["body"])["body"]
    assert AI_KEY not in body and "corp-internal-secret-42" not in body
    assert body.count(MARK) >= 2 and "Dawnfix removed" in body


def test_a_planted_host_token_and_a_credential_shape_in_a_pr_description_and_title():
    host, http = guarded()
    aws = "AKIA" + "R" * 16
    host.open_draft_change("dawnfix/1997f26556fdd1c5", f"dawnfix: {HOST_TOKEN}", f"see {HOST_TOKEN} and {aws}")
    pr = json.loads([c for c in http.calls if c["path"] == "/repos/octo/shop-api/pulls"][0]["body"])
    assert HOST_TOKEN not in json.dumps(pr) and aws not in pr["body"]
    assert pr["title"] == "dawnfix finding (title redacted)" and "Dawnfix removed 2 value(s)" in pr["body"]


def test_comments_too_and_clean_text_is_untouched():
    host, http = guarded()
    from dawnfix_core.run.hosts import Change
    host.comment(Change("issue", 9, "open", ""), f"again: {AI_KEY}")
    assert AI_KEY not in sent(http)
    assert TextGuard(values=[HOST_TOKEN]).clean("a token budget of 3, nothing secret") == ("a token budget of 3, nothing secret", 0)


def test_hash_files_hold_no_values(tmp_path):
    env = {"DAWNFIX_AI_API_KEY": AI_KEY, "DAWNFIX_ENTERPRISE_KEY": ENTERPRISE, "MY_DB_PASSWORD": "hunter2hunter2",
           "PATH": "/usr/bin", "SHORT_TOKEN": "abc"}
    assert set(secret_values(env)) == {AI_KEY, ENTERPRISE, "hunter2hunter2"}
    f = tmp_path / "secret-hashes.json"
    write_hashes(f, env)
    text = f.read_text()
    assert AI_KEY not in text and ENTERPRISE not in text and "hunter2" not in text
    assert {e["sha256"] for e in load_hashes(f)} == {hashlib.sha256(v.encode()).hexdigest() for v in secret_values(env)}
    (tmp_path / "bad.json").write_text("{not json")
    assert load_hashes(tmp_path / "bad.json") == [] and load_hashes(tmp_path / "missing.json") == []


ODD = 'Zq9"x{7},Lm42-Pw88Kd' + "Rt5Vb"  # a secret holding a quote, braces and a comma


def test_a_secret_with_quotes_braces_and_commas_is_found_by_hash_over_the_whole_text():
    g = TextGuard(hashes=hashes_of([ODD]))
    text, n = g.clean(f"before {ODD} after")
    assert ODD not in text and n == 1 and text == f"before {MARK} after"


def test_a_secret_embedded_in_json_even_escaped():
    g = TextGuard(hashes=hashes_of([ODD]))
    doc = json.dumps({"config": {"token": ODD, "n": 1}})
    assert '\\"' in doc  # the quote inside the secret is escaped in the JSON text
    text, n = g.clean(doc)
    assert n >= 1 and "Lm42-Pw88KdRt5Vb" not in text and "Zq9" not in text


def test_a_secret_split_across_two_lines():
    secret = "Alpha1234567Beta89012345"
    g = TextGuard(hashes=hashes_of([secret]))
    text, n = g.clean(f"key part one: Alpha1234567\nBeta89012345 was the rest\n")
    assert n == 1 and "Alpha1234567" not in text and "Beta89012345" not in text
    assert text.startswith("key part one: ") and text.endswith(" was the rest\n")


def test_tokens_of_a_secret_are_recorded_and_redacted():
    secret = "user:Sup3rS3cretPassw0rd@db.internal"
    entries = hashes_of([secret])
    assert len(entries) > 1 and all(e["len"] >= 8 for e in entries)
    text, n = TextGuard(hashes=entries).clean("the password Sup3rS3cretPassw0rd leaked alone")
    assert "Sup3rS3cretPassw0rd" not in text and n == 1
