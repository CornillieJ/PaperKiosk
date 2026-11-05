#!/usr/bin/env bash
# Step 0: check what the installer needs (Docker with Compose v2, curl, ssh for the Kindle) and offer gum,
# the tool that draws the nice menus, downloaded into ./.bin (checksum checked). Changes nothing else.
source "$(dirname "$0")/lib.sh"

GUM_VERSION=2.0.2
declare -A GUM_SHA256=(
  [Linux_x86_64]=d842e06d93dbed90af48cb8dd10698db6f22e331fc40346bb37bbc753109edc2
  [Linux_arm64]=8ebf8b54ec1e8c81f2bb58b59ff9b70998186a4d11375f0cf357b80e0ccfa1d5
  [Linux_armv7]=a7ee9b68052e401c47335982fec7fc1d246868abfe6b542654432ee2df7a8141
  [Linux_armv6]=3589848314d33adc47b1852774d10808dd7c0c055f71b09a2cc60b6887429454
  [Linux_i386]=43332d42cf809434c884a51ff7f0c624e2c8c5fc2585f5153845ff691b8f45a4
  [Darwin_arm64]=4777a69b1170b8db23c95d5889fb32186cfda1a3ac950d339aa17e3513633890
  [Darwin_x86_64]=5374966c7c7199ea879fcaa525ddc6d447a098d3d35496e430a9a1ef38d30485
)

get_gum() {
  local os arch plat url tmp sum
  os=$(uname -s); arch=$(uname -m)
  case "$arch" in x86_64|amd64) arch=x86_64 ;; aarch64|arm64) arch=arm64 ;; armv7*) arch=armv7 ;; armv6*) arch=armv6 ;;
                  i?86) arch=i386 ;; esac
  plat=${os}_${arch}
  [[ -n "${GUM_SHA256[$plat]:-}" ]] || { warn "No gum download for $plat: plain prompts it is."; return 1; }
  url=https://github.com/charmbracelet/gum/releases/download/v$GUM_VERSION/gum_${GUM_VERSION}_$plat.tar.gz
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' RETURN
  curl -fsSL "$url" -o "$tmp/gum.tgz" || { warn "Download failed: $url"; return 1; }
  sum=$( (sha256sum "$tmp/gum.tgz" 2>/dev/null || shasum -a 256 "$tmp/gum.tgz") | cut -d' ' -f1)
  [[ "$sum" == "${GUM_SHA256[$plat]}" ]] || { warn "gum download has the wrong checksum, not using it."; return 1; }
  tar -xzf "$tmp/gum.tgz" -C "$tmp"
  mkdir -p "$ROOT/.bin"; install -m 755 "$(find "$tmp" -type f -name gum | head -1)" "$ROOT/.bin/gum"
  ok "gum $GUM_VERSION installed in .bin/ (only used by this installer)"
}

title "Requirements" "Docker, Docker Compose, and a few small tools"
missing=0
if is_wsl; then
  ok "Windows (WSL)"
  case "$ROOT" in
    /mnt/[a-z]/*) warn "PaperKiosk is in a Windows folder ($ROOT). Keys and passwords can't be protected there."
                  fail "Clone it inside WSL instead, e.g.: cd ~ && git clone https://github.com/CornillieJ/PaperKiosk.git" ;;
  esac
fi
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then ok "Docker $(docker version -f '{{.Server.Version}}' 2>/dev/null)"
  else
    warn "Docker is installed but this user can't use it."
    if is_wsl; then info "Start Docker Desktop on Windows, and in its Settings > Resources > WSL integration, turn it on for this distro."
    else info "Fix: sudo usermod -aG docker $USER   (then log out and in again), or run the installer with sudo."; fi
    missing=1
  fi
else
  if is_wsl; then warn "Docker isn't available here. Install Docker Desktop on Windows (https://docs.docker.com/desktop/setup/install/windows-install/) and turn on its WSL integration for this distro."
  else warn "Docker is not installed. Get it from https://docs.docker.com/engine/install/ (or: curl -fsSL https://get.docker.com | sh)"; fi
  missing=1
fi
if docker compose version >/dev/null 2>&1; then ok "Docker Compose $(docker compose version --short 2>/dev/null)"
else warn "Docker Compose v2 (the 'docker compose' command) is missing: install the docker-compose-plugin package."; missing=1; fi
for c in curl awk sed; do
  command -v $c >/dev/null 2>&1 && ok "$c" || { warn "$c is missing"; missing=1; }
done
command -v ssh >/dev/null 2>&1 && command -v ssh-keygen >/dev/null 2>&1 && ok "ssh (to set up a KUAL device over Wi-Fi)" ||
  info "ssh is missing: fine, unless you want the installer to reach a KUAL device over Wi-Fi."

if command -v gum >/dev/null 2>&1; then
  ok "gum $(gum --version 2>/dev/null | awk '{print $NF}')"
elif interactive && [[ "$(env_get PAPERKIOSK_GUM)" != no ]]; then
  echo
  if confirm "Download gum (nicer menus for this installer, ~5 MB, into ./.bin)?" yes; then get_gum || true
  else env_set PAPERKIOSK_GUM no; info "OK, plain questions (asked once; PAPERKIOSK_GUM=no in .env)."; fi
fi
(( missing == 0 )) || fail "Install what is missing above, then run this again."
ok "All set."
