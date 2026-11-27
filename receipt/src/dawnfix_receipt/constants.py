"""Brand, org, URLs and the comment marker, in one place.

Nothing else in the package may hard-code these strings. Changing MARKER_PREFIX orphans
existing comments (the next run posts a new one instead of updating), so change it once.
"""
BRAND = "Dawnfix Receipt"
TOOL = "receipt"
ORG = "Dawnfix"                    # who makes it
SITE_URL = "https://dawnfix.dev"
HOMEPAGE = f"{SITE_URL}/receipt"
MARKER_PREFIX = "dawnfix-receipt"  # appears in <!-- dawnfix-receipt:sha=... -->
GITHUB_API = "https://api.github.com"
CE_USD_PER_REQUEST = 0.01            # https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/
