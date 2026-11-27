"""Every brand, org and URL string in one place.

Files that cannot import Python (action.yml, examples/, iam/, README.md) repeat a few of
these strings; `tests/test_brand.py` lists them so a rename is one grep away.
"""

PRODUCT_NAME = "Dawnfix Parity"
CLI_NAME = "parity"
CONFIG_FILE = ".parity.yml"
ORG_NAME = "Dawnfix"                      # who makes it
GITHUB_ORG = "dawnfix"
ACTION_REF = f"{GITHUB_ORG}/dawnfix/parity@v0"
DOCS_URL = "https://dawnfix.dev/parity"
ASSUME_ROLE_SESSION = "dawnfix-parity"   # shows up in the customer's CloudTrail
USER_AGENT_EXTRA = "dawnfix-parity/0.1"  # appended to boto's User-Agent
# The closing line of a JSON report (carried as `pitch`): the free CI workflow, and the one
# hosted extra. No prices: Enterprise is sold by "Contact us".
CI_WORKFLOW = "templates/github/workflows/dawnfix-parity.yml"
PITCH_LINE = (f"Run this on every push and every week in your own CI, free: {CI_WORKFLOW} in the "
              f"Dawnfix repo. The weekly unread / never-rotated / orphaned secrets email is "
              "Dawnfix Enterprise.")
PITCH_URL = f"{DOCS_URL}#ci"
