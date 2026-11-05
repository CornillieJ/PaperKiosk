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
# Every saved Kindle (kindles_list) that this server can reach over SSH gets the new app and a restart.
mapfile -t KINDLES < <(kindles_list)
for line in "${KINDLES[@]}"; do
  IFS=$'\t' read -r name ip ssh <<<"$line"
  if [[ "$ssh" == yes ]] && KINDLE_IP=$ip kindle_ssh_ok; then
    if KINDLE_IP=$ip ADDING=1 KINDLE_METHOD=ssh SCREEN=kindle KINDLE_SSH=yes PAPERKIOSK_AUTO=1 "$ROOT/scripts/40-kindle-install.sh" >/dev/null &&
       KINDLE_IP=$ip ADDING=1 KINDLE_SSH=yes SCREEN=kindle PAPERKIOSK_AUTO=1 "$ROOT/scripts/50-kindle-setup.sh" >/dev/null; then
      ok "$name ($ip): app updated and restarted"
    else warn "$name ($ip): update failed, try: KINDLE=\"$name\" ./scripts/40-kindle-install.sh"; fi
  else
    info "$name ($ip): not reachable over SSH; its app only changes now and then (./scripts/40-kindle-install.sh)"
  fi
done
