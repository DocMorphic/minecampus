#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
bundle="$PWD"
fail() { printf '%s\n' "$1"; read -r -p 'Press Return to close.' || true; exit 1; }
[ "$(uname -s)" = Darwin ] || fail 'This is the Mac download. Please download the version for your computer.'
case "$(uname -m)" in
  arm64) runtime=darwin-arm64 ;;
  x86_64) runtime=darwin-x64 ;;
  *) fail 'This package supports Apple Silicon and Intel Macs.' ;;
esac
node="$bundle/runtime/$runtime/bin/node"
prism="$bundle/launcher/Prism Launcher.app/Contents/MacOS/prismlauncher"
[ -x "$node" ] && [ -x "$prism" ] || fail 'Extract the entire ZIP first, then open Play Minecampus.command from the extracted folder.'
"$node" "$bundle/configure-runtime.cjs" "$bundle" || fail 'Setup stopped. Keep the error above when asking for help.'
export PATH="$bundle/runtime/$runtime/bin:$PATH"
"$prism" --dir "$bundle/data" --launch minecampus || fail 'The launcher stopped. Keep the error above when asking for help.'
