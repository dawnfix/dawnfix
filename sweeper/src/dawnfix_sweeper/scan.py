"""Find what an old stack left behind after a cutover. Read-only: every call goes through guard.make_client.

The scanner never deletes anything. It returns Items, each with the exact CLI command(s)
a human would run to tear it down, in dependency order.
"""
from __future__ import annotations

import ipaddress
import json
import re
import shlex
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from botocore.exceptions import BotoCoreError, ClientError

from .guard import ReadOnlyViolation, make_client
from .pricing import Prices

# Teardown order. DNS first (dangling names are a takeover risk and must go before
# their targets), then consumers before what they consume, logs last.
PHASES = {
    "route53_record": 1,
    "ecs_service": 2,
    "eb_environment": 3,
    "eb_application": 4,
    "load_balancer": 5,
    "classic_elb": 6,
    "target_group": 7,
    "nat_gateway": 8,
    "ec2_instance": 9,
    "rds_instance": 10,
    "rds_snapshot": 11,
    "ami": 12,
    "snapshot": 13,
    "ebs_volume": 14,
    "elastic_ip": 15,
    "log_group": 16,
}
KIND_TITLES = {
    "route53_record": "Route 53 records pointing at deleted or doomed targets",
    "ecs_service": "ECS services at 0 desired",
    "eb_environment": "Elastic Beanstalk environments",
    "eb_application": "Elastic Beanstalk applications",
    "load_balancer": "Load balancers with no healthy targets",
    "classic_elb": "Classic load balancers with no healthy instances",
    "target_group": "Target groups with zero registered targets",
    "nat_gateway": "NAT gateways with no traffic since the cutover",
    "ec2_instance": "EC2 instances stopped since before the cutover",
    "rds_instance": "RDS instances stopped or with no connections since the cutover",
    "rds_snapshot": "RDS manual snapshots taken before the cutover",
    "ami": "AMIs not used by any instance",
    "snapshot": "EBS snapshots",
    "ebs_volume": "Unattached EBS volumes",
    "elastic_ip": "Unassociated Elastic IPs",
    "log_group": "Log groups with no events since the cutover",
}
ELB_DNS = re.compile(r"\.([a-z]{2}(?:-gov)?-[a-z]+-\d)\.elb\.amazonaws\.com$")
EB_DNS = re.compile(r"\.([a-z]{2}(?:-gov)?-[a-z]+-\d)\.elasticbeanstalk\.com$")
MAX_PAGES = 500


@dataclass
class Item:
    kind: str
    region: str
    id: str
    name: str
    reason: str
    monthly_usd: float | None
    cost_note: str = ""
    action: str = "delete"  # delete | verify (needs a human to confirm it is really dead)
    commands: list[str] = field(default_factory=list)
    backup_commands: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    created: str | None = None
    tags: dict = field(default_factory=dict)

    @property
    def phase(self) -> int:
        return PHASES[self.kind]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["phase"] = self.phase
        if d["monthly_usd"] is not None:
            d["monthly_usd"] = round(d["monthly_usd"], 2)
        return d


def _q(*parts) -> str:
    return " ".join(shlex.quote(str(p)) for p in parts)


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(dt / 1000, tz=timezone.utc)
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(v) -> datetime | None:
    s = _iso(v)
    return None if s is None else datetime.fromisoformat(s.replace("Z", "+00:00"))


def _tags(lst, key="Key", value="Value") -> dict:
    return {t[key]: t.get(value, "") for t in (lst or [])}


def _norm_dns(name: str) -> str:
    n = name.lower().rstrip(".")
    return n[len("dualstack."):] if n.startswith("dualstack.") else n


STOPPED_AT = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)")


def _stopped_at(reason: str | None) -> datetime | None:
    """'User initiated (2026-08-01 10:00:00 GMT)' -> that time; None if EC2 gave no time."""
    m = STOPPED_AT.search(reason or "")
    return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc) if m else None


def _code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


def parse_tag_filters(specs: list[str] | None) -> dict[str, str | None]:
    """`Key=Value` must match exactly; bare `Key` only requires the key."""
    out = {}
    for s in specs or []:
        k, sep, v = s.partition("=")
        if not k:
            raise ValueError(f"bad --tag {s!r}; use Key=Value or Key")
        out[k] = v if sep else None
    return out


def load_ip_ranges(path: str) -> list:
    """AWS ip-ranges.json (https://ip-ranges.amazonaws.com/ip-ranges.json): EC2 prefixes only."""
    doc = json.loads(open(path).read())
    nets = [p["ip_prefix"] for p in doc.get("prefixes", []) if p.get("service") == "EC2"]
    nets += [p["ipv6_prefix"] for p in doc.get("ipv6_prefixes", []) if p.get("service") == "EC2"]
    return [ipaddress.ip_network(n) for n in nets]


class Scanner:
    def __init__(self, session, regions: list[str], before: datetime, tags: dict | None = None,
                 prices: Prices | None = None, ip_ranges: list | None = None, clients: dict | None = None,
                 now: datetime | None = None):
        self.session = session
        self.now = now or datetime.now(timezone.utc)
        self.regions = regions
        self.before = before if before.tzinfo else before.replace(tzinfo=timezone.utc)
        self.tag_filter = tags or {}
        self.prices = prices or Prices.load()
        self.ip_ranges = ip_ranges
        self._clients = dict(clients or {})  # (service, region) -> client
        self.items: list[Item] = []
        self.errors: list[dict] = []
        self.notes: list[str] = []
        # Inventory of live things, filled while scanning, used for the DNS check.
        self.live_lb_dns: set[str] = set()
        self.live_eb_dns: set[str] = set()
        self.owned_ips: set[str] = set()
        self.doomed_dns: dict[str, str] = {}  # dns -> item id this plan tears down
        self.doomed_ips: dict[str, str] = {}

    # --- plumbing ---------------------------------------------------------------

    def client(self, service: str, region: str):
        key = (service, region)
        if key not in self._clients:
            self._clients[key] = make_client(self.session, service, region)
        return self._clients[key]

    def _pages(self, client, op: str, result_key: str, **params):
        if client.can_paginate(op):
            for page in client.get_paginator(op).paginate(**params):
                yield from page.get(result_key, [])
            return
        yield from getattr(client, op)(**params).get(result_key, [])

    def _old(self, dt) -> bool:
        d = _dt(dt)
        return d is not None and d < self.before

    def _match(self, tags: dict) -> bool:
        for k, v in self.tag_filter.items():
            if k not in tags or (v is not None and tags[k] != v):
                return False
        return True

    def _safe(self, name: str, region: str, fn):
        try:
            fn(region)
        except ReadOnlyViolation:
            raise
        except (ClientError, BotoCoreError) as e:
            self.errors.append({"collector": name, "region": region, "error_code": _code(e)})

    # --- entry point ----------------------------------------------------------------

    def run(self) -> dict:
        account = None
        try:
            account = self.client("sts", self.regions[0]).get_caller_identity().get("Account")
        except ReadOnlyViolation:
            raise
        except (ClientError, BotoCoreError) as e:
            self.errors.append({"collector": "sts", "region": self.regions[0], "error_code": _code(e)})
        for region in self.regions:
            if not self.prices.has_region(region):
                self.notes.append(f"{region} is not in the price table; its items are priced at "
                                  f"{self.prices.default_region} list prices.")
            self._instances, self._used_images = {}, set()
            self._lb_by_name, self._elb_items = {}, {}
            self._classic_by_name, self._classic_items = {}, {}
            self._safe("ec2_instances", region, self._ec2_instances)
            self._safe("elastic_ips", region, self._eips)
            self._safe("ebs_volumes", region, self._volumes)
            self._safe("amis_snapshots", region, self._images_and_snapshots)
            self._safe("nat_gateways", region, self._nat_gateways)
            self._safe("elbv2", region, self._elbv2)
            self._safe("classic_elb", region, self._classic_elb)
            self._safe("elastic_beanstalk", region, self._beanstalk)
            self._safe("ecs", region, self._ecs)
            self._safe("rds", region, self._rds)
            self._safe("log_groups", region, self._logs)
        self._safe("route53", "global", self._route53)
        self.items.sort(key=lambda i: (i.phase, i.region, i.id))
        return {"account": account, "items": self.items, "errors": self.errors, "notes": self.notes}

    # --- EC2 ------------------------------------------------------------------------

    def _ec2_instances(self, region):
        ec2 = self.client("ec2", region)
        stopped = []
        for r in self._pages(ec2, "describe_instances", "Reservations"):
            for i in r.get("Instances", []):
                if i.get("State", {}).get("Name") == "terminated":
                    continue
                self._instances[i["InstanceId"]] = i.get("InstanceType")
                if i.get("ImageId"):
                    self._used_images.add(i["ImageId"])
                if i.get("PublicIpAddress"):
                    self.owned_ips.add(i["PublicIpAddress"])
                if i.get("State", {}).get("Name") == "stopped":
                    since = _stopped_at(i.get("StateTransitionReason")) or _dt(i.get("LaunchTime"))
                    tags = _tags(i.get("Tags"))
                    if since is not None and since < self.before and self._match(tags):
                        stopped.append((i, since, tags))
        if stopped:
            self._stopped_instances(ec2, region, stopped)

    def _stopped_instances(self, ec2, region, stopped):
        """A stopped instance bills no compute, but its EBS volumes (and any Elastic IP) still bill."""
        ids = [i["InstanceId"] for i, _, _ in stopped]
        volumes: dict[str, list[dict]] = {}
        for k in range(0, len(ids), 200):
            for v in self._pages(ec2, "describe_volumes", "Volumes",
                                 Filters=[{"Name": "attachment.instance-id", "Values": ids[k:k + 200]}]):
                for a in v.get("Attachments", []):
                    volumes.setdefault(a.get("InstanceId"), []).append({**v, "_delete_on_termination":
                                                                         a.get("DeleteOnTermination", False)})
        p = self.prices.region(region)
        for inst, since, tags in stopped:
            iid = inst["InstanceId"]
            vols = volumes.get(iid, [])
            cost, unknown = 0.0, []
            for v in vols:
                c = p.ebs_volume(v.get("VolumeType", ""), int(v.get("Size", 0)), v.get("Iops"), v.get("Throughput"))
                if c is None:
                    unknown.append(v["VolumeId"])
                else:
                    cost += c
            kept = [v["VolumeId"] for v in vols if not v["_delete_on_termination"]]
            reason = f"{inst.get('InstanceType')} stopped since {_iso(since)[:10]}"
            if kept:
                reason += f"; {', '.join(kept)} survive termination (DeleteOnTermination is off): delete them after"
            note = f"EBS storage of {len(vols)} attached volume(s); a stopped instance bills no compute"
            if unknown:
                note += f"; not priced: {', '.join(unknown)}"
            name = tags.get("Name", iid)
            self.items.append(Item(
                "ec2_instance", region, iid, name, reason, cost, note,
                action="verify",  # stopped on purpose (a pet, a break-glass box) happens
                commands=[_q("aws", "ec2", "terminate-instances", "--instance-ids", iid, "--region", region)],
                backup_commands=[_q("aws", "ec2", "create-image", "--instance-id", iid, "--name",
                                    f"pre-teardown-{iid}", "--no-reboot", "--region", region)],
                created=_iso(inst.get("LaunchTime")), tags=tags))

    def _eips(self, region):
        ec2 = self.client("ec2", region)
        for a in ec2.describe_addresses().get("Addresses", []):
            ip = a.get("PublicIp")
            if ip:
                self.owned_ips.add(ip)
            if a.get("AssociationId") or a.get("InstanceId") or a.get("NetworkInterfaceId"):
                continue
            tags = _tags(a.get("Tags"))
            if not self._match(tags):
                continue
            alloc = a.get("AllocationId") or ip
            item = Item("elastic_ip", region, alloc, ip or alloc, "Elastic IP not associated with anything",
                        self.prices.region(region).public_ipv4(), "public IPv4 hourly charge",
                        commands=[_q("aws", "ec2", "release-address", "--allocation-id", alloc, "--region", region)],
                        tags=tags)
            self.items.append(item)
            if ip:
                self.doomed_ips[ip] = item.id

    def _volumes(self, region):
        ec2 = self.client("ec2", region)
        for v in self._pages(ec2, "describe_volumes", "Volumes",
                             Filters=[{"Name": "status", "Values": ["available"]}]):
            tags = _tags(v.get("Tags"))
            if not self._old(v.get("CreateTime")) or not self._match(tags):
                continue
            vid = v["VolumeId"]
            self.items.append(Item(
                "ebs_volume", region, vid, tags.get("Name", vid),
                f"{v.get('VolumeType')} {v.get('Size')} GiB volume, attached to nothing",
                self.prices.region(region).ebs_volume(v.get("VolumeType", ""), int(v.get("Size", 0)), v.get("Iops"), v.get("Throughput")),
                f"{v.get('VolumeType')} storage" + (" + provisioned IOPS" if v.get("VolumeType") in ("io1", "io2", "gp3") else ""),
                commands=[_q("aws", "ec2", "delete-volume", "--volume-id", vid, "--region", region)],
                backup_commands=[_q("aws", "ec2", "create-snapshot", "--volume-id", vid, "--description",
                                    f"pre-teardown copy of {vid}", "--region", region)],
                created=_iso(v.get("CreateTime")), tags=tags))

    def _images_and_snapshots(self, region):
        ec2 = self.client("ec2", region)
        images = list(self._pages(ec2, "describe_images", "Images", Owners=["self"]))
        snap_to_image: dict[str, tuple[str, bool]] = {}
        for img in images:
            iid = img["ImageId"]
            tags = _tags(img.get("Tags"))
            doomed = (self._old(img.get("CreationDate")) and iid not in self._used_images and self._match(tags))
            snaps = [b["Ebs"]["SnapshotId"] for b in img.get("BlockDeviceMappings", [])
                     if b.get("Ebs", {}).get("SnapshotId")]
            for s in snaps:
                snap_to_image[s] = (iid, doomed)
            if not doomed:
                continue
            self.items.append(Item(
                "ami", region, iid, img.get("Name") or iid,
                "AMI created before the cutover and not used by any running or stopped instance",
                0.0, "AMIs are billed through their backing snapshots (listed separately)",
                action="verify",  # launch templates / ASGs / other accounts may still reference it
                commands=[_q("aws", "ec2", "deregister-image", "--image-id", iid, "--region", region)],
                created=_iso(img.get("CreationDate")), tags=tags))
        for s in self._pages(ec2, "describe_snapshots", "Snapshots", OwnerIds=["self"]):
            sid = s["SnapshotId"]
            tags = _tags(s.get("Tags"))
            if not self._old(s.get("StartTime")) or not self._match(tags):
                continue
            depends, reason = [], "snapshot taken before the cutover"
            if sid in snap_to_image:
                iid, doomed = snap_to_image[sid]
                if not doomed:
                    continue  # backs an AMI we keep; it cannot be deleted anyway
                depends, reason = [iid], f"backs {iid}, which this plan deregisters"
            full = s.get("FullSnapshotSizeInBytes")
            if full:
                gb, note = full / 1e9, "full snapshot size; billed size is the changed blocks, so this is an upper bound"
            else:
                gb, note = float(s.get("VolumeSize", 0)), "source volume size; billed size is the changed blocks, so this is an upper bound"
            managed = any(k.startswith(("aws:backup", "dlm:")) for k in tags) or "AWS Backup" in (s.get("Description") or "")
            if managed:
                reason += "; managed by AWS Backup or Data Lifecycle Manager: change the plan/policy instead"
            self.items.append(Item(
                "snapshot", region, sid, tags.get("Name", s.get("Description") or sid), reason,
                self.prices.region(region).snapshot(gb), note, action="verify" if managed else "delete",
                commands=[_q("aws", "ec2", "delete-snapshot", "--snapshot-id", sid, "--region", region)],
                depends_on=depends, created=_iso(s.get("StartTime")), tags=tags))

    # --- NAT gateways -----------------------------------------------------------------

    def _metric(self, region, namespace: str, metric: str, dim: str, ids: list[str], stat: str):
        """{id: (value, datapoints)} since the cutover, one GetMetricData call per 500 ids.

        `value` is the Sum (or Maximum) over the whole window. Raises on API errors; the
        caller decides what an unknown means.
        """
        cw = self.client("cloudwatch", region)
        start, end = self.before, self.now
        out: dict[str, tuple[float, int]] = {}
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            queries = [{"Id": f"m{n}", "ReturnData": True, "MetricStat": {
                "Metric": {"Namespace": namespace, "MetricName": metric,
                           "Dimensions": [{"Name": dim, "Value": rid}]},
                "Period": 86400, "Stat": stat}} for n, rid in enumerate(chunk)]
            params = {"MetricDataQueries": queries, "StartTime": start, "EndTime": end, "ScanBy": "TimestampAscending"}
            for _ in range(MAX_PAGES):
                resp = cw.get_metric_data(**params)
                for r in resp.get("MetricDataResults", []):
                    rid = chunk[int(r["Id"][1:])]
                    vals = r.get("Values", [])
                    prev, n = out.get(rid, (0.0, 0))
                    agg = max([prev, *vals]) if stat == "Maximum" else prev + sum(vals)
                    out[rid] = (agg, n + len(vals))
                if not resp.get("NextToken"):
                    break
                params["NextToken"] = resp["NextToken"]
        return out

    def _nat_gateways(self, region):
        ec2 = self.client("ec2", region)
        cands = []
        for g in self._pages(ec2, "describe_nat_gateways", "NatGateways",
                             Filter=[{"Name": "state", "Values": ["available"]}]):
            tags = _tags(g.get("Tags"))
            if self._old(g.get("CreateTime")) and self._match(tags):
                cands.append((g, tags))
        if not cands:
            return
        try:
            traffic = self._metric(region, "AWS/NATGateway", "BytesOutToDestination", "NatGatewayId",
                                   [g["NatGatewayId"] for g, _ in cands], "Sum")
        except ReadOnlyViolation:
            raise
        except (ClientError, BotoCoreError) as e:
            self.errors.append({"collector": "nat_gateway_traffic", "region": region, "error_code": _code(e)})
            traffic = None
        p = self.prices.region(region)
        for g, tags in cands:
            gid = g["NatGatewayId"]
            if traffic is None:
                action, reason = "verify", "traffic unknown (CloudWatch GetMetricData failed)"
            else:
                sent, points = traffic.get(gid, (0.0, 0))
                if sent > 0:
                    continue  # something still routes through it
                action = "delete" if points else "verify"
                reason = ("no bytes out since the cutover" if points
                          else "no traffic datapoints since the cutover (CloudWatch has none for it)")
            public = [a for a in g.get("NatGatewayAddresses", []) if a.get("PublicIp")]
            cost = p.nat_gateway()
            note = "NAT gateway hourly charge"
            if cost is not None and public:
                cost += len(public) * (p.public_ipv4() or 0)
                note += f" + {len(public)} public IPv4"
            if p.nat_gb() is not None:
                note += f"; data processing (${p.nat_gb():.3f}/GB) is zero while idle"
            cmds = [_q("aws", "ec2", "delete-nat-gateway", "--nat-gateway-id", gid, "--region", region)]
            # Its Elastic IPs stay allocated (and billed) after the gateway is gone.
            cmds += [_q("aws", "ec2", "release-address", "--allocation-id", a["AllocationId"], "--region", region)
                     for a in public if a.get("AllocationId")]
            if len(cmds) > 1:
                reason += "; wait for the gateway to reach `deleted` before releasing its Elastic IP"
            self.items.append(Item(
                "nat_gateway", region, gid, tags.get("Name", gid), reason, cost, note, action=action,
                commands=cmds, created=_iso(g.get("CreateTime")), tags=tags))

    # --- ELBv2 ----------------------------------------------------------------------

    def _elbv2(self, region):
        elb = self.client("elbv2", region)
        lbs = list(self._pages(elb, "describe_load_balancers", "LoadBalancers"))
        tgs = list(self._pages(elb, "describe_target_groups", "TargetGroups"))
        self._lb_by_name.update({lb["LoadBalancerName"]: lb for lb in lbs})
        tags: dict[str, dict] = {}
        if self.tag_filter:
            arns = [lb["LoadBalancerArn"] for lb in lbs] + [tg["TargetGroupArn"] for tg in tgs]
            for i in range(0, len(arns), 20):
                for d in elb.describe_tags(ResourceArns=arns[i:i + 20]).get("TagDescriptions", []):
                    tags[d["ResourceArn"]] = _tags(d.get("Tags"))
        health: dict[str, tuple[int, int]] = {}
        for tg in tgs:
            descs = elb.describe_target_health(TargetGroupArn=tg["TargetGroupArn"]).get("TargetHealthDescriptions", [])
            healthy = sum(1 for d in descs if d.get("TargetHealth", {}).get("State") == "healthy")
            health[tg["TargetGroupArn"]] = (len(descs), healthy)
        doomed_lbs = set()
        for lb in lbs:
            arn, dns = lb["LoadBalancerArn"], _norm_dns(lb.get("DNSName", ""))
            attached = [tg for tg in tgs if arn in tg.get("LoadBalancerArns", [])]
            alive = any(health[tg["TargetGroupArn"]][1] > 0 for tg in attached)
            if alive or not self._old(lb.get("CreatedTime")) or not self._match(tags.get(arn, {})):
                self.live_lb_dns.add(dns)
                continue
            lb_type = lb.get("Type", "application")
            cost = self.prices.region(region).load_balancer(lb_type)
            note = f"{lb_type} load balancer hourly charge, no LCU"
            if cost is not None and lb.get("Scheme") == "internet-facing" and lb_type != "gateway":
                n = max(1, len(lb.get("AvailabilityZones", [])))
                cost += n * (self.prices.region(region).public_ipv4() or 0)
                note += f" + {n} public IPv4"
            if attached:
                reason = f"none of its {len(attached)} target group(s) has a healthy target"
                action = "delete"
            else:
                reason = "no target groups attached (listeners may be redirects or fixed responses)"
                action = "verify"
            item = Item("load_balancer", region, arn, lb["LoadBalancerName"], reason, cost, note, action=action,
                        commands=[_q("aws", "elbv2", "delete-load-balancer", "--load-balancer-arn", arn,
                                     "--region", region)],
                        created=_iso(lb.get("CreatedTime")), tags=tags.get(arn, {}))
            self._elb_items[lb["LoadBalancerName"]] = item
            self.items.append(item)
            doomed_lbs.add(arn)
            self.live_lb_dns.add(dns)  # still exists today; records to it are "doomed", not dangling
            self.doomed_dns[dns] = arn
        for tg in tgs:
            arn = tg["TargetGroupArn"]
            registered, _ = health[arn]
            if registered or not self._match(tags.get(arn, {})):
                continue
            users = tg.get("LoadBalancerArns", [])
            kept = [a for a in users if a not in doomed_lbs]
            self.items.append(Item(
                "target_group", region, arn, tg["TargetGroupName"], "zero registered targets", 0.0,
                "target groups are free; this is clutter that hides real config",
                action="verify" if kept else "delete",
                commands=[_q("aws", "elbv2", "delete-target-group", "--target-group-arn", arn, "--region", region)],
                depends_on=[a for a in users if a in doomed_lbs], tags=tags.get(arn, {})))
            if kept:
                self.items[-1].reason += "; still referenced by a kept load balancer (remove the listener rule first)"

    # --- Classic ELB --------------------------------------------------------------------

    def _classic_elb(self, region):
        elb = self.client("elb", region)
        lbs = list(self._pages(elb, "describe_load_balancers", "LoadBalancerDescriptions"))
        self._classic_by_name.update({lb["LoadBalancerName"]: lb for lb in lbs})
        tags: dict[str, dict] = {}
        if self.tag_filter and lbs:
            names = [lb["LoadBalancerName"] for lb in lbs]
            for k in range(0, len(names), 20):
                for d in elb.describe_tags(LoadBalancerNames=names[k:k + 20]).get("TagDescriptions", []):
                    tags[d["LoadBalancerName"]] = _tags(d.get("Tags"))
        p = self.prices.region(region)
        for lb in lbs:
            name, dns = lb["LoadBalancerName"], _norm_dns(lb.get("DNSName", ""))
            self.live_lb_dns.add(dns)  # exists today: records to it are "doomed", not dangling
            if not self._old(lb.get("CreatedTime")) or not self._match(tags.get(name, {})):
                continue
            instances = lb.get("Instances", [])
            if instances:
                states = elb.describe_instance_health(LoadBalancerName=name).get("InstanceStates", [])
                if any(st.get("State") == "InService" for st in states):
                    continue
                reason = f"none of its {len(instances)} registered instance(s) is InService"
            else:
                reason = "no registered instances"
            cost = p.load_balancer("classic")
            note = "classic load balancer hourly charge, no data"
            if cost is not None and lb.get("Scheme") == "internet-facing":
                n = max(1, len(lb.get("AvailabilityZones", [])))
                cost += n * (p.public_ipv4() or 0)
                note += f" + {n} public IPv4"
            item = Item("classic_elb", region, name, name, reason, cost, note,
                        commands=[_q("aws", "elb", "delete-load-balancer", "--load-balancer-name", name,
                                     "--region", region)],
                        created=_iso(lb.get("CreatedTime")), tags=tags.get(name, {}))
            self._classic_items[name] = item
            self.items.append(item)
            self.doomed_dns[dns] = name

    # --- Elastic Beanstalk --------------------------------------------------------

    def _beanstalk(self, region):
        eb = self.client("elasticbeanstalk", region)
        envs = list(self._pages(eb, "describe_environments", "Environments", IncludeDeleted=False))
        live = [e for e in envs if e.get("Status") not in ("Terminated", "Terminating")]
        doomed_by_app: dict[str, list[bool]] = {}
        for e in live:
            for host in (e.get("CNAME"), e.get("EndpointURL")):
                if host and EB_DNS.search(_norm_dns(host)):
                    self.live_eb_dns.add(_norm_dns(host))
            tags = _tags(eb.list_tags_for_resource(ResourceArn=e["EnvironmentArn"]).get("ResourceTags")) \
                if self.tag_filter and e.get("EnvironmentArn") else {}
            doomed = self._old(e.get("DateUpdated")) and self._match(tags)
            doomed_by_app.setdefault(e["ApplicationName"], []).append(doomed)
            if not doomed:
                continue
            cost, parts = self._eb_cost(eb, e["EnvironmentId"], region)
            item = Item(
                "eb_environment", region, e["EnvironmentId"], e["EnvironmentName"],
                f"environment status {e.get('Status')}, health {e.get('Health')}, last updated before the cutover",
                cost, parts,
                # A Green env may still be serving traffic that simply has not needed a deploy.
                action="delete" if e.get("Health") in ("Grey", "Red") else "verify",
                commands=[_q("aws", "elasticbeanstalk", "terminate-environment", "--environment-id",
                             e["EnvironmentId"], "--region", region)],
                created=_iso(e.get("DateCreated")), tags=tags)
            self.items.append(item)
            if e.get("CNAME"):
                self.doomed_dns[_norm_dns(e["CNAME"])] = e["EnvironmentId"]
        for app in eb.describe_applications().get("Applications", []):
            name = app["ApplicationName"]
            flags = doomed_by_app.get(name, [])
            tags = _tags(eb.list_tags_for_resource(ResourceArn=app["ApplicationArn"]).get("ResourceTags")) \
                if self.tag_filter and app.get("ApplicationArn") else {}
            if not all(flags) or not self._old(app.get("DateUpdated")) or not self._match(tags):
                continue
            env_ids = [i.id for i in self.items if i.kind == "eb_environment" and i.region == region
                       and i.id in {e["EnvironmentId"] for e in live if e["ApplicationName"] == name}]
            self.items.append(Item(
                "eb_application", region, name, name,
                "no live environments" if not flags else "every live environment is in this plan",
                0.0, "applications are free; stored application versions in S3 are not counted",
                commands=[_q("aws", "elasticbeanstalk", "delete-application", "--application-name", name,
                             "--region", region)],
                depends_on=env_ids, created=_iso(app.get("DateCreated")), tags=tags))

    def _eb_cost(self, eb, env_id: str, region: str) -> tuple[float | None, str]:
        res = eb.describe_environment_resources(EnvironmentId=env_id).get("EnvironmentResources", {})
        total, unknown, parts = 0.0, [], []
        for inst in res.get("Instances", []):
            itype = self._instances.get(inst["Id"])
            c = self.prices.region(region).ec2(itype) if itype else None
            if c is None:
                unknown.append(inst["Id"] + (f" ({itype})" if itype else ""))
            else:
                total += c
                parts.append(itype)
        for lb in res.get("LoadBalancers", []):
            known = self._lb_by_name.get(lb["Name"])
            classic = lb["Name"] in self._classic_by_name
            kind = "classic" if classic else (known.get("Type", "application") if known else "application")
            c = self.prices.region(region).load_balancer(kind)
            total += c or 0
            parts.append("classic load balancer" if classic else "load balancer" if known
                         else "load balancer (not found, priced as ALB)")
            # terminate-environment removes this LB; do not count or delete it twice
            for dup in (self._elb_items.pop(lb["Name"], None), self._classic_items.pop(lb["Name"], None)):
                if dup in self.items:
                    self.items.remove(dup)
        note = "EC2 + load balancer hourly: " + (", ".join(parts) or "no resources")
        if unknown:
            note += f"; not priced: {', '.join(unknown)} (add to prices.json)"
        return total, note

    # --- ECS ------------------------------------------------------------------------

    def _ecs(self, region):
        ecs = self.client("ecs", region)
        for cluster in self._pages(ecs, "list_clusters", "clusterArns"):
            arns = list(self._pages(ecs, "list_services", "serviceArns", cluster=cluster))
            for i in range(0, len(arns), 10):
                for s in ecs.describe_services(cluster=cluster, services=arns[i:i + 10], include=["TAGS"]).get("services", []):
                    tags = _tags(s.get("tags"), "key", "value")
                    if (s.get("status") != "ACTIVE" or s.get("desiredCount", 0) != 0
                            or not self._old(s.get("createdAt")) or not self._match(tags)):
                        continue
                    self.items.append(Item(
                        "ecs_service", region, s["serviceArn"], s["serviceName"], "desired count is 0",
                        0.0, "no running tasks; it still pins its target group and task definition",
                        commands=[_q("aws", "ecs", "delete-service", "--cluster", cluster, "--service",
                                     s["serviceName"], "--region", region)],
                        created=_iso(s.get("createdAt")), tags=tags))

    # --- RDS ----------------------------------------------------------------------------

    def _rds(self, region):
        rds = self.client("rds", region)
        dbs = list(self._pages(rds, "describe_db_instances", "DBInstances"))
        live_ids = {db["DBInstanceIdentifier"] for db in dbs}
        cands, aurora = [], 0
        for db in dbs:
            if db.get("DBClusterIdentifier"):
                aurora += 1  # Aurora is billed per cluster: not checked here
                continue
            tags = _tags(db.get("TagList"))
            if not self._old(db.get("InstanceCreateTime")) or not self._match(tags):
                continue
            if db.get("DBInstanceStatus") in ("stopped", "available"):
                cands.append((db, tags))
        if aurora:
            self.notes.append(f"{aurora} Aurora cluster member(s) in {region} were not checked (clusters are not "
                              "covered yet).")
        available = [db["DBInstanceIdentifier"] for db, _ in cands if db.get("DBInstanceStatus") == "available"]
        conns = None
        if available:
            try:
                conns = self._metric(region, "AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", available,
                                     "Maximum")
            except ReadOnlyViolation:
                raise
            except (ClientError, BotoCoreError) as e:
                self.errors.append({"collector": "rds_connections", "region": region, "error_code": _code(e)})
        p = self.prices.region(region)
        for db, tags in cands:
            did, status = db["DBInstanceIdentifier"], db.get("DBInstanceStatus")
            if status == "available":
                if conns is None:
                    continue  # no evidence either way: never guess about a database
                peak, points = conns.get(did, (0.0, 0))
                if peak > 0 or not points:
                    continue
                reason = "no connections since the cutover (peak DatabaseConnections 0)"
            else:
                reason = "stopped; AWS starts a stopped instance again after 7 days, and compute bills again"
            multi = bool(db.get("MultiAZ"))
            storage = p.rds_storage(db.get("StorageType", ""), int(db.get("AllocatedStorage", 0)), multi)
            compute = p.rds_instance(db.get("DBInstanceClass", ""), db.get("Engine", ""), multi)
            parts, cost = [], 0.0
            if storage is not None:
                cost += storage
                parts.append(f"{db.get('AllocatedStorage')} GB {db.get('StorageType')} storage")
            else:
                parts.append(f"{db.get('StorageType')} storage not priced")
            if status == "available":
                if compute is not None:
                    cost += compute
                    parts.append(f"{db.get('DBInstanceClass')} {db.get('Engine')} hours")
                else:
                    parts.append(f"{db.get('DBInstanceClass')} {db.get('Engine')} not priced")
            note = ", ".join(parts) + (" (Multi-AZ, x2)" if multi else "") + "; backups and I/O not counted"
            final = f"{did}-final-{self.now.strftime('%Y%m%d')}"
            if db.get("DeletionProtection"):
                reason += "; deletion protection is on: turn it off with modify-db-instance first"
            self.items.append(Item(
                "rds_instance", region, did, did, reason, cost, note,
                action="verify",  # a database is never deleted on metrics alone
                commands=[_q("aws", "rds", "delete-db-instance", "--db-instance-identifier", did,
                             "--final-db-snapshot-identifier", final, "--region", region)],
                created=_iso(db.get("InstanceCreateTime")), tags=tags))
        for snap in self._pages(rds, "describe_db_snapshots", "DBSnapshots", SnapshotType="manual"):
            sid = snap["DBSnapshotIdentifier"]
            tags = _tags(snap.get("TagList"))
            if not self._old(snap.get("SnapshotCreateTime")) or not self._match(tags):
                continue
            src = snap.get("DBInstanceIdentifier")
            if src in live_ids:
                action, reason = "delete", f"manual snapshot of {src} taken before the cutover; {src} has newer backups"
            else:
                action, reason = "verify", (f"manual snapshot of {src}, which no longer exists: it may be the last "
                                            "copy of that database (keep one, or export it to S3 first)")
            gb = float(snap.get("AllocatedStorage", 0))
            self.items.append(Item(
                "rds_snapshot", region, sid, sid, reason, p.rds_snapshot(gb),
                "allocated size at backup storage price; billed size is smaller (incremental), so an upper bound",
                action=action,
                commands=[_q("aws", "rds", "delete-db-snapshot", "--db-snapshot-identifier", sid, "--region", region)],
                created=_iso(snap.get("SnapshotCreateTime")), tags=tags))

    # --- CloudWatch Logs ------------------------------------------------------------

    def _logs(self, region):
        logs = self.client("logs", region)
        for g in self._pages(logs, "describe_log_groups", "logGroups"):
            name = g["logGroupName"]
            if not self._old(g.get("creationTime")):
                continue
            streams = logs.describe_log_streams(logGroupName=name, orderBy="LastEventTime", descending=True,
                                                limit=1).get("logStreams", [])
            last = streams[0].get("lastEventTimestamp") if streams else None
            if last is not None and not self._old(last):
                continue
            tags = {}
            if self.tag_filter:
                arn = g.get("logGroupArn") or (g.get("arn") or "").removesuffix(":*")
                tags = logs.list_tags_for_resource(resourceArn=arn).get("tags", {})
                if not self._match(tags):
                    continue
            item = Item(
                "log_group", region, name, name,
                f"no events since {_iso(last)}" if last else "no events at all",
                self.prices.region(region).log_storage(int(g.get("storedBytes", 0))),
                f"{int(g.get('storedBytes', 0)) / 1e9:.2f} GB stored",
                commands=[_q("aws", "logs", "delete-log-group", "--log-group-name", name, "--region", region)],
                created=_iso(g.get("creationTime")), tags=tags)
            if g.get("deletionProtectionEnabled"):
                item.action = "verify"
                item.reason += "; deletion protection is on, turn it off first"
            self.items.append(item)

    # --- Route 53 -------------------------------------------------------------------

    def _route53(self, _region):
        r53 = self.client("route53", "us-east-1")
        scanned = set(self.regions)
        unchecked = 0
        for zone in self._pages(r53, "list_hosted_zones", "HostedZones"):
            zid = zone["Id"].split("/")[-1]
            for rr in self._pages(r53, "list_resource_record_sets", "ResourceRecordSets", HostedZoneId=zid):
                verdict = self._judge_record(rr, scanned)
                if verdict == "unchecked":
                    unchecked += 1
                if not isinstance(verdict, tuple):
                    continue
                action, reason, depends = verdict
                batch = {"Comment": "sweeper teardown", "Changes": [{"Action": "DELETE", "ResourceRecordSet": rr}]}
                rid = f"{zid}/{rr['Name']}/{rr['Type']}" + (f"/{rr['SetIdentifier']}" if rr.get("SetIdentifier") else "")
                self.items.append(Item(
                    "route53_record", "global", rid, f"{rr['Name']} {rr['Type']} ({zone['Name']})", reason, 0.0,
                    "records are free; dangling ones are a subdomain-takeover risk",
                    action=action, depends_on=depends,
                    commands=[_q("aws", "route53", "change-resource-record-sets", "--hosted-zone-id", zid,
                                 "--change-batch", json.dumps(batch, separators=(",", ":"), sort_keys=True))]))
        if unchecked:
            self.notes.append(f"{unchecked} Route 53 record(s) point at load balancers or Beanstalk environments in "
                              "regions that were not scanned; pass those regions with --region to check them.")
        if self.ip_ranges is None:
            self.notes.append("A/AAAA records with plain IPs were not checked; pass --ip-ranges ip-ranges.json "
                              "(https://ip-ranges.amazonaws.com/ip-ranges.json) to flag IPs in AWS EC2 space that this "
                              "account no longer owns.")

    def _judge_record(self, rr: dict, scanned: set):
        """('delete'|'verify', reason, depends) for a record to remove, 'unchecked', or None."""
        targets = []
        if rr.get("AliasTarget"):
            targets.append(_norm_dns(rr["AliasTarget"]["DNSName"]))
        elif rr.get("Type") == "CNAME":
            targets += [_norm_dns(r["Value"]) for r in rr.get("ResourceRecords", [])]
        elif rr.get("Type") in ("A", "AAAA") and self.ip_ranges is not None:
            return self._judge_ips(rr)
        for t in targets:
            m_elb, m_eb = ELB_DNS.search(t), EB_DNS.search(t)
            if not (m_elb or m_eb):
                continue
            region = (m_elb or m_eb).group(1)
            if region not in scanned:
                return "unchecked"
            if t in self.doomed_dns:
                return ("verify", f"points at {t}, which this plan tears down: delete the record first",
                        [self.doomed_dns[t]])
            live = self.live_lb_dns if m_elb else self.live_eb_dns
            if t not in live:
                what = "load balancer" if m_elb else "Elastic Beanstalk environment"
                return ("delete", f"points at {t}: no such {what} exists any more (dangling)", [])
        return None

    def _judge_ips(self, rr: dict):
        for r in rr.get("ResourceRecords", []):
            ip = r["Value"]
            if ip in self.doomed_ips:
                return ("verify", f"points at {ip}, an Elastic IP this plan releases", [self.doomed_ips[ip]])
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if ip not in self.owned_ips and any(addr in n for n in self.ip_ranges if n.version == addr.version):
                return ("verify", f"points at {ip}: in AWS EC2 address space but not owned by this account in the "
                                  "scanned regions (likely a released Elastic IP)", [])
        return None
