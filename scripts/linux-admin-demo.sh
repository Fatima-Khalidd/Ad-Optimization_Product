#!/usr/bin/env bash
# Section A, task 2 - Linux administration: commands, directory creation, permissions.
#
# Run this on the EC2 instance (Ubuntu), not in Git Bash on Windows: chown, groupadd and
# the setgid bit behave differently or not at all under MSYS.
#
#   bash scripts/linux-admin-demo.sh
#
# Everything is written under $CSC418_HOME (default ~/csc418-linux) so the script is
# idempotent and cannot touch the running application.

set -euo pipefail

BASE="${CSC418_HOME:-$HOME/csc418-linux}"

banner() { printf '\n=== %s ===\n' "$1"; }

banner "1. System inspection"
uname -a
grep -E '^(PRETTY_NAME|VERSION_ID)' /etc/os-release || true
echo "kernel/user-clock: $(uptime)"
df -h "$HOME" | tail -1
free -h | head -2
echo "identity: $(id -un) ($(id -rn)) groups: $(id -nG)"

banner "2. Services and processes"
if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active docker || echo "docker.service is not active - run scripts/bootstrap-ec2.sh"
  systemctl status docker --no-pager | head -5 || true
fi
ps -eo pid,ppid,user,comm --sort=-%cpu | head -8

banner "3. Directory layout"
# -p makes this safe to re-run; the mode is set explicitly rather than inherited.
mkdir -p "$BASE"/{config,secrets,logs,shared,backup}
chmod 750 "$BASE"
chmod 750 "$BASE/config" "$BASE/logs" "$BASE/backup"
chmod 700 "$BASE/secrets"
chmod 2775 "$BASE/shared"   # setgid: new files inherit the group, so a team dir stays shared
ls -ld "$BASE" "$BASE"/*

banner "4. File creation and permissions"
printf 'ENV=dev\nSTORAGE_BACKEND=local\n' > "$BASE/config/app.env"
printf 'replace-me\n' > "$BASE/secrets/db.passwd"
: > "$BASE/logs/deploy.log"
printf 'placeholder\n' > "$BASE/shared/notes.txt"

chmod 640 "$BASE/config/app.env"    # owner rw, group r, others none
chmod 600 "$BASE/secrets/db.passwd" # owner only
chmod 644 "$BASE/logs/deploy.log"   # world-readable log
chmod 664 "$BASE/shared/notes.txt"

banner "5. Reading the mode three ways"
ls -l "$BASE/config" "$BASE/secrets" "$BASE/logs" "$BASE/shared"
stat -c '%n  octal=%a  human=%A  owner=%U:%G' "$BASE"/config/app.env "$BASE"/secrets/db.passwd \
  "$BASE"/logs/deploy.log "$BASE"/shared/notes.txt "$BASE"/shared

banner "6. Symbolic changes (what each bit does)"
chmod u+rw,g+r,o-rwx "$BASE/config/app.env"
echo "after 'u+rw,g+r,o-rwx':"; stat -c '%A %n' "$BASE/config/app.env"
chmod g-w,o+r "$BASE/shared/notes.txt"
echo "after 'g-w,o+r':"; stat -c '%A %n' "$BASE/shared/notes.txt"

banner "7. Ownership"
if [ "$(id -u)" -eq 0 ]; then
  GROUP=adopt
  if ! getent group "$GROUP" >/dev/null; then groupadd "$GROUP"; fi
  if ! id -u appuser >/dev/null 2>&1; then useradd -r -g "$GROUP" -s /usr/sbin/nologin appuser; fi
  chown -R "appuser:$GROUP" "$BASE/config" "$BASE/logs"
  ls -l "$BASE/config" "$BASE/logs"
  echo "created service account appuser:$GROUP (nologin shell) and handed config/ + logs/ to it"
else
  echo "not root: skipping groupadd/useradd/chown. Re-run with sudo, or use 'sudo groupadd adopt'."
fi

banner "8. umask and the mode it produces"
echo "current umask: $(umask)"
umask 077
touch "$BASE/secrets/token.env"
echo "umask 077 -> new file:"; stat -c '%A %n' "$BASE/secrets/token.env"
umask 022
touch "$BASE/logs/access.log"
echo "umask 022 -> new file:"; stat -c '%A %n' "$BASE/logs/access.log"

banner "9. Searching by permission"
echo "executable files under $BASE:"; find "$BASE" -type f -perm /111 -print
echo "files unreadable by others:"; find "$BASE" -type f ! -perm -004 -print
echo "world-writable (should be empty):"; find "$BASE" -type f -perm -0002 -print
echo "directories with setgid:"; find "$BASE" -type d -perm -g+s -print

banner "10. The setgid bit in practice"
( umask 002; printf 'created inside the shared dir\n' > "$BASE/shared/from-setgid.txt" )
stat -c '%A %U:%G %n' "$BASE/shared/from-setgid.txt"
echo "^ group is the directory's group, not the creator's primary group - that is the setgid bit"

banner "11. Log inspection commands worth knowing"
tail -n 5 "$BASE/logs/access.log" || true
grep -c '' "$BASE/config/app.env"
wc -l "$BASE"/*/*.log 2>/dev/null || true
du -sh "$BASE"

banner "12. Cleanup"
read -r -p "delete $BASE? [y/N] " answer
if [ "${answer:-N}" = "y" ]; then rm -rf "$BASE"; echo "removed $BASE"; else echo "kept $BASE"; fi

echo
echo "Done. Screenshot the blocks '3. Directory layout', '5. Reading the mode three ways'"
echo "and '9. Searching by permission' - those are the marks for task 2."
