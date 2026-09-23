# Focused visual validation playbook

Use this reference only when a UI or live Herdr behavior cannot be verified by the normal Rust
product tests. Prefer the Docker sandbox so validation cannot touch the user's active board state.

## Normal product checks

```bash
./scripts/sandbox.sh prepare
./scripts/sandbox.sh gates
```

The gate set is intentionally small: formatting, clippy, and Rust product tests. Do not add
repository-policy, documentation-contract, source-shape, or duplicate invariant tests.

## Interactive validation

```bash
./scripts/sandbox.sh prepare
./scripts/sandbox.sh tui
```

The sandbox owns its Herdr server, board daemon, database, socket, workspaces, and provider state.
Never point an interactive validation command at a user's live session or workspace.

For a provider run, require the explicit network opt-in and use only the provider needed for the
behavior under test:

```bash
./scripts/sandbox.sh agent --provider <pi|codex|antigravity> --allow-network
```

Provider runs can incur cost. Run one focused attempt; do not retry or fan out unless the user asks.

## Evidence and cleanup

```bash
./scripts/sandbox.sh artifacts
./scripts/sandbox.sh down
```

Use `./scripts/sandbox.sh reset --all` only when the sandbox caches or disposable state must be
discarded. The wrapper scopes cleanup to resources created for the current worktree.
