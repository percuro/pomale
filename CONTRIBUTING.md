# Contributing

Thanks for your interest! Bug reports, ideas and pull requests are welcome.

## Before you start

- For larger changes, open an issue or discussion first so we can agree on the approach.
- The product idea is deliberately small: checking off a habit must stay a one-second, one-tap action, and there are no points or streak drama. Features that make that harder will probably not be accepted.
- Read [docs/development.md](docs/development.md) to set up the backend, frontend and tests.

## Pull requests

- One topic per pull request, with tests for changed behaviour.
- All checks must pass: `ruff check`, `ruff format --check`, backend unit tests, `npm run lint`, `npm test`, `npm run build`, and the Playwright end-to-end tests (CI runs all of them).
- Database changes need an Alembic migration.
- English for code, comments, docs and commit messages.
- The CLA bot asks you to sign the [Contributor License Agreement](CLA.md) once, by commenting on your pull request. This is needed because the project is also licensed commercially.

## Reporting security issues

Please do not open public issues for vulnerabilities; see [SECURITY.md](SECURITY.md).

## Code of conduct

Be kind and constructive; see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
