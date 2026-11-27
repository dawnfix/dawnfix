"""The stage and secret matrix: which secrets each stage may hold, and the AI settings.

Each stage refuses to run when its environment holds a secret meant for another stage, so a
CI job set up with too much fails loudly instead of quietly widening what the agent can reach.
"""
import os
import re

from .scrub import REDACT, say

# Your AI API key (Claude today), the model and the provider. The provider is fixed to claude:
# a second vendor later is code, not a rename.
AI_KEY = "DAWNFIX_AI_API_KEY"
AI_KEY_FALLBACK = "ANTHROPIC_API_KEY"  # deprecated fallback for DAWNFIX_AI_API_KEY, this release only
AI_MODEL = "DAWNFIX_AI_MODEL"
AI_MODEL_FALLBACK = "DAWNFIX_MODEL"  # deprecated fallback for DAWNFIX_AI_MODEL, this release only
AI_PROVIDER = "DAWNFIX_AI_PROVIDER"
PROVIDERS = ("claude",)
DEFAULT_MODEL = "sonnet"
AI_KEYS = (AI_KEY, AI_KEY_FALLBACK)

# The repo host token: push a branch, open a draft PR/MR or an issue. The publish stage reads
# DAWNFIX_HOST_TOKEN; the other names are refused anywhere else so a stray one is caught.
HOST_TOKEN = "DAWNFIX_HOST_TOKEN"
HOST_TOKENS = (HOST_TOKEN, "DAWNFIX_PR_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN", "GL_TOKEN",
               "BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN")
ENTERPRISE_KEY = "DAWNFIX_ENTERPRISE_KEY"
# Cloud credentials, and the means to mint them (an OIDC token, or the right to request one).
CLOUD = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_WEB_IDENTITY_TOKEN_FILE",
         "GOOGLE_APPLICATION_CREDENTIALS", "CLOUDSDK_AUTH_ACCESS_TOKEN", "GOOGLE_OAUTH_ACCESS_TOKEN")
# GITLAB_OIDC_TOKEN: the ID token the GitLab template's read job declares (id_tokens:).
OIDC = ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "BITBUCKET_STEP_OIDC_TOKEN",
        "CIRCLE_OIDC_TOKEN", "CIRCLE_OIDC_TOKEN_V2", "GITLAB_OIDC_TOKEN")
# Set by the CI system in every job, whatever the pipeline says. Never refused (the job could
# not run), never passed to the agent or to git.
AMBIENT = ("CI_JOB_TOKEN", "CI_JOB_JWT", "CI_JOB_JWT_V2", "CI_REGISTRY_PASSWORD", "CI_DEPLOY_PASSWORD",
           "CI_DEPENDENCY_PROXY_PASSWORD", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL")

# stage -> the groups it must not hold.
FORBIDDEN = {
    "read": {"the AI API key": AI_KEYS, "a repo host token": HOST_TOKENS},
    "agent": {"a repo host token": HOST_TOKENS, "cloud credentials": CLOUD, "an OIDC token": OIDC,
              "the Enterprise key": (ENTERPRISE_KEY,)},
    "publish": {"the AI API key": AI_KEYS, "cloud credentials": CLOUD, "an OIDC token": OIDC,
                "the Enterprise key": (ENTERPRISE_KEY,)},
    "report": {"the AI API key": AI_KEYS, "a repo host token": HOST_TOKENS, "cloud credentials": CLOUD},
}
# stage -> the one secret it is for (documentation and the matrix test).
NEEDS = {"read": "cloud credentials (OIDC)", "agent": AI_KEY, "publish": HOST_TOKEN, "report": ENTERPRISE_KEY}

SECRET_NAMES = AI_KEYS + HOST_TOKENS + (ENTERPRISE_KEY,) + CLOUD + OIDC + AMBIENT + (
    "DAWNFIX_PR_APP_PRIVATE_KEY",)


class StageError(Exception):
    """The stage cannot run as set up; the message says what to change."""


def register_secrets(env) -> None:
    """Every secret value in the environment is scrubbed from everything this process prints."""
    for name in SECRET_NAMES:
        REDACT.add(env.get(name, ""))


def check_stage_env(stage: str, env) -> None:
    held = []
    for what, names in FORBIDDEN[stage].items():
        present = [n for n in names if env.get(n)]
        if present:
            held.append(f"{what} ({', '.join(present)})")
    if held:
        raise StageError(
            f"the {stage} stage must not hold {'; '.join(held)}. Give this CI job only {NEEDS[stage]}: "
            "each stage runs in its own job with its own secret")


MODEL_RE = re.compile(r"^[A-Za-z0-9._:@\[\]-]{1,100}$")


def ai_settings(env) -> dict:
    """provider, model and key for the agent stage; one deprecation notice per old name used."""
    provider = env.get(AI_PROVIDER) or "claude"
    if provider not in PROVIDERS:
        raise StageError(f"{AI_PROVIDER} must be claude (the only provider today), not '{provider}'")
    key = env.get(AI_KEY, "")
    if not key and env.get(AI_KEY_FALLBACK):
        say(f"notice: the {AI_KEY_FALLBACK} name is deprecated: set {AI_KEY} (your AI API key, Claude today). "
            "This fallback goes in the next release.")
        key = env[AI_KEY_FALLBACK]
    if not key:
        raise StageError(f"no AI API key: set {AI_KEY} (your AI API key, Claude today) in this job")
    model = env.get(AI_MODEL, "")
    if not model and env.get(AI_MODEL_FALLBACK):
        say(f"notice: the {AI_MODEL_FALLBACK} name is deprecated: set {AI_MODEL}. This fallback goes in the next release.")
        model = env[AI_MODEL_FALLBACK]
    model = model or DEFAULT_MODEL
    if not MODEL_RE.match(model):
        raise StageError(f"the model must be a model name or alias, not '{model}'")
    return {"provider": provider, "model": model, "key": key}


def environ():
    return dict(os.environ)
