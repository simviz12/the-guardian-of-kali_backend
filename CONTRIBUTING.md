# Contributing to The Guardian of Kali — Backend

To maintain clean code quality and full auditability, all contributions must strictly adhere to the following workflow and standards.

## Language Rule
All source code, identifiers, comments, commit messages, pull requests, and documentation must be in **English**.

## Branch Strategy
Direct pushes to `main` are disabled. All work must be conducted in dedicated branches and merged via Pull Requests.

Branch naming standard:
- `feature/<short-name>`: New capabilities, endpoints, or layers.
- `fix/<short-name>`: Bug fixes or error handling corrections.
- `chore/<short-name>`: Tooling, dependency updates, or repository maintenance.
- `test/<short-name>`: Adding or modifying test suites.
- `docs/<short-name>`: Documentation, guides, or architectural records.

## Conventional Commits
All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification:

- `feat:` Adds a new feature.
- `fix:` Fixes a bug.
- `test:` Adds or updates tests.
- `docs:` Changes documentation only.
- `chore:` Changes that do not modify src or test files.
- `refactor:` Code changes that neither fix bugs nor add features.

### Workflow Example:
```bash
git checkout -b feature/policy-risk-classifier
git add .
git commit -m "feat: add risk classification logic to policy engine"
git push -u origin feature/policy-risk-classifier
# Open a Pull Request on GitHub to merge into main
```
