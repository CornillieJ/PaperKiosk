#!/usr/bin/env bash
# Update PaperKiosk: pull the newest version (git pull --ff-only), rebuild and restart the server, and, when
# this server can reach the Kindle over SSH, update the Kindle app too (your kiosk link and key are kept).
source "$(dirname "$0")/lib.sh"

title "Update PaperKiosk"
cd "$ROOT" || exit 1
if [[ -d .git ]]; then
  [[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail "You changed files here (git status): commit or stash them first."
  old=$(git rev-parse HEAD)
  spin "Getting the newest version" git pull --ff-only
  new=$(git rev-parse HEAD)
  if [[ "$old" == "$new" ]]; then ok "Already the newest version"; else
    ok "Updated: $(git rev-list --count "$old..$new") new change(s)"; git log --format='    %s' "$old..$new" | head -15; fi
fi
"$ROOT/scripts/30-start-server.sh" >/dev/null && ok "Server rebuilt and running"
if [[ "$(env_get KINDLE_SSH)" == yes ]] && kindle_ssh_ok; then
  KINDLE_METHOD=ssh SCREEN=kindle KINDLE_SSH=yes PAPERKIOSK_AUTO=1 "$ROOT/scripts/40-kindle-install.sh" >/dev/null &&
    ok "Kindle app updated" && PAPERKIOSK_AUTO=1 "$ROOT/scripts/50-kindle-setup.sh" >/dev/null && ok "Kiosk restarted on the Kindle"
else
  info "Kindle not reachable over SSH: its app only changes now and then; to update it run ./scripts/40-kindle-install.sh"
fi
