# mrh-runtime

This folder is the terminal wall for the harness study: the headless multiplexer that `mrh watch` drives to put every body's session in its own pane and read the panes back. It is a cut-down fork of the herdr kernel. The herdr sessions, headless server, workspaces, panes, agent detection and socket API are here; the herdr product layer is not.

## Attribution

mrh-runtime is a fork of herdr (https://github.com/herdrdev/herdr) at commit 7b675f42af35508eab66ac42fe1598628597a893, herdr 0.8.2, protocol 21, released 2026-08-27 under Apache-2.0. NOTICE.md at the repository root carries the full provenance, including what this fork changed. LICENSE in this folder is the Apache-2.0 text, unchanged. Two vendored libraries sit under `vendor/` with their own notices: libghostty-vt (MIT, from Ghostty) and portable-pty (MIT).

## Build

```sh
cd runtime
cargo build --release
```

The binary lands at `runtime/target/release/mrh-runtime`. The build needs the Rust toolchain pinned in `rust-toolchain.toml` and zig 0.15, which compiles the vendored libghostty-vt. `scripts/build-runtime.sh` at the repository root wraps the same command; `--check` prints the toolchain and pin facts without building and `--link` symlinks the binary into `~/.local/bin`.

## What the study calls

`mrh watch` starts one headless server per study session and drives it with these commands:

```
mrh-runtime --session <name> server
mrh-runtime session list
mrh-runtime session stop <name>
mrh-runtime status server
mrh-runtime workspace list
mrh-runtime workspace create --cwd <dir> --label <label> --no-focus
mrh-runtime pane create --crew --bind <name> --cwd <dir> --env KEY=VALUE --no-focus
mrh-runtime pane run <id> <command>
mrh-runtime pane read <id> --source visible --lines <n>
mrh-runtime pane rename <id> <label>
mrh-runtime pane send-keys <id> <key>
mrh-runtime agent list
mrh-runtime agent read <handle> --source recent-unwrapped --lines <n>
mrh-runtime agent send-keys <handle> ctrl+c
```

`mrh-runtime --help` lists the rest. The study finds the binary through `MRH_RUNTIME_BIN`, then `runtime/target/release/mrh-runtime`, then `mrh-runtime` on `PATH`.

## Config and sockets

Config lives at `~/.config/mrh-runtime/config.toml` (`~/.config/mrh-runtime-dev` for debug builds). `MRH_RUNTIME_CONFIG_PATH` overrides the path, and so does `HERDR_CONFIG_PATH`, which the pane hooks still speak. A named session listens on `~/.config/mrh-runtime/sessions/<name>/herdr.sock`; `session list` prints that path. Every `HERDR_*` environment variable keeps its name because the hook scripts inside the panes read them.

## What was removed

The fork dropped the product layer that sat on top of the kernel (a resident sidebar column, a login card and the pane it drove), the self-updater and its update channel, the background fetch of agent detection manifests, the remote-install download for `--remote`, and the upstream website, docs, packaging and CI files. Each of those either phoned home or existed to sell the product, and the study needs neither. The fork also dropped `plugin install`, which fetched a plugin from GitHub through git; `plugin link <path>` remains for a local one. The binary opens no network connection on its own. One command hands a connection to another program: `--remote` runs your ssh client. The study does not use it.
