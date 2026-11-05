# shellcheck shell=bash
# Shared helpers for install.sh and scripts/*.sh. Sourced, not run.
#
# Prompts use gum (https://github.com/charmbracelet/gum) when it is there (scripts/00-requirements.sh offers to
# download it into ./.bin), plain `read` otherwise. Every question can be answered ahead of time with an
# environment variable (named in the question's code), so the whole install can run unattended:
#   PAPERKIOSK_AUTO=1   take the default for everything that has one; ask only what is really needed
#   PAPERKIOSK_YES=1    also answer yes to confirmations (implies AUTO)

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE=$ROOT/.env
SECRETS=$ROOT/secrets
DATA=$ROOT/data
[[ "${PAPERKIOSK_YES:-0}" == 1 ]] && PAPERKIOSK_AUTO=1
AUTO=${PAPERKIOSK_AUTO:-0}
YES=${PAPERKIOSK_YES:-0}
export PATH="$ROOT/.bin:$PATH"

if [[ -t 1 ]]; then B=$'\e[1m' D=$'\e[2m' R=$'\e[0m' PINK=$'\e[38;5;212m' GREEN=$'\e[32m' YEL=$'\e[33m' RED=$'\e[31m'
else B="" D="" R="" PINK="" GREEN="" YEL="" RED=""; fi

has_gum() { command -v gum >/dev/null 2>&1 && [[ -t 0 && -t 1 ]]; }
interactive() { [[ -t 0 ]]; }

# --- Output ------------------------------------------------------------------------------------

title() {   # title "Step name" ["one line about it"]
  echo
  if has_gum; then
    gum style --border rounded --border-foreground 212 --padding "0 2" --bold "$1" ${2:+"$(gum style --faint "$2")"}
  else
    echo "${PINK}${B}== $1${R}"; [[ -n "${2:-}" ]] && echo "${D}$2${R}"
  fi
}
info() { echo "  $*"; }
ok()   { echo "  ${GREEN}✓${R} $*"; }
warn() { echo "  ${YEL}!${R} $*" >&2; }
fail() { echo "  ${RED}✗ $*${R}" >&2; exit 1; }

explain() {   # explain <<'EOF' ... markdown ... EOF   (rendered by gum, or printed as it is)
  local text; text=$(cat)
  if has_gum; then gum format -- "$text"; else echo "$text" | sed -e 's/\*\*//g' -e 's/`//g' -e 's/^/  /'; fi
  echo
}

# --- Questions ---------------------------------------------------------------------------------

# ask VAR "Question" [default] [--password] [--required]
# Sets VAR. A value already in the environment wins (unattended installs); in AUTO mode the default is taken.
ask() {
  local var=$1 q=$2 def=${3:-} pw="" req="" val=""
  shift 2; [[ $# -gt 0 ]] && shift
  for o in "$@"; do case $o in --password) pw=1 ;; --required) req=1 ;; esac; done
  if [[ -n "${!var:-}" ]]; then return 0; fi
  if [[ "$AUTO" == 1 && -n "$def" ]]; then printf -v "$var" '%s' "$def"; return 0; fi
  if ! interactive; then
    [[ -n "$def" ]] && { printf -v "$var" '%s' "$def"; return 0; }
    fail "$q: no answer (no terminal). Set $var=... and run again."
  fi
  while :; do
    if has_gum; then
      if [[ -n "$pw" ]]; then val=$(gum input --password --header "$q" --placeholder "${def:+(keep: press Enter)}" --char-limit 0) || exit 130
      else val=$(gum input --header "$q" --value "$def" --char-limit 0) || exit 130; fi
    else
      if [[ -n "$pw" ]]; then read -r -s -p "  $q: " val; echo
      else read -r -p "  $q${def:+ [$def]}: " val; fi
    fi
    [[ -z "$val" ]] && val=$def
    [[ -z "$req" || -n "$val" ]] && break
    warn "This one is needed."
  done
  printf -v "$var" '%s' "$val"
  if has_gum && [[ -z "$pw" ]]; then echo "  ${D}$q:${R} $val"; fi
}

# confirm "Question?" [yes|no]   -> exit status. AUTO takes the default, YES says yes.
confirm() {
  local q=$1 def=${2:-yes}
  if [[ "$YES" == 1 ]]; then return 0; fi
  if [[ "$AUTO" == 1 ]] || ! interactive; then [[ "$def" == yes ]]; return; fi
  if has_gum; then
    local r=0
    if [[ "$def" == yes ]]; then gum confirm "$q" || r=$?; else gum confirm --default=false "$q" || r=$?; fi
    [[ $r -eq 130 ]] && exit 130
    return $r
  fi
  local a; read -r -p "  $q [$([[ $def == yes ]] && echo Y/n || echo y/N)] " a
  a=${a:-$def}; [[ "$a" =~ ^[Yy] ]]
}

# choose VAR "Header" "option 1" "option 2" ...   (the first option is the default)
# Options can be "value|label": VAR gets the value, the label is shown.
choose() {
  local var=$1 header=$2; shift 2
  local opts=("$@") labels=() i
  if [[ -n "${!var:-}" ]]; then return 0; fi
  for i in "${opts[@]}"; do labels+=("${i#*|}"); done
  local picked=""
  if [[ "$AUTO" == 1 ]] || ! interactive; then picked=${labels[0]}
  elif has_gum; then picked=$(gum choose --header "$header" "${labels[@]}") || exit 130
  else
    echo "  $header"; for i in "${!labels[@]}"; do echo "    $((i + 1))) ${labels[$i]}"; done
    local n; read -r -p "  Number [1]: " n; n=${n:-1}
    [[ "$n" =~ ^[0-9]+$ && $n -ge 1 && $n -le ${#labels[@]} ]] || n=1
    picked=${labels[$((n - 1))]}
  fi
  for i in "${opts[@]}"; do [[ "${i#*|}" == "$picked" ]] && { printf -v "$var" '%s' "${i%%|*}"; break; }; done
  echo "  ${D}$header${R} $picked"
}

# spin "What is happening" command args...   (functions work too; output shown only when it fails)
spin() {
  local t=$1 rc=0 log; shift
  log=$(mktemp)
  if has_gum; then
    "$@" >"$log" 2>&1 &
    local pid=$!
    gum spin --spinner dot --title " $t" -- sh -c "while kill -0 $pid 2>/dev/null; do sleep 0.2; done" || true
    wait "$pid" || rc=$?
  else
    echo "  … $t"
    "$@" >"$log" 2>&1 || rc=$?
  fi
  if (( rc != 0 )); then tail -30 "$log" | sed 's/^/    /' >&2; fi
  rm -f "$log"
  return $rc
}

# --- .env and secrets --------------------------------------------------------------------------

env_init() { [[ -f "$ENV_FILE" ]] || { cp "$ROOT/.env.example" "$ENV_FILE"; chmod 600 "$ENV_FILE"; }; }

env_get() {   # env_get KEY -> value from .env ("" when missing)
  [[ -f "$ENV_FILE" ]] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

env_set() {   # env_set KEY VALUE
  env_init
  local tmp; tmp=$(mktemp "$ROOT/.env.XXXXXX")
  if grep -qE "^$1=" "$ENV_FILE"; then
    awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k {print k "=" v; next} {print}' "$ENV_FILE" > "$tmp"
  else
    cat "$ENV_FILE" > "$tmp"; echo "$1=$2" >> "$tmp"
  fi
  chmod 600 "$tmp"; mv "$tmp" "$ENV_FILE"
}

secret_set() {   # echo value | secret_set name
  mkdir -p "$SECRETS"; chmod 700 "$SECRETS"
  local f=$SECRETS/$1; umask 077; cat > "$f.tmp"; mv "$f.tmp" "$f"; chmod 600 "$f"
}
secret_has() { [[ -s "$SECRETS/$1" ]]; }

# --- Docker ------------------------------------------------------------------------------------

compose() { docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" "$@"; }

ensure_dirs() {
  mkdir -p "$DATA" "$SECRETS"; chmod 700 "$SECRETS"
  for s in ha_token kiosk_key admin_password; do [[ -e "$SECRETS/$s" ]] || { : > "$SECRETS/$s"; chmod 600 "$SECRETS/$s"; }; done
}

ensure_image() {   # build the image if it isn't there (or "force")
  ensure_dirs
  if [[ "${1:-}" == force ]] || ! docker image inspect paperkiosk >/dev/null 2>&1; then
    spin "Building the PaperKiosk image (the first time takes a minute)" compose build
  fi
}

in_container() {   # in_container cmd...  (the app in a throw-away container, with .env, data and secrets)
  ensure_image
  compose build -q >/dev/null 2>&1 || ensure_image force   # the current code (cached: a second when nothing changed)
  compose run --rm --no-deps -T --quiet-pull paperkiosk "$@" 2> >(grep -vE '^ *Container .*(Creat|Start|Remov)' >&2)
}

# --- Network -----------------------------------------------------------------------------------

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }          # Windows: WSL
docker_desktop() { docker info --format '{{.OperatingSystem}}' 2>/dev/null | grep -qi "docker desktop"; }

lan_ip() {   # this machine's address on the LAN (on WSL: the Windows PC's, that is where Docker publishes the port)
  if is_wsl && command -v powershell.exe >/dev/null 2>&1; then
    local w
    w=$(powershell.exe -NoProfile -Command '(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1).IPv4Address.IPAddress' 2>/dev/null | tr -d '\r' | grep -E '^[0-9.]+$' | head -1)
    [[ -n "$w" ]] && { echo "$w"; return 0; }
  fi
  ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}' ||
    hostname -I 2>/dev/null | awk '{print $1}'
}

# Docker Desktop (Windows, macOS) passes requests on from its own gateway: the server never sees a screen's real
# address. Such an address is no use for SSH or for telling screens apart.
hidden_ip() { docker_desktop || [[ "$1" =~ ^(192\.168\.65\.|172\.(1[6-9]|2[0-9]|3[01])\.) ]]; }

kiosk_link() {   # the URL a screen opens once (with the key), e.g. http://192.168.1.10:8100/?key=...
  echo "$(env_get PAPERKIOSK_URL)/?key=$(cat "$SECRETS/kiosk_key")"
}

# --- Pairing ------------------------------------------------------------------------------------

# wait_paired SINCE SECONDS [Kindle|any] -> prints the IP of the first screen that paired with the kiosk link after
# SINCE (an ISO time, UTC), or nothing after SECONDS. The server logs "paired: <ip> (Kindle|browser) <user agent>".
wait_paired() {
  local since=$1 end=$((SECONDS + $2)) kind=${3:-Kindle} re line
  [[ "$kind" == any ]] && re='^paired: [0-9a-fA-F.:]+ ' || re='^paired: [0-9a-fA-F.:]+ \(Kindle\)'
  while (( SECONDS < end )); do
    line=$(compose logs --no-log-prefix --since "$since" paperkiosk 2>/dev/null | grep -E "$re" | tail -1 || true)
    [[ -n "$line" ]] && { awk '{print $2}' <<<"$line"; return 0; }
    sleep 2
  done
}

# save_env KEY VALUE: into .env, or, when adding another screen (ADDING=1), into $ADD_STATE for add-screen.sh
save_env() {
  if [[ "${ADDING:-0}" == 1 ]]; then [[ -n "${ADD_STATE:-}" ]] && printf '%s=%q\n' "$1" "$2" >> "$ADD_STATE"
  else env_set "$1" "$2"; fi
}

show_link() {   # the kiosk link, plus a QR code when qrencode is installed
  local link; link=$(kiosk_link)
  echo; echo "    ${B}$link${R}"; echo
  if command -v qrencode >/dev/null 2>&1; then qrencode -t ansiutf8 -m 2 "$link" | sed 's/^/    /'
  else info "${D}(install qrencode to get a QR code here to scan with the screen's camera)${R}"; fi
}

# --- Kindle over SSH ---------------------------------------------------------------------------

# Kindles: the first one is in .env (KINDLE_NAME, KINDLE_IP, KINDLE_SSH); more (scripts/add-screen.sh) in
# data/kindles.tsv as name<TAB>ip<TAB>ssh. kindles_list prints all of them, the first one first.
KINDLES_FILE=$DATA/kindles.tsv
kindles_list() {
  local main; main=$(env_get KINDLE_IP)
  [[ -n "$main" ]] && printf '%s\t%s\t%s\n' "$(env_get KINDLE_NAME | grep . || echo "KUAL device")" "$main" "$(env_get KINDLE_SSH)"
  [[ -f "$KINDLES_FILE" ]] && awk -F'\t' -v m="$main" 'NF >= 2 && $2 != m' "$KINDLES_FILE"
  return 0
}
kindle_add() {   # kindle_add NAME IP SSH   (another Kindle; the same IP again replaces its line)
  if [[ "$2" == "$(env_get KINDLE_IP)" ]]; then   # it is the first Kindle: just its name and SSH
    env_set KINDLE_NAME "$(tr -d '\t\r\n' <<<"$1")"; env_set KINDLE_SSH "$3"; return 0
  fi
  mkdir -p "$DATA"
  local tmp; tmp=$(mktemp "$DATA/.kindles.XXXXXX")
  [[ -f "$KINDLES_FILE" ]] && awk -F'\t' -v ip="$2" '$2 != ip' "$KINDLES_FILE" > "$tmp"
  printf '%s\t%s\t%s\n' "$(tr -d '\t\r\n' <<<"$1")" "$2" "$3" >> "$tmp"
  mv "$tmp" "$KINDLES_FILE"
}
# pick_kindle: sets and exports KINDLE_IP (and KINDLE_SSH). Already set: kept. KINDLE=<name or IP>: that one.
# One Kindle: that one. More: a menu, the first one preselected (and taken without a terminal).
pick_kindle() {
  [[ -n "${KINDLE_IP:-}" ]] && { export KINDLE_IP; return 0; }
  local lines=() opts=() l name ip
  mapfile -t lines < <(kindles_list)
  (( ${#lines[@]} )) || fail "No KUAL device set up yet: ./install.sh (or ./install.sh --add-screen)."
  for l in "${lines[@]}"; do
    IFS=$'\t' read -r name ip _ <<<"$l"
    if [[ -n "${KINDLE:-}" && ( "$KINDLE" == "$ip" || "${KINDLE,,}" == "${name,,}" ) ]]; then KINDLE_IP=$ip; fi
    opts+=("$ip|$name ($ip)")
  done
  [[ -n "${KINDLE:-}" && -z "${KINDLE_IP:-}" ]] && fail "No device called $KINDLE. Saved: $(cut -f1 < <(kindles_list) | paste -sd, - | sed 's/,/, /g')"
  if [[ -z "${KINDLE_IP:-}" ]]; then
    if (( ${#opts[@]} == 1 )); then KINDLE_IP=${opts[0]%%|*}
    else choose KINDLE_IP "Which device?" "${opts[@]}" >&2; fi
  fi
  KINDLE_SSH=$(kindles_list | awk -F'\t' -v ip="$KINDLE_IP" '$2 == ip {print $3; exit}')
  export KINDLE_IP KINDLE_SSH
}

# PaperKiosk's own SSH key for the Kindles, in ./ssh: not in ./secrets, which the server container can read.
SSHDIR=$ROOT/ssh
KINDLE_KEY=$SSHDIR/kindle_ed25519
if [[ -f "$SECRETS/kindle_ed25519" && ! -e "$KINDLE_KEY" ]]; then   # older installs kept it in secrets/
  mkdir -p "$SSHDIR" && chmod 700 "$SSHDIR"
  for f in kindle_ed25519 kindle_ed25519.pub kindle_known_hosts; do if [[ -e "$SECRETS/$f" ]]; then mv "$SECRETS/$f" "$SSHDIR/"; fi; done
fi
kssh() {   # kssh [ssh args...] command   (root@KINDLE_IP with PaperKiosk's own key and known_hosts)
  local ip=${KINDLE_IP:-$(env_get KINDLE_IP)}
  [[ -n "$ip" ]] || fail "No KINDLE_IP in .env: run ./scripts/50-kindle-setup.sh first."
  ssh -i "$KINDLE_KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$SSHDIR/kindle_known_hosts" \
      -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -o BatchMode=yes -o LogLevel=ERROR "root@$ip" "$@"
}
kscp() {   # kscp src... dest   (":path" means on the Kindle)
  local ip=${KINDLE_IP:-$(env_get KINDLE_IP)} args=()
  for a in "$@"; do [[ "$a" == :* ]] && args+=("root@$ip$a") || args+=("$a"); done
  scp -q -i "$KINDLE_KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$SSHDIR/kindle_known_hosts" \
      -o StrictHostKeyChecking=accept-new -o ConnectTimeout=6 -o BatchMode=yes -o LogLevel=ERROR "${args[@]}"
}
kindle_ssh_ok() { [[ -f "$KINDLE_KEY" ]] && kssh true 2>/dev/null; }
