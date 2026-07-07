#!/usr/bin/env bash
# ci_install_ripgrep.sh — install rg for path-guard / comfort_check without apt-get update.
#
# GitHub-hosted runners occasionally ship broken third-party apt sources (e.g. Microsoft
# azure-cli) that make `apt-get update` fail with exit 100 before ripgrep can install.
# Prefer: already installed → apt install without update → GitHub release binary.
set -euo pipefail

if command -v rg >/dev/null 2>&1; then
  echo "ripgrep: $(rg --version | head -1)"
  exit 0
fi

if sudo apt-get install -y -qq ripgrep >/dev/null 2>&1; then
  echo "ripgrep: installed via apt (no update)"
  rg --version | head -1
  exit 0
fi

RG_VERSION="${RG_VERSION:-14.1.1}"
case "$(uname -m)" in
  x86_64) RG_ARCH=amd64 ;;
  aarch64|arm64) RG_ARCH=arm64 ;;
  *)
    echo "::error::ci_install_ripgrep: unsupported arch $(uname -m)"
    exit 1
    ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
TARBALL="ripgrep-${RG_VERSION}-${RG_ARCH}-unknown-linux-gnu.tar.gz"
URL="https://github.com/BurntSushi/ripgrep/releases/download/${RG_VERSION}/${TARBALL}"

curl -fsSL "${URL}" | tar -xz -C "${TMP}"
install -m 0755 "${TMP}/ripgrep-${RG_VERSION}-${RG_ARCH}-unknown-linux-gnu/rg" /usr/local/bin/rg
echo "ripgrep: installed from ${URL}"
rg --version | head -1
