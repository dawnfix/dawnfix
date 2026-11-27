"""Rebuild src/dawnfix_sweeper/prices.json from the AWS Price List bulk API.

Maintainer tool, never run by the sweeper itself (which never touches the network). The
offer files are public and unauthenticated; each is streamed as CSV and only the rows the
sweeper prices are kept, so nothing large lands on disk.

    python3 -I tools/refresh_prices.py fetch RAW_DIR [REGION ...]   # network: 5 offers x regions
    python3 -I tools/refresh_prices.py build RAW_DIR > src/dawnfix_sweeper/prices.json

AmazonEC2 is the big one (about 300 MB of CSV for us-east-1, less elsewhere).
"""
import csv
import io
import json
import re
import sys
import urllib.request

BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{offer}/current/{region}/index.csv"
PREFIX = re.compile(r"^[A-Z]{2,4}\d?-(?=[A-Za-z])")

EC2_TYPES = {
    "t3.nano", "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge", "t3.2xlarge",
    "t3a.micro", "t3a.small", "t3a.medium", "t3a.large", "t3a.xlarge",
    "t4g.nano", "t4g.micro", "t4g.small", "t4g.medium", "t4g.large", "t4g.xlarge",
    "t2.micro", "t2.small", "t2.medium", "t2.large",
    "m5.large", "m5.xlarge", "m5.2xlarge", "m6i.large", "m6i.xlarge", "m6g.large", "m6g.xlarge",
    "m7i.large", "m7g.large", "m7g.xlarge",
    "c5.large", "c5.xlarge", "c6i.large", "c6g.large", "c7g.large",
    "r5.large", "r5.xlarge", "r6i.large", "r6g.large", "r7g.large",
}
RDS_TYPES = {
    "db.t3.micro", "db.t3.small", "db.t3.medium", "db.t3.large", "db.t4g.micro", "db.t4g.small",
    "db.t4g.medium", "db.t4g.large", "db.m5.large", "db.m5.xlarge", "db.m6g.large", "db.m6g.xlarge",
    "db.m6i.large", "db.m7g.large", "db.r5.large", "db.r6g.large", "db.r6g.xlarge", "db.r7g.large",
}
EBS_KEEP = {
    "EBS:VolumeUsage.gp3", "EBS:VolumeUsage.gp2", "EBS:VolumeUsage.piops", "EBS:VolumeUsage.io2",
    "EBS:VolumeUsage.st1", "EBS:VolumeUsage.sc1", "EBS:VolumeUsage",
    "EBS:VolumeP-IOPS.piops", "EBS:VolumeP-IOPS.io2", "EBS:VolumeP-IOPS.gp3", "EBS:VolumeP-Throughput.gp3",
    "EBS:SnapshotUsage", "NatGateway-Hours", "NatGateway-Bytes",
}


def rows(offer, region):
    req = urllib.request.Request(BASE.format(offer=offer, region=region), headers={"User-Agent": "price-refresh"})
    with urllib.request.urlopen(req, timeout=600) as r:
        text = io.TextIOWrapper(r, encoding="utf-8", newline="")
        meta = {}
        for _ in range(5):
            line = next(csv.reader([text.readline()]))
            meta[line[0]] = line[1] if len(line) > 1 else ""
        reader = csv.DictReader(text)
        yield meta
        yield from reader


def keep(offer, row):
    if row.get("TermType") != "OnDemand" or row.get("Unit") in ("Quantity",):
        return None
    ut = PREFIX.sub("", row.get("usageType", ""))
    if offer == "AmazonEC2":
        if ut in EBS_KEEP:
            return ut
        if ut.startswith("BoxUsage:") and row.get("Instance Type") in EC2_TYPES \
                and row.get("Operating System") == "Linux" and row.get("Tenancy") == "Shared" \
                and row.get("Pre Installed S/W") == "NA" and row.get("CapacityStatus") == "Used" \
                and row.get("License Model") in ("No License required", ""):
            return ut
        return None
    if offer == "AmazonVPC":
        return ut if ut.startswith("PublicIPv4:") else None
    if offer == "AWSELB":
        return f"{ut}|{row.get('operation')}" if ut == "LoadBalancerUsage" else None
    if offer == "AmazonCloudWatch":
        return ut if ut == "TimedStorage-ByteHrs" else None
    if offer == "AmazonRDS":
        if ut.startswith("InstanceUsage:") and row.get("Instance Type") in RDS_TYPES \
                and row.get("Database Engine") in ("MySQL", "PostgreSQL") \
                and row.get("Deployment Option") == "Single-AZ":
            return f"{ut}|{row.get('Database Engine')}"
        if ut in ("RDS:GP2-Storage", "RDS:GP3-Storage", "RDS:ChargedBackupUsage"):
            return ut
        return None
    return None


OFFERS = ("AmazonEC2", "AmazonVPC", "AWSELB", "AmazonCloudWatch", "AmazonRDS")
# The regions Dawnfix Logbill prices (logbill/src/logbill/prices.json).
REGIONS = ("us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "eu-central-1", "eu-west-1",
           "eu-west-2", "eu-west-3", "eu-north-1", "eu-south-1", "ap-south-1", "ap-southeast-1", "ap-southeast-2",
           "ap-northeast-1", "ap-northeast-2", "sa-east-1")


def fetch(out_dir, offer, regions):
    for region in regions:
        it = rows(offer, region)
        meta = next(it)
        found = {}
        for row in it:
            k = keep(offer, row)
            if k is None:
                continue
            found.setdefault(k, []).append({
                "usd": row.get("PricePerUnit"), "unit": row.get("Unit"), "begin": row.get("StartingRange"),
                "end": row.get("EndingRange"), "desc": row.get("PriceDescription"),
                "usagetype": row.get("usageType"), "effective": row.get("EffectiveDate"),
            })
        with open(f"{out_dir}/{offer}-{region}.json", "w") as f:
            json.dump({"meta": meta, "rows": found}, f, indent=1, sort_keys=True)
        print(offer, region, meta.get("Publication Date"), len(found), file=sys.stderr, flush=True)


# --- build -------------------------------------------------------------------------------

# sweeper key -> (offer, usage type without region prefix, unit shown in the table, scale)
SIMPLE = {
    "ebs_gb_month.gp3": ("AmazonEC2", "EBS:VolumeUsage.gp3", "GB-month"),
    "ebs_gb_month.gp2": ("AmazonEC2", "EBS:VolumeUsage.gp2", "GB-month"),
    "ebs_gb_month.io1": ("AmazonEC2", "EBS:VolumeUsage.piops", "GB-month"),
    "ebs_gb_month.io2": ("AmazonEC2", "EBS:VolumeUsage.io2", "GB-month"),
    "ebs_gb_month.st1": ("AmazonEC2", "EBS:VolumeUsage.st1", "GB-month"),
    "ebs_gb_month.sc1": ("AmazonEC2", "EBS:VolumeUsage.sc1", "GB-month"),
    "ebs_gb_month.standard": ("AmazonEC2", "EBS:VolumeUsage", "GB-month (magnetic)"),
    "ebs_iops_month.io1": ("AmazonEC2", "EBS:VolumeP-IOPS.piops", "provisioned IOPS-month"),
    "ebs_iops_month.io2": ("AmazonEC2", "EBS:VolumeP-IOPS.io2", "provisioned IOPS-month (first tier, up to 32k)"),
    "ebs_iops_month.gp3": ("AmazonEC2", "EBS:VolumeP-IOPS.gp3", "IOPS-month above 3,000"),
    "ebs_throughput_month.gp3": ("AmazonEC2", "EBS:VolumeP-Throughput.gp3", "MiB/s-month above 125"),
    "snapshot_gb_month": ("AmazonEC2", "EBS:SnapshotUsage", "GB-month (standard tier)"),
    "nat_gateway_hour": ("AmazonEC2", "NatGateway-Hours", "hour per NAT gateway"),
    "nat_gateway_gb": ("AmazonEC2", "NatGateway-Bytes", "GB processed"),
    "public_ipv4_hour": ("AmazonVPC", "PublicIPv4:IdleAddress", "hour per public IPv4 address, idle or in use"),
    "alb_hour": ("AWSELB", "LoadBalancerUsage|LoadBalancing:Application", "hour (excludes LCU)"),
    "nlb_hour": ("AWSELB", "LoadBalancerUsage|LoadBalancing:Network", "hour (excludes NLCU)"),
    "gwlb_hour": ("AWSELB", "LoadBalancerUsage|LoadBalancing:Gateway", "hour (excludes GLCU)"),
    "clb_hour": ("AWSELB", "LoadBalancerUsage|LoadBalancing", "hour, classic (excludes data)"),
    "log_storage_gb_month": ("AmazonCloudWatch", "TimedStorage-ByteHrs", "GB-month archived"),
    "rds_storage_gb_month.gp2": ("AmazonRDS", "RDS:GP2-Storage", "GB-month, Single-AZ"),
    "rds_storage_gb_month.gp3": ("AmazonRDS", "RDS:GP3-Storage", "GB-month, Single-AZ"),
    "rds_backup_gb_month": ("AmazonRDS", "RDS:ChargedBackupUsage", "GB-month above the free allocation"),
}
SCALE = {"EBS:VolumeP-Throughput.gp3": 1 / 1024}  # the offer prices GiBps-month


def _pick(rows, key):
    rows = [r for r in rows if (r.get("begin") or "0") in ("0", "0.0") and "Trust Store" not in (r.get("desc") or "")]
    if key.startswith("rds_storage"):
        own = [r for r in rows if "MySQL" in r["desc"] or "PostgreSQL" in r["desc"]]
        rows = own or rows
    vals = sorted({float(r["usd"]) for r in rows})
    if not vals:
        return None
    if len(vals) > 1:
        print(f"note: {key}: several prices {vals}, taking the lowest", file=sys.stderr)
    return vals[0]


def build(raw_dir):
    import glob
    import os

    raw = {}
    for f in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        offer, region = os.path.basename(f)[:-5].split("-", 1)
        raw[(offer, region)] = json.load(open(f))
    regions = [r for r in REGIONS if all((o, r) in raw for o in OFFERS)]
    offers = {}
    for o in OFFERS:
        pubs = sorted({raw[(o, r)]["meta"].get("Publication Date", "") for r in regions})
        offers[o] = {"url": BASE.format(offer=o, region="<region>"), "publication_date": pubs[-1][:10],
                     "version": raw[(o, regions[0])]["meta"].get("Version")}
    prices = {}
    for key, (offer, ut, unit) in SIMPLE.items():
        by_region = {}
        for r in regions:
            v = _pick(raw[(offer, r)]["rows"].get(ut, []), key)
            if v is not None:
                by_region[r] = round(v * SCALE.get(ut, 1), 10)
        prices[key] = {"unit": unit, "offer": offer, "usage_type": ut.split("|")[0], "regions": by_region}
    ec2_types = sorted({k.split(":", 1)[1] for (o, _), d in raw.items() if o == "AmazonEC2"
                        for k in d["rows"] if k.startswith("BoxUsage:")})
    for t in ec2_types:
        by_region = {r: _pick(raw[("AmazonEC2", r)]["rows"].get(f"BoxUsage:{t}", []), t) for r in regions}
        prices[f"ec2_hour.{t}"] = {"unit": "hour, Linux on-demand, shared tenancy", "offer": "AmazonEC2",
                                   "usage_type": f"BoxUsage:{t}",
                                   "regions": {r: v for r, v in by_region.items() if v is not None}}
    for engine, family in (("MySQL", "mysql"), ("PostgreSQL", "postgres")):
        classes = sorted({k.split("|")[0].split(":", 1)[1] for (o, _), d in raw.items() if o == "AmazonRDS"
                          for k in d["rows"] if k.startswith("InstanceUsage:") and k.endswith("|" + engine)})
        for c in classes:
            full = c[:-3] + ".xlarge" if c.endswith(".xl") else c
            by_region = {r: _pick(raw[("AmazonRDS", r)]["rows"].get(f"InstanceUsage:{c}|{engine}", []), c)
                         for r in regions}
            prices[f"rds_hour.{family}.{full}"] = {"unit": f"hour, {engine} Single-AZ on-demand", "offer": "AmazonRDS",
                                                   "usage_type": f"InstanceUsage:{c}",
                                                   "regions": {r: v for r, v in by_region.items() if v is not None}}
    return {
        "as_of": max(o["publication_date"] for o in offers.values()),
        "default_region": "us-east-1",
        "regions": regions,
        "hours_per_month": 730,
        "note": ("On-demand list prices from the AWS Price List bulk API (offer files named under source.offers, "
                 "publication dates there); the tool never fetches prices live. Estimates only: no Savings Plans, "
                 "reserved capacity, credits, free tier, LCU or data charges. Still estimated by rule, not by a "
                 "price: Multi-AZ RDS is counted as twice Single-AZ, snapshot sizes are upper bounds, and a region "
                 "missing here is priced at us-east-1."),
        "source": {"api": "AWS Price List bulk API (public, unauthenticated offer files, CSV)",
                   "retrieved": RETRIEVED, "offers": offers},
        "prices": prices,
    }


RETRIEVED = None


def main():
    global RETRIEVED
    cmd, raw_dir, *rest = sys.argv[1:]
    if cmd == "fetch":
        for offer in OFFERS:
            fetch(raw_dir, offer, rest or REGIONS)
    elif cmd == "build":
        from datetime import date

        RETRIEVED = date.today().isoformat()
        doc = build(raw_dir)
        prices = doc.pop("prices")
        head = json.dumps(doc, indent=2)[:-2]  # one price entry per line keeps diffs readable
        body = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v, separators=(', ', ': '))}" for k, v in prices.items())
        sys.stdout.write(f"{head},\n  \"prices\": {{\n{body}\n  }}\n}}\n")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
