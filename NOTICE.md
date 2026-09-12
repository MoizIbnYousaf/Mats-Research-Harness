# NOTICE

Everything in this repository outside `runtime/` is MIT (see [LICENSE](./LICENSE)). The study package under `study/` is original work for the study in [study/PLAN.md](./study/PLAN.md).

The CLI skeleton under `src/` and the multiplexer seam under `src/mux/` derive from [harnessindex/hi-harness](https://github.com/harnessindex/hi-harness) (MIT), commit `7769fcb7`. That credit stays with the code.

`runtime/` is `mrh-runtime`, the terminal multiplexer `mrh watch` uses as the wall, and it is Apache-2.0 (see [runtime/LICENSE](./runtime/LICENSE)). It is a fork of [herdr](https://github.com/herdrdev/herdr) at base commit `7b675f42af35508eab66ac42fe1598628597a893` (herdr 0.8.2, protocol 21, 2026-08-27), Apache-2.0 since herdr v0.8.0. The pin must never move below that relicense, because earlier herdr history is AGPL-3.0-or-later. The tree was vendored into this repository from commit `7769fcb7` of this repository's history and modified here: the product layer, the self-update, the catalog fetch, the plugin fetch from GitHub and the website were removed, and the binary was renamed. Vendored inside it are libghostty-vt (MIT, from Ghostty) and portable-pty (MIT), with their own notices under `runtime/vendor/`. herdr is also the source of the pane and agent CLI vocabulary used in `src/mux/`.

There are no binary releases.
