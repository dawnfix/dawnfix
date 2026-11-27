"""Every product name, org and URL in one place:
renaming the product is a change to this file only (docs aside)."""

PRODUCT = "Dawnfix Logbill"   # shown in the report title and CLI banner
SHORT = "Logbill"
CLI = "logbill"                 # console script name (also in pyproject.toml [project.scripts])
SUITE = "Dawnfix"
PITCH_PRODUCT = SUITE           # what the closing line of the report points at
PITCH_LINE = (
    f"{SUITE} watches these same logs for new errors and opens a draft PR with a failing "
    "test and the fix, from your own GitHub Actions. Free and source available. Hosted "
    "status page and email alerts: Dawnfix Enterprise."
)
LICENCE = "Source available under FSL-1.1-ALv2"
ORG = "dawnfix"                # GitHub org
SITE_DOMAIN = "dawnfix.dev"   # printed as plain text; the report links nowhere
SITE_URL = f"https://{SITE_DOMAIN}"
PITCH_PATH = "/docs/setup"
PITCH_URL = f"{SITE_URL}{PITCH_PATH}"          # the pitch's link (JSON)
PITCH_TEXT = f"{SITE_DOMAIN}{PITCH_PATH}"      # the same, as plain text in the HTML report
PAGE_URL = f"{SITE_URL}/logbill"                 # the hosted Logbill page
# Where the free workflow the pitch points at lives (the JSON's `install`).
PITCH_INSTALL = f"templates/github/workflows/dawnfix.yml in github.com/{ORG}/{ORG}"
REPORT_SCHEMA = "logbill.report/1"
