# AGENTS.md

Contributor guide for Stem Board. Stem Board is a
kanban board that dispatches AI coding agents into visible herdr panes; the single `board` binary is
TUI + daemon + CLI. Rust, cargo workspace, edition 2021, all crates share the workspace version.
Feature PRs target the long-lived `dev` branch; `main` is production (branch model:
[`docs/releasing.md`](docs/releasing.md)).

## Development workflow

Keep the normal loop small: `cargo fmt --all --check`,
`cargo clippy --workspace --all-targets --all-features -- -D warnings`, and
`cargo test --workspace --all-features`. `./scripts/sandbox.sh gates` runs that same set in an
isolated container. Use the optional `e2e/` tools only when a change genuinely needs a live Herdr
session, and never point them at user data.

## Workspace layout & crate ownership

| Crate | Owns | Never leaks into |
|---|---|---|
| `board-core` | models, `board-core::protocol` types, SQLite db + migrations, the pure column engine, prompt assembly, harness adapters, config, the blocking boardd client | herdr/tokio/ratatui specifics |
| `board-herdr` | the Herdr unix-socket client (envelope, typed workspace/tab/agent/pane/notification/session calls, event stream) | board state; no worktree API |
| `board-tui` | the ratatui app (`run()` entry), forms, snapshot tests | daemon logic |
| `board-daemon` | boardd server: run queue, dispatch, per-session herdr clients, watchers, spawner | — |
| `board-cli` | the `board` binary: clap subcommands wiring the above | business logic |

Ownership is strict: edit your crate(s) + append to root `[workspace.dependencies]`. Semantics
source of truth: `docs/protocol.md` + `docs/design.md`. Docs live in `docs/` (index: `docs/README.md`);
`schema.sql` is the fresh-schema source of truth and `board-core::db` owns upgrades. Optional live
scenarios are documented in `e2e/README.md`.

## Build and test

Tests should exercise product behavior through the smallest useful public surface. Do not add
repository-policy, documentation-contract, source-shape, or duplicated invariant tests. Ignored
tests and `e2e/` scenarios are opt-in diagnostics, not blanket merge requirements.

## Code ownership

Put new code behind the boundary that already owns the responsibility rather than growing an
entry-point file. The current stable boundaries:

  | Crate | Boundary | Owns |
  |---|---|---|
  | `board-daemon` | `ops/` | request operations; `ops/errors.rs` is the one place a domain failure becomes a protocol code, `ops/panes.rs` the caller's-own-session pane calls |
  | | `dispatch/` | queue lifecycle; `launch_plan.rs` builds the launch spec, `ownership.rs` decides what this daemon may claim |
  | | `spawner/` | launch and placement; `placement/` (alloc/geometry/race), `herdr/` (managed + configured), `error.rs` |
  | | `watchers/` | timeout/liveness/Herdr observation |
  | | `herdr_conn.rs` | the gated connect: normalize the socket path, connect, run the 0.9.0/protocol-22 check, in one place. New placement, discovery, and mutation paths go through it. The two space-resolution sites that still connect directly (`ops/cards.rs`, `dispatch/launch_plan.rs`) run the same gate inside `dispatch/space.rs`; cleanup/observation retain an ungated client only for panes this daemon already owns |
  | | `rescue.rs`, `recovery.rs`, `logging.rs`, `testkit.rs` | run rescue, per-session recovery, tracing setup, and the `cfg(test)` daemon/fake-Herdr builders |
  | `board-tui` | `app/` | the pure reducer — `state`/`effect`/`nav`/`drag` plus one module per screen |
  | | `driver/` | the effect loop (`dispatch`, `load`); `runtime.rs` owns terminal setup/teardown, `origin.rs` the Herdr-plugin origin context |
  | | `forms/`, `view/`, `widgets/` | form model, rendering, hit-testing |
  | `board-cli` | `args/` | the clap surface, split by domain; **backward compatibility is mandatory** — new spellings are additive, old ones become (sometimes hidden) aliases |
  | | `render.rs` | the single output path. Handlers never branch on `--json`: they hand a value to `emit`/`emit_line`, and every text listing goes through one `table` helper |
  | | `context.rs` | lazy client/board resolution and client-side column lookup |
  | `board-core` | `engine/` | pure decisions — lifecycle, transitions, validation, signals, `columns.rs` |
  | | `client/` | traits, Unix transport, fake client |
  | `board-herdr` | `events/` | event parsing and streams |

Before adding a helper, check `board-core` for shared primitives first.

Keep private tests beside those boundaries; describe ownership rather than maintaining a
file-by-file test manifest.

## Conventions

- `anyhow` at edges, `thiserror` in core. No `unwrap()` outside tests.
- Inject clocks/paths — the engine takes `now: i64`; paths via `directories` + env overrides
  (`BOARD_DB`, `BOARD_SOCKET`). No wall-clock flakiness in tests.
- Commit style: **Conventional Commits** grouped by crate/intent, as in the git log —
  `feat(core): …`, `feat(daemon,cli): …`, `docs: …`.
- The daemon opens a **fresh Herdr connection per operation** — so the protocol gate lives at the
  connect, not at a startup check; that is what `board-daemon/src/herdr_conn.rs` centralizes. One
  `HerdrClient` = one request/response connection, event streaming lives on its own connection.
  Runtime launch ownership is daemon-only: `board-core`
  persists the neutral schema-v11 launch spec, while `board-daemon` owns placement, pane/process
  handles, liveness, cleanup, and the Herdr supervisor.
- `RootConfig` is parsed once at daemon startup; typed `[daemon]` settings are resolved before
  environment overrides, and malformed existing config is fatal. CLI and TUI use typed
  `board-core::client::BoardClient` wrappers rather than raw method/result handling.
- Auto-start creates one child process-group leader (no double-fork/`setsid`); stop is an exact
  socket/identity-gated operation. The active-run summary drives TUI timers, and the always-on
  per-session supervisor reconnects and reconciles conservatively.
- Definition of done for a user-facing change: update the relevant docs and add a concise
  `CHANGELOG.md` entry when it helps users understand the release.
- Release/version changes follow [`docs/releasing.md`](docs/releasing.md). Agents must never create,
  push, move, or delete release tags manually: a maintainer starts **Prepare Release**, merges its
  PR into `dev`, the **Promote** workflow merges `dev -> main`, and the **Release** workflow creates
  the tag only after `main` CI is green at that promotion SHA. Repository rulesets protect `main`
  (PR-only, merge-commit, required fast CI) and `v*` tags (deletion/force-update); this is
  policy and workflow validation together. Bot-created PRs (release, promotion) need one manual
  approval of their workflow runs before CI executes — see `docs/releasing.md`.
- Branching: `dev` is the long-lived integration branch and the default target for feature PRs;
  `main` is production (default branch, Release's only publish path). The `dev -> main` promotion
  and hotfix PRs are opened/merged by the workflows themselves. After every promotion or hotfix,
  back-merge `main -> dev` before the next normal release.

## herdr gotchas (field-tested)

**Learning/verifying herdr is its own page.** herdr has no man page; the authoritative
sources are the installed binary itself — `herdr api schema --json` (methods/types/events +
protocol number), `herdr <cmd> --help`, `herdr api snapshot`. Never assume a herdr command,
flag, or JSON shape from memory, and pin the argv you verified in a test comment. Repo herdr
facts are pinned to exactly **Herdr 0.9.0 / protocol 22**. herdr-board intentionally rejects every
other Herdr version and protocol; re-verify against `api schema` before changing that gate or any
wire behavior. **See [`docs/herdr.md`](docs/herdr.md).**

- **Never run destructive herdr commands against a user's workspaces/sessions.** Mutations only
  against disposable workspaces you created (see `e2e/`). Read-only probes otherwise.
- **Agent names are exclusive** while a pane is open. Names are `card-<id>-<column-slug>`; on an
  `agent_name_taken` collision the daemon retries with the `-r<run>` fallback.
- **Panes don't inherit the workspace's env/cwd.** Managed-agent launch is pane-first:
  `tab.create`/`pane.split` establishes cwd + env, then `agent.start` targets that pane with
  `{name, kind, pane_id, args}`. Workspace cwd is read from the workspace's pane snapshot.
- Current durable runs use stable `card-<id>` tab labels, but reuse only an exact board-owned `tab_id` reconstructed from durable pane identity; labels are never ownership. Legacy `kanban` tabs remain untouched and legacy-only.
- **Herdr events are a raw-socket stream** (`events.subscribe`, persistent connection); the CLI only
  has a blocking one-shot `events.wait`. Protocol-19 `pane_agent_status_changed` carries pane,
  workspace, agent, and status fields; `idle ≠ finished`, and a trailing `idle` may follow `done`
  (completion still needs the explicit `board done` channel). Watcher identity is `(session socket,
  pane id)`, not pane id alone.
- **AF_UNIX paths cap at 108 chars.** Test DBs/sockets must live under a short `/tmp` dir
  (`tempfile::tempdir()`), not a deep nested path, or `connect` fails with a cryptic error.
