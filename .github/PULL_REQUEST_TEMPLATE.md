<!-- Thanks. Keep it small; one change per PR lands faster than three. -->

## What

<!-- One or two sentences. Link the issue if there is one: For #123 (not Fixes or Closes; an issue stays open until the fix has shipped) -->

## Why

<!-- The problem this solves, or what a person can do afterwards that they could not before. -->

## Checks

<!-- Tick what applies; the commands are in AGENTS.md. -->

- [ ] The checks pass: `ruff check . && ruff format --check . && python -m pytest -q -m "not live"` (and `cd web && npm run check && npm run build` if the web app changed)
- [ ] New behaviour has a test; tests use `MockLLM`, no network
- [ ] If a person sees or does something differently: a line under `## [Unreleased]` in `CHANGELOG.md` (past tense, concrete, in the right section) and the page under `docs/` that describes it
- [ ] If the web app changed: the build under `dragon/server/static` is committed
- [ ] If the provider catalogue changed: `node scripts/providers-json.mjs --check` passes
- [ ] If a tool or the Sentinel changed: risk level, `assess()` summary and the approval flow are up to date
- [ ] Commits follow Conventional Commits and carry a DCO sign-off (`git commit -s`)
- [ ] No secrets, internal hostnames or personal data in the diff; no version bump
- [ ] No old project names anywhere in the diff (the brand guard job checks this)

## Screenshots

<!-- For anything visible in the web app: before / after. Delete this section otherwise. -->
