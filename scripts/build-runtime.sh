#!/bin/sh
# Build mrh-runtime, the terminal wall for the hand runs, from runtime/ in this tree.
#
#   sh scripts/build-runtime.sh            cargo build --release in runtime/, then the binary path and its --version
#   sh scripts/build-runtime.sh --check    toolchain and pin facts, no build, exits 0
#   sh scripts/build-runtime.sh --link     build, then symlink ~/.local/bin/mrh-runtime to the binary
#
# Writes nothing outside runtime/target, except the --link symlink.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
RT="$ROOT/runtime"
BIN="$RT/target/release/mrh-runtime"
LINK="$HOME/.local/bin/mrh-runtime"

mode=${1:-}
case "$mode" in
  ""|--check|--link) ;;
  *) echo "usage: sh scripts/build-runtime.sh [--check|--link]" >&2; exit 2 ;;
esac

if [ ! -f "$RT/Cargo.toml" ]; then
  echo "build-runtime: no runtime/Cargo.toml under $ROOT" >&2
  exit 1
fi

if [ "$mode" = "--check" ]; then
  pinned=$(sed -n 's/^channel = "\(.*\)"/\1/p' "$RT/rust-toolchain.toml" 2>/dev/null || true)
  echo "runtime:   $RT"
  echo "toolchain: rust-toolchain.toml pins ${pinned:-nothing}"
  if command -v cargo >/dev/null 2>&1; then
    # Run from runtime/ so rustup applies the pin; never let it download a missing toolchain, and keep its errors off the gate output.
    if cargo_version=$(cd "$RT" && RUSTUP_AUTO_INSTALL=0 cargo --version 2>/dev/null); then
      echo "cargo:     $cargo_version"
    else
      echo "cargo:     on PATH, but no toolchain answers for the pin (rustup toolchain install ${pinned:-stable})"
    fi
  else
    echo "cargo:     missing (install Rust through rustup; the pin picks the version)"
  fi
  if command -v zig >/dev/null 2>&1; then
    echo "zig:       $(zig version)"
  else
    echo "zig:       missing (the vendored terminal library needs zig 0.15.2)"
  fi
  if [ -x "$BIN" ]; then
    echo "binary:    $BIN ($("$BIN" --version))"
  else
    echo "binary:    $BIN not built (make runtime)"
  fi
  exit 0
fi

missing=0
if ! command -v cargo >/dev/null 2>&1; then
  echo "build-runtime: cargo not found; install Rust through rustup (https://rustup.rs)" >&2
  missing=1
fi
if ! command -v zig >/dev/null 2>&1; then
  echo "build-runtime: zig not found; the vendored terminal library needs zig 0.15.2" >&2
  missing=1
fi
[ "$missing" -eq 0 ] || exit 1

echo "building mrh-runtime (release) in $RT"
(cd "$RT" && cargo build --release)
echo "$BIN"
"$BIN" --version

if [ "$mode" = "--link" ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sfn "$BIN" "$LINK"
  echo "linked $LINK -> $BIN"
fi
