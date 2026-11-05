#!/usr/bin/env bash
# PaperKiosk installer. Runs the steps in scripts/ in order; each one also works on its own.
#
#   ./install.sh                 asks: automatic (sensible defaults, only the needed questions) or manual
#   ./install.sh --auto          automatic
#   ./install.sh --manual        pick the steps, every question asked
#   ./install.sh --step 20       just one step (00 requirements, 10 configure, 20 home-assistant,
#                                30 start-server, 40 kindle-install, 50 kindle-setup)
#   ./install.sh --add-screen    add another screen (a second Kindle, a tablet, ...) to a working setup
#   ./install.sh --yes           automatic and yes to every confirmation (unattended; give the answers as
#                                environment variables: ADMIN_PASSWORD, HA_URL, HA_TOKEN, SCREEN, KINDLE_METHOD, ...)
#
# Safe to run again: it keeps what is set up (keys, password, token) unless you ask for new ones.
set -euo pipefail
cd "$(dirname "$0")"
source scripts/lib.sh

STEPS=(00-requirements 10-configure 20-home-assistant 30-start-server 40-kindle-install 50-kindle-setup)
LABELS=("Requirements: Docker, Compose, gum"
        "Configure: port, address, time zone, keys, settings password"
        "Home Assistant: address, access token, the kiosk's room"
        "Start the server"
        "Install on the screen: KUAL extension (USB or Wi-Fi), or just the link"
        "Start the kiosk (the KUAL taps, automated over Wi-Fi)")
MODE="" ONLY=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --auto) MODE=auto ;;
    --manual) MODE=manual ;;
    --yes|-y) MODE=auto; export PAPERKIOSK_YES=1 ;;
    --step) ONLY=${2:?--step needs a number}; shift ;;
    --add-screen) exec scripts/add-screen.sh ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)"; exit 1 ;;
  esac
  shift
done

run_step() {
  local s=$1
  [[ -x "scripts/$s.sh" ]] || chmod +x "scripts/$s.sh"
  if ! "scripts/$s.sh"; then
    echo; warn "Step $s stopped. Fix what it says, then: ./install.sh --step ${s%%-*}"
    exit 1
  fi
}

if [[ -n "$ONLY" ]]; then
  for s in "${STEPS[@]}"; do [[ "$s" == "$ONLY"* ]] && { run_step "$s"; exit 0; }; done
  fail "No step $ONLY. Steps: ${STEPS[*]}"
fi

scripts/00-requirements.sh || exit 1   # first, so the rest gets the nice menus
if has_gum; then
  gum style --border double --border-foreground 212 --padding "1 4" --margin "1 0" --align center \
    "$(gum style --bold --foreground 212 'PaperKiosk')" "Home Assistant on an e-ink screen" "(=^.^=)"
else
  echo; echo "${PINK}${B}  PaperKiosk${R}  Home Assistant on an e-ink screen  (=^.^=)"; echo
fi

# Already set up? Then most people come back for one thing.
if [[ -z "$MODE" ]] && secret_has kiosk_key && secret_has admin_password && interactive &&
   compose ps --status running --services 2>/dev/null | grep -qx paperkiosk; then
  ok "PaperKiosk is set up and running ($(env_get PAPERKIOSK_URL))"
  choose TODO "What do you want to do?" \
    "add|Add a screen (another KUAL device, a tablet, a dashboard, ...)" \
    "link|Show the kiosk link (to pair a screen by hand)" \
    "update|Update PaperKiosk" \
    "password|Change the settings password" \
    "ha|Change the Home Assistant connection" \
    "setup|Run the setup again"
  case $TODO in
    add) exec scripts/add-screen.sh ;;
    link) show_link; exit 0 ;;
    update) exec scripts/update.sh ;;
    password) exec scripts/10-configure.sh --new-password ;;
    ha) HA_TOKEN="" exec scripts/20-home-assistant.sh ;;
  esac
fi

if [[ -z "$MODE" ]]; then
  explain <<'EOF'
**Automatic** asks only what it can't know (your Home Assistant token, a password, where the screen is) and picks
sensible defaults for the rest. **Manual** lets you choose the steps and asks every question. You can run any
step again later on its own: `./install.sh --step 20` (or `./scripts/20-home-assistant.sh`).
EOF
  choose MODE "How do you want to install?" "auto|Automatic (recommended)" "manual|Manual: choose the steps"
fi

if [[ "$MODE" == auto ]]; then
  export PAPERKIOSK_AUTO=1
  for s in "${STEPS[@]:1}"; do run_step "$s"; done
else
  picked=()
  if has_gum; then
    mapfile -t chosen < <(gum choose --no-limit --header "Steps to run (space to tick, enter to go)" \
                           --selected="*" "${LABELS[@]:1}") || exit 130
    for i in "${!LABELS[@]}"; do for c in "${chosen[@]}"; do [[ "$c" == "${LABELS[$i]}" ]] && picked+=("${STEPS[$i]}"); done; done
  else
    for i in "${!STEPS[@]}"; do
      (( i == 0 )) && continue
      confirm "Run step: ${LABELS[$i]}?" yes && picked+=("${STEPS[$i]}")
    done
  fi
  for s in "${picked[@]}"; do run_step "$s"; done
fi
echo; ok "${B}PaperKiosk is set up.${R} Settings: $(env_get PAPERKIOSK_URL)/config"
