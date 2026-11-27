"""The agency workflow template: least privilege, no baked-in URL or brand, and its client
matrix agrees with the example fleet.yml."""
import re
from pathlib import Path

import yaml

from dawnfix_fleet.config import load

FLEET = Path(__file__).resolve().parents[2]
WORKFLOW = FLEET / "templates" / "fleet-collect.yml"
EXAMPLE = FLEET / "collector" / "examples" / "fleet.yml"
# The same pins as dawnfix/templates/github/workflows/*.yml.
CHECKOUT = "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
PINS = {
    "actions/checkout": ("fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "v5.1.0"),
    "actions/setup-python": ("ece7cb06caefa5fff74198d8649806c4678c61a1", "v6.3.0"),
    "actions/cache": ("0057852bfaa89a56745cba8c7296529d2fc39830", "v4.3.0"),
    "aws-actions/configure-aws-credentials": ("61815dcd50bd041e203e49132bacad1fd04d2708", "v5.1.1"),
}


def test_least_privilege_and_matrix():
    wf = yaml.safe_load(WORKFLOW.read_text())
    assert wf["permissions"] == {"contents": "read", "id-token": "write"}
    job = wf["jobs"]["collect"]
    assert set(job["strategy"]["matrix"]["client"]) == set(load(str(EXAMPLE)))
    steps = {s.get("name") or s.get("uses"): s for s in job["steps"]}
    assert steps[CHECKOUT]["with"]["persist-credentials"] is False
    assert "--cache-dir .fleet-cache" in steps["Collect"]["run"]
    assert "-K -" in steps["Send to the board"]["run"]  # key via stdin, not argv


def test_no_url_or_brand_baked_in():
    text = WORKFLOW.read_text().lower()
    for needle in ("github.com/dawnfix", "dawnfix.dev", "workers.dev"):
        assert needle not in text


def test_every_action_is_pinned_to_a_full_commit_sha_with_its_tag():
    uses = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", WORKFLOW.read_text(), re.M)
    assert len(uses) == 4
    for ref, comment in uses:
        action, _, sha = ref.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", sha), ref
        want_sha, tag = PINS[action.split("/restore")[0].split("/save")[0]]
        assert (sha, comment.strip()) == (want_sha, f"# {tag}"), ref


def test_a_refused_key_is_reported_and_the_run_goes_on():
    """VERIFY item 3: a missing or refused Enterprise key never fails the collector run."""
    text = WORKFLOW.read_text()
    assert "401|402|403) say_need_key" in text
    assert "The Fleet board needs an Enterprise key. Contact dawnfix@" in text


def test_no_licence_gate_and_send_is_optional():
    """The collector is free: no licence job, no /v1/license call. Without the optional
    Enterprise key the send step exits 0 quietly and prints summary.json instead."""
    wf = yaml.safe_load(WORKFLOW.read_text())
    assert set(wf["jobs"]) == {"collect"}
    assert "/v1/license" not in WORKFLOW.read_text()
    job = wf["jobs"]["collect"]
    assert "needs" not in job and "if" not in job
    send = next(s for s in job["steps"] if s.get("name") == "Send to the board")["run"]
    head = re.split(r"^fi$", send, maxsplit=1, flags=re.M)[0]
    assert 'if [ -z "$FLEET_AGENCY_KEY" ]' in head
    assert "jq -c . summary.json" in head and "exit 0" in head and "::error" not in head


def test_licence_header_is_fsl():
    assert WORKFLOW.read_text().startswith("# SPDX-License-Identifier: FSL-1.1-ALv2\n")
    # One LICENSE at the repo root; no per-directory licence files.
    for d in (FLEET, FLEET / "collector"):
        assert not (d / "LICENSE").exists()
    root = (FLEET.parent / "LICENSE").read_text()
    assert "Functional Source License" in root
    assert 'license = "FSL-1.1-ALv2"' in (FLEET / "collector" / "pyproject.toml").read_text()
