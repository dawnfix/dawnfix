import json
import subprocess
import urllib.parse
from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import Stubber

from dawnfix_leastpriv import cli
from dawnfix_leastpriv import render as rd
from dawnfix_leastpriv.guard import ReadOnlyViolation, make_client

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
ROLE = "app-worker"
ROLE_ARN = f"arn:aws:iam::123456789012:role/{ROLE}"
JOB = "11111111-2222-3333-4444-555555555555"
ANALYZER = "arn:aws:access-analyzer:us-east-1:123456789012:analyzer/unused"
SES_ARN = "arn:aws:iam::123456789012:policy/legacy-ses"
SSM_ARN = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"

INLINE = {"Version": "2012-10-17", "Statement": [
    {"Sid": "S3", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteBucket", "s3:ListBucket"],
     "Resource": ["arn:aws:s3:::app-bucket", "arn:aws:s3:::app-bucket/*"]},
    {"Sid": "Queue", "Effect": "Allow", "Action": "sqs:*", "Resource": "arn:aws:sqs:us-east-1:123456789012:jobs"},
    {"Sid": "Dynamo", "Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:RestoreTableFromBackup"],
     "Resource": "*"},
    {"Sid": "NoIam", "Effect": "Deny", "Action": "iam:*", "Resource": "*"},
    {"Sid": "Rotate", "Effect": "Allow", "Action": "secretsmanager:RotateSecret", "Resource": "*",
     "Condition": {"StringEquals": {"aws:ResourceTag/app": "worker"}}},
]}
SES = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "ses:SendEmail", "Resource": "*"}]}
SSM = {"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Action": ["ssm:Describe*", "ssm:Get*", "ssm:List*"], "Resource": "*"}]}


def d(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def enc(doc):
    return urllib.parse.quote(json.dumps(doc))


def svc(ns, last, tracked=None):
    s = {"ServiceName": ns.upper(), "ServiceNamespace": ns}
    if last:
        s["LastAuthenticated"] = d(last)
    if tracked is not None:
        s["TrackedActionsLastAccessed"] = [
            {"ActionName": a, **({"LastAccessedTime": d(t)} if t else {})} for a, t in tracked.items()]
    return s


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def clients():
    s = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    iam, aa = make_client(s, "iam", "us-east-1"), make_client(s, "accessanalyzer", "us-east-1")
    st_iam, st_aa = Stubber(iam), Stubber(aa)
    yield iam, aa, st_iam, st_aa
    st_iam.deactivate()
    st_aa.deactivate()


def add_iam(st, created="2025-01-01"):
    st.add_response("get_role", {"Role": {"Path": "/", "RoleName": ROLE, "RoleId": "AROAEXAMPLEEXAMPLE1",
                                          "Arn": ROLE_ARN, "CreateDate": d(created)}}, {"RoleName": ROLE})
    st.add_response("list_attached_role_policies", {"AttachedPolicies": [
        {"PolicyName": "legacy-ses", "PolicyArn": SES_ARN},
        {"PolicyName": "AmazonSSMReadOnlyAccess", "PolicyArn": SSM_ARN}], "IsTruncated": False},
        {"RoleName": ROLE})
    for arn, doc in ((SES_ARN, SES), (SSM_ARN, SSM)):
        st.add_response("get_policy", {"Policy": {"PolicyName": arn.rsplit("/", 1)[1], "Arn": arn,
                                                  "DefaultVersionId": "v3"}}, {"PolicyArn": arn})
        st.add_response("get_policy_version", {"PolicyVersion": {"Document": enc(doc), "VersionId": "v3",
                                                                 "IsDefaultVersion": True}},
                        {"PolicyArn": arn, "VersionId": "v3"})
    st.add_response("list_role_policies", {"PolicyNames": ["app"], "IsTruncated": False}, {"RoleName": ROLE})
    st.add_response("get_role_policy", {"RoleName": ROLE, "PolicyName": "app", "PolicyDocument": enc(INLINE)},
                    {"RoleName": ROLE, "PolicyName": "app"})
    st.add_response("generate_service_last_accessed_details", {"JobId": JOB},
                    {"Arn": ROLE_ARN, "Granularity": "ACTION_LEVEL"})
    st.add_response("get_service_last_accessed_details", {
        "JobStatus": "IN_PROGRESS", "JobCreationDate": NOW, "JobCompletionDate": NOW, "ServicesLastAccessed": []}, {"JobId": JOB})
    st.add_response("get_service_last_accessed_details", {
        "JobStatus": "COMPLETED", "JobType": "ACTION_LEVEL", "JobCreationDate": NOW, "JobCompletionDate": NOW,
        "IsTruncated": False, "ServicesLastAccessed": [
            svc("s3", "2026-10-26", {"ListBucket": "2026-10-26", "DeleteBucket": None}),
            svc("sqs", None),
            svc("dynamodb", "2026-10-26", {"GetItem": "2026-10-26", "RestoreTableFromBackup": None}),
            svc("iam", None),
            svc("secretsmanager", "2026-05-01", {"RotateSecret": "2026-05-01"}),
            svc("ses", None),
            svc("ssm", "2026-10-20", {"GetParameter": "2026-10-20", "DescribeParameters": None}),
        ]}, {"JobId": JOB})


def add_aa(st):
    st.add_response("list_analyzers", {"analyzers": [{
        "arn": ANALYZER, "name": "unused", "type": "ACCOUNT_UNUSED_ACCESS", "createdAt": d("2026-01-01"),
        "status": "ACTIVE", "configuration": {"unusedAccess": {"unusedAccessAge": 90}}}]},
        {"type": "ACCOUNT_UNUSED_ACCESS"})
    st.add_response("list_findings_v2", {"findings": [{
        "id": "f1", "resource": ROLE_ARN, "resourceType": "AWS::IAM::Role", "resourceOwnerAccount": "123456789012",
        "status": "ACTIVE", "findingType": "UnusedPermission", "analyzedAt": NOW, "createdAt": NOW,
        "updatedAt": NOW}]}, {"analyzerArn": ANALYZER, "filter": {
            "resource": {"eq": [ROLE_ARN]}, "findingType": {"eq": ["UnusedPermission", "UnusedIAMRole"]},
            "status": {"eq": ["ACTIVE"]}}})
    st.add_response("get_finding_v2", {
        "id": "f1", "resource": ROLE_ARN, "resourceType": "AWS::IAM::Role", "resourceOwnerAccount": "123456789012",
        "status": "ACTIVE", "findingType": "UnusedPermission", "analyzedAt": NOW, "createdAt": NOW,
        "updatedAt": NOW, "findingDetails": [
            {"unusedPermissionDetails": {"serviceNamespace": "sqs"}},
            {"unusedPermissionDetails": {"serviceNamespace": "dynamodb",
                                         "actions": [{"action": "dynamodb:RestoreTableFromBackup"}]}},
        ]}, {"analyzerArn": ANALYZER, "id": "f1"})


def run(clients, tmp_path, *extra, created="2025-01-01", aa_ok=True):
    iam, aa, st_iam, st_aa = clients
    add_iam(st_iam, created)
    if aa_ok:
        add_aa(st_aa)
    else:
        st_aa.add_client_error("list_analyzers", "AccessDeniedException", "no")
    st_iam.activate()
    st_aa.activate()
    sleeps = []
    args = cli.parser().parse_args(["role", ROLE, "--days", "90", "--out", str(tmp_path), *extra])
    code = cli.cmd_role(args, iam=iam, aa=aa, sleep=sleeps.append, now=NOW)
    st_iam.assert_no_pending_responses()
    st_aa.assert_no_pending_responses()
    return code, json.loads((tmp_path / "report.json").read_text()), sleeps


def removals(report):
    return {(p["name"], r["action"]): r for p in report["policies"] for r in p["removals"]}


def test_trims_unused_with_risk_notes(clients, tmp_path, capsys):
    code, rep, sleeps = run(clients, tmp_path)
    assert code == 0 and sleeps == [1.0] and rep["applied"] is False
    rem = removals(rep)
    assert set(rem) == {("app", "s3:DeleteBucket"), ("app", "sqs:*"), ("app", "dynamodb:RestoreTableFromBackup"),
                        ("app", "secretsmanager:RotateSecret"), ("legacy-ses", "ses:SendEmail")}
    assert rem[("app", "s3:DeleteBucket")]["risk"] == "low" and rem[("app", "s3:DeleteBucket")]["basis"] == "action"
    assert "blast radius" in rem[("app", "s3:DeleteBucket")]["note"]
    assert rem[("app", "sqs:*")]["sources"] == ["IAM last accessed", "Access Analyzer"]
    assert rem[("app", "dynamodb:RestoreTableFromBackup")]["risk"] == "high"
    assert rem[("app", "dynamodb:RestoreTableFromBackup")]["sources"][-1] == "Access Analyzer"
    assert rem[("app", "secretsmanager:RotateSecret")]["risk"] == "high"
    assert rem[("app", "secretsmanager:RotateSecret")]["last_used"] == "2026-05-01"
    assert "yearly or quarterly" in rem[("app", "secretsmanager:RotateSecret")]["note"]

    pols = {p["name"]: p for p in rep["policies"]}
    new = pols["app"]["new_document"]["Statement"]
    assert [s.get("Sid") for s in new] == ["S3", "Dynamo", "NoIam"]  # Queue and Rotate statements emptied out
    assert new[0]["Action"] == ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]  # untracked actions are kept
    assert new[1]["Action"] == ["dynamodb:GetItem"]
    assert new[2] == INLINE["Statement"][3]  # Deny untouched
    assert pols["legacy-ses"]["delete_policy"] is True
    assert pols["AmazonSSMReadOnlyAccess"]["changed"] is False
    assert any("ssm:getparameter" in s for s in pols["AmazonSSMReadOnlyAccess"]["suggestions"])

    pr = (tmp_path / "pr.md").read_text()
    assert "Removes 5 permission(s) not used in the last 90 days (2 high, 0 medium, 3 low risk)" in pr
    assert "nothing was applied to AWS" in pr
    assert "| high | `dynamodb:RestoreTableFromBackup` |" in pr
    assert "detach and delete this policy" in pr
    tf = (tmp_path / "app.terraform.diff").read_text()
    assert tf.startswith("--- a/iam/app.tf\n+++ b/iam/app.tf\n")
    assert '-      "s3:DeleteBucket",' in tf and '-    actions   = ["sqs:*"]' in tf
    js = (tmp_path / "app.json.diff").read_text()
    assert '-        "s3:DeleteBucket",' in js
    cfn = (tmp_path / "app.cloudformation.diff").read_text()
    assert '-        - "dynamodb:RestoreTableFromBackup"' in cfn
    assert '"aws:ResourceTag/app": "worker"' in cfn
    assert json.loads((tmp_path / "app.json").read_text())["Statement"][0]["Sid"] == "S3"
    assert "5 unused permission(s) to remove (2 high risk)" in capsys.readouterr().err


def test_young_role_bumps_risk(clients, tmp_path):
    _, rep, _ = run(clients, tmp_path, created="2026-09-27")
    rem = removals(rep)
    assert rep["evidence_days"] == 30
    assert rem[("app", "s3:DeleteBucket")]["risk"] == "medium"
    assert any("only 30 days of evidence" in n for n in rep["notes"])


def test_works_without_access_analyzer(clients, tmp_path):
    _, rep, _ = run(clients, tmp_path, aa_ok=False)
    rem = removals(rep)
    assert rem[("app", "sqs:*")]["sources"] == ["IAM last accessed"]
    assert any("AccessDeniedException" in n for n in rep["notes"])


def test_policy_file_patch_applies_with_git_and_drift_is_refused(clients, tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "iam").mkdir(parents=True)
    (repo / "iam" / "app.json").write_text(json.dumps(INLINE, indent=4) + "\n")
    (repo / "iam" / "ses.json").write_text(json.dumps({"Statement": []}) + "\n")  # drifted from live
    monkeypatch.chdir(repo)
    out = tmp_path / "out"
    run(clients, out, "--policy-file", "app=iam/app.json", "--policy-file", "legacy-ses=iam/ses.json")
    patch = (out / "app.patch").read_text()
    assert patch.startswith("--- a/iam/app.json\n+++ b/iam/app.json\n")
    assert '-                "s3:DeleteBucket",' in patch  # 4-space indent preserved: a small, reviewable hunk
    assert not (out / "legacy_ses.patch").exists()
    assert "drift" in capsys.readouterr().err
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "apply", str(out / "app.patch")], cwd=repo, check=True)
    applied = json.loads((repo / "iam" / "app.json").read_text())
    assert applied == json.loads((out / "app.json").read_text())


def test_cloudformation_yaml_round_trips():
    yaml = pytest.importorskip("yaml")
    assert yaml.safe_load(rd.as_cloudformation(INLINE, "app"))["PolicyDocument"] == INLINE


def test_guard_refuses_writes(clients):
    iam, aa, _, _ = clients
    for call in (lambda: iam.put_role_policy(RoleName="r", PolicyName="p", PolicyDocument="{}"),
                 lambda: iam.detach_role_policy(RoleName="r", PolicyArn=SES_ARN),
                 lambda: iam.create_policy_version(PolicyArn=SES_ARN, PolicyDocument="{}"),
                 lambda: aa.generate_finding_recommendation(analyzerArn=ANALYZER, id="f1")):
        with pytest.raises(ReadOnlyViolation):
            call()


def test_days_bounds():
    args = cli.parser().parse_args(["role", ROLE, "--days", "500"])
    assert cli.cmd_role(args, iam=object()) == 2


def test_terraform_and_yaml_rendering():
    tf = rd.as_terraform(INLINE, "app")
    assert 'data "aws_iam_policy_document" "app" {' in tf
    assert 'test     = "StringEquals"' in tf and 'variable = "aws:ResourceTag/app"' in tf
    assert rd.as_terraform({"Statement": [{"Effect": "Allow", "Action": "s3:GetObject",
                                           "Resource": "arn:aws:s3:::b/${aws:username}/*"}]}, "x").count("$${") == 1
    y = rd.as_cloudformation(SES, "legacy-ses")
    assert y == ('# legacy-ses\nPolicyDocument:\n  Version: "2012-10-17"\n  Statement:\n    - Effect: "Allow"\n'
                 '      Action: "ses:SendEmail"\n      Resource: "*"\n')
