"""Brand, org and URLs, in one place.

Nothing else in the package may hard-code these strings (the README, iam/ Sids and
prompts/sweeper.md repeat a few; grep for them on a rename).
"""
BRAND = "Dawnfix Sweeper"
TOOL = "sweeper"
ORG = "Dawnfix"                     # who makes it
LICENCE = "Source available under FSL-1.1-ALv2"
GITHUB_ORG = "dawnfix"
SITE_URL = "https://dawnfix.dev"
HOMEPAGE = f"{SITE_URL}/sweeper"
ISSUES_URL = f"https://github.com/{GITHUB_ORG}/dawnfix/issues"
PLAN_BASENAME = "sweeper-plan"
# What the closing line points at: a cost receipt on every deploy, free in your own CI.
UPSELL = "Dawnfix Receipt"
RECEIPT_WORKFLOW = "templates/github/workflows/dawnfix-receipt.yml"
PITCH_URL = f"{SITE_URL}/receipt"


def pitch(monthly_usd: float) -> dict:
    """The closing line (plan.json carries it as `pitch`). No prices: the workflow is free."""
    lead = (f"You're paying about ${monthly_usd:,.0f}/month for leftovers." if monthly_usd >= 1
            else "No leftovers worth money this time.")
    return {"line": f"{lead} {UPSELL} catches the next one at deploy time: every deploy gets a comment with "
                    f"what it did to the AWS bill, from your own CI. Free: {RECEIPT_WORKFLOW} in the Dawnfix repo.",
            "url": PITCH_URL}
