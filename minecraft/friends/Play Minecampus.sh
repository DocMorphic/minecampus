#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
bundle="$PWD"
fail() { printf '%s\n' "$1"; read -r -p 'Press Return to close.' || true; exit 1; }
[ "$(uname -s)" = Linux ] || fail 'This is the Linux download. Please download the version for your computer.'
case "$(uname -m)" in
  x86_64) runtime=linux-x64 ;;
  aarch64|arm64) runtime=linux-arm64 ;;
  *) fail 'This package supports Linux x64 or ARM64. A 64-bit desktop OS is required.' ;;
esac
node="$bundle/runtime/$runtime/bin/node"
prism="$bundle/launcher/PrismLauncher.AppImage"
[ -f "$node" ] || fail 'This download is for a different CPU. Choose Linux-x64 for Intel/AMD or Linux-ARM64 for ARM.'
[ -x "$node" ] && [ -x "$prism" ] || fail 'Extract the entire ZIP onto a Linux filesystem that permits running programs.'
"$node" "$bundle/configure-runtime.cjs" "$bundle" || fail 'Setup stopped. Keep the error above when asking for help.'
export PATH="$bundle/runtime/$runtime/bin:$PATH"
# AppImage's supported extraction mode avoids a separate FUSE installation.
APPIMAGE_EXTRACT_AND_RUN=1 "$prism" --dir "$bundle/data" --launch minecampus || fail 'The launcher stopped. Keep the error above when asking for help.'
