"""Brand, org and URLs, in one place.

Nothing else in the package may hard-code these strings (the README, iam/ Sids and
prompts/leastpriv.md repeat a few; grep for them on a rename).
"""
BRAND = "Dawnfix Leastpriv"
TOOL = "leastpriv"
ORG = "Dawnfix"                     # who makes it
GITHUB_ORG = "dawnfix"
SITE_URL = "https://dawnfix.dev"
HOMEPAGE = f"{SITE_URL}/leastpriv"
OUT_DIR = "leastpriv-out"
PITCH_URL = f"{SITE_URL}/tools"
# The closing line (report.json carries it as `pitch`). No prices: all of it is free to run.
PITCH_LINE = ("Keep it trimmed: Dawnfix runs read-only checks in your own CI, free (Parity config drift "
              "and secret inventory, the Flare Cloudflare audit, a cost receipt on every deploy), and "
              "opens draft PRs for production errors.")
