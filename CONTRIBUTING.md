# Contributing to SelenePlan

Thanks for contributing to SelenePlan.

## Ground rules
- Follow the architecture and service specs in `docs/` and `services/<name>/SPEC.md`.
- Keep changes focused and small.
- Use Conventional Commits in commit messages.
- Do not commit secrets, datasets, model weights, or build artifacts.

## Development setup
1. Clone the repository.
2. Create the local environment file:
   ```bash
   cp infra/.env.example infra/.env
   ```
3. Start local dependencies:
   ```bash
   docker compose -f infra/docker-compose.yml --env-file infra/.env up -d
   ```

## Validate your changes
Run checks before opening a PR:

```bash
make lint
make typecheck
make test
```

If your change affects the web app:

```bash
cd services/web
npm ci
npm run test
```

## Pull request process
1. Create a branch from the latest default branch.
2. Implement your change with tests.
3. Update docs/contracts when API, schema, or event behavior changes.
4. Open a PR with:
   - concise summary of the change
   - testing performed
   - assumptions/limitations
5. Address review feedback and keep CI green.

## Reporting bugs and proposing features
- Use GitHub Issues with clear reproduction steps for bugs.
- Include expected vs. actual behavior and relevant logs (without secrets).

## Questions
If the spec is unclear, raise the ambiguity in your PR or issue instead of guessing implementation behavior.
