# Releasing

A release is a tag `vX.Y.Z` on this repo. `.github/workflows/release.yml` then:

1. checks that the tag, `pyproject.toml`, `cli/package.json`, every tool's version and
   `DAWNFIX_VERSION` in every workflow are the same version;
2. runs the test suites (core and each Python tool, infra, Flare, the npm package);
3. builds the PyPI package `dawnfix` (wheel and sdist) and the npm package `dawnfix`;
4. publishes both with **trusted publishing**: no npm or PyPI token is stored anywhere. Each
   registry trusts this repository, `release.yml` and one GitHub environment, and the job
   exchanges its short-lived GitHub OIDC token for an upload token. npm also gets signed
   provenance (`npm publish --provenance`);
5. moves the major tag (`v0`) to the release, **in the same workflow, after both packages
   are published**. Callers use `dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0`, and that
   workflow installs `dawnfix==<its version>` from PyPI, so `v0` must never point at a
   release whose package is not on PyPI yet. A failed publish leaves `v0` where it was. To
   move it by hand instead: `git tag -f v0 vX.Y.Z && git push -f origin v0`.

## One-time setup

### GitHub (this repo)

1. Settings > Environments: create `pypi` and `npm`. For each, under "Deployment branches
   and tags", allow tags matching `v*` only. Optionally add yourself as a required reviewer,
   so every publish waits for one click.
2. If a tag ruleset protects `v0`, let GitHub Actions bypass it (the release moves it with
   the workflow's own token, `contents: write` in that one job).

### PyPI (the project does not exist yet: a "pending publisher")

1. Sign in at https://pypi.org (2FA on), then Your account > Publishing > "Add a new
   pending publisher" > GitHub:
   - PyPI Project Name: `dawnfix`
   - Owner: `dawnfix`
   - Repository name: `dawnfix`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. The first release creates the project and turns the pending publisher into a normal
   one. Nothing else to do; never create an API token.

### npm (the first publish is manual)

npm can only trust a workflow for a package that already exists, so the very first version
of `dawnfix` is published by hand, once, before its tag is pushed. From a checkout of this
repo at the commit you will tag:

```sh
cd cli
npm ci
npm login                    # the npm account that will own the package, with 2FA
npm publish --access public  # prepack checks the bundle and copies the root LICENSE in
```

(Provenance needs GitHub's OIDC, so this one version has none. The release workflow sees
that the version is on npm already and skips it; every later version is published by the
workflow, with provenance.)

Then on https://www.npmjs.com/package/dawnfix > Settings > Trusted Publisher > GitHub Actions:

- Organization or user: `dawnfix`
- Repository: `dawnfix`
- Workflow filename: `release.yml`
- Environment name: `npm`

and under "Publishing access" choose "Require two-factor authentication and disallow
tokens". Now push the tag (below).

## Every release

1. Set the version everywhere (one command in the source repo this one is cut from; it
   also regenerates the templates and the npm bundle), run the tests, commit.
2. Tag and push:

```sh
git tag v0.4.0
git push origin v0.4.0
```

That is all: the release workflow tests, builds, publishes to PyPI and npm, and moves `v0`.
Check https://pypi.org/project/dawnfix/ and https://www.npmjs.com/package/dawnfix.

A major version (`v1.0.0`) moves `v1`, not `v0`: callers on `@v0` stay on the 0.x line.
