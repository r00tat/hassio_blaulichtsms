# Automated Changelog & Release with release-please

**Date:** 2026-04-16
**Branch:** `feature/release-please-changelog`

## Goal

Generate `CHANGELOG.md` automatically from Conventional Commits, bump
`custom_components/blaulichtsms/manifest.json` on every release, commit both
back to `main` as part of the release, and surface the changelog to users
through the GitHub Release body (which HACS displays in its update dialog).

## Approach

Use [release-please](https://github.com/googleapis/release-please) in
`release-type: simple` mode. On every push to `main` the action maintains a
"release PR" that:

- updates `CHANGELOG.md` with new Conventional-Commit entries,
- bumps `.version` in `custom_components/blaulichtsms/manifest.json`
  (via `extra-files` with JSON-path updater),
- bumps the tracked version in `.release-please-manifest.json`.

Merging the release PR creates the Git tag and the GitHub Release. The
release body is what HACS shows when users click *Update*. The existing
`release.yml` workflow continues to build the ZIP on `release: published`,
but no longer needs to rewrite `manifest.json` itself (release-please already
did it pre-tag).

## Bootstrap

The last real release is tag `0.3.5`, but `manifest.json` on `main` still
reads `0.3.4` (the bump was never merged back after the 0.3.5 release). The
bootstrap PR therefore:

- sets `.release-please-manifest.json` to `0.3.5`,
- corrects `manifest.json` to `0.3.5` in a non-release `chore:` change.

The first real release-please PR after merging feature work (e.g. the
`new_alarm_active` sensor) will propose `0.4.0` because of the `feat:`
commits on that work.

## SemVer

Default release-please behaviour: `feat` → minor, `fix`/`perf`/`refactor` →
patch, `BREAKING CHANGE`/`!` → major. `chore`/`ci`/`test`/`build`/`style`
are hidden in the changelog and do not trigger a release.

## Dependabot

`.github/dependabot.yml` is extended with
`commit-message: { prefix: 'fix', include: 'scope' }` for both
`github-actions` and `pip` ecosystems. Dependabot commits then look like
`fix(deps): bump X from Y to Z` and trigger a patch release. Weekly grouping
is already configured, so at most one Dependabot release PR per ecosystem
per week.

## File changes

| Path | Action |
|---|---|
| `.github/workflows/release-please.yml` | new |
| `release-please-config.json` | new |
| `.release-please-manifest.json` | new (`{".": "0.3.5"}`) |
| `CHANGELOG.md` | new (stub) |
| `.github/workflows/release.yml` | remove `yq` bump step |
| `.github/dependabot.yml` | add `commit-message.prefix: 'fix'` for both ecosystems |
| `custom_components/blaulichtsms/manifest.json` | `0.3.4` → `0.3.5` |
| `CLAUDE.md` | document release flow via release-please |

## Validation

No local test harness — first real run is the smoke test:

1. Merge this PR into `main`.
2. release-please-action runs and opens its first release PR.
3. Verify the PR proposes the expected version bump and lists the expected
   commits in its changelog preview.
4. Merge the release PR when ready → tag + GitHub Release are created →
   existing `release.yml` builds and uploads the ZIP.
