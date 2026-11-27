"""`logbill fix`: retention commands for never-expiring groups. Printing them is the
default; `--apply` is the only write path in logbill and needs a typed confirmation."""
import shlex
import sys

from . import brand
from .awsread import WRITE_OPERATIONS, error_code, list_log_groups

# Values PutRetentionPolicy accepts.
VALID_RETENTION = (1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827,
                   2192, 2557, 2922, 3288, 3653)


def targets_from_report(report: dict, only: set | None = None) -> list[tuple[str, str]]:
    out = []
    for g in report.get("groups", []):
        if g.get("never_expires") and (not only or g["name"] in only):
            out.append((g["region"], g["name"]))
    return out


def targets_live(make_logs_client, regions: list[str], only: set | None = None) -> list[tuple[str, str]]:
    """Read-only listing (DescribeLogGroups) of groups without retention."""
    out = []
    for region in regions:
        for lg in list_log_groups(make_logs_client(region)):
            if lg.get("retentionInDays") is None and lg.get("logGroupClass") != "DELIVERY":
                if not only or lg["logGroupName"] in only:
                    out.append((region, lg["logGroupName"]))
    return out


def command(region: str, name: str, days: int, profile: str | None = None) -> str:
    args = ["aws", "logs", "put-retention-policy", "--region", region, "--log-group-name", name,
            "--retention-in-days", str(days)]
    if profile:
        args += ["--profile", profile]
    return " ".join(shlex.quote(a) for a in args)


def confirm_apply(n: int, days: int, stdin=None, stdout=None) -> bool:
    """The user must type `apply <n>` on a terminal. Anything else, or no terminal, is a no."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stderr
    if not stdin.isatty():
        print(f"{brand.CLI}: --apply needs an interactive terminal to confirm; nothing changed", file=stdout)
        return False
    want = f"apply {n}"
    print(f"This sets {days}-day retention on {n} log group(s). Log data older than {days} days in "
          f"those groups will be deleted by AWS and cannot be recovered.", file=stdout)
    print(f"Type '{want}' to continue: ", end="", file=stdout, flush=True)
    return stdin.readline().strip() == want


def apply(make_write_client, targets: list[tuple[str, str]], days: int) -> list[dict]:
    """Calls PutRetentionPolicy on a client whose allowlist holds only that operation."""
    results = []
    clients = {}
    for region, name in targets:
        if region not in clients:
            clients[region] = make_write_client(region, WRITE_OPERATIONS)
        try:
            clients[region].put_retention_policy(logGroupName=name, retentionInDays=days)
            results.append({"region": region, "group": name, "ok": True})
        except Exception as e:  # keep going; report codes only
            results.append({"region": region, "group": name, "ok": False, "error": error_code(e)})
    return results
