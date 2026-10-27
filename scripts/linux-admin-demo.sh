#!/usr/bin/env bash
# CSC418 Task 2 — Linux administration: commands, a directory, and file permissions.
#
#   bash scripts/linux-admin-demo.sh
#
# Read-only apart from everything it creates under /opt/ad-optimizer, so it is safe to re-run.
# Remove that tree afterwards with:  sudo rm -rf /opt/ad-optimizer

set -euo pipefail

ROOT=/opt/ad-optimizer
OWNER="${SUDO_USER:-$(id -un)}"

banner() {
    printf '\n===== %s =====\n' "$1"
}

banner "1. who and where"
echo "user:      $(id -un)   groups: $(id -Gn)"
echo "hostname:  $(hostname)"
echo "kernel:    $(uname -r)"
echo "working directory: $(pwd)"

banner "2. system state"
echo "--- memory ---"
free -h
echo "--- disk ---"
df -h /

banner "3. create the directory structure"
sudo mkdir -p "$ROOT/logs" "$ROOT/data"
echo "created $ROOT with logs/ and data/"

banner "4. create the files it will hold"
printf 'release 1.0.0\n' | sudo tee "$ROOT/deploy.txt" > /dev/null
sudo touch "$ROOT/logs/app.log"
printf 'row\n' | sudo tee "$ROOT/data/import.csv" > /dev/null

banner "5. hand ownership to the signed-in user"
sudo chown -R "$OWNER:$OWNER" "$ROOT"

banner "6. set the permissions"
# 755 on the project root: everyone may enter and list it.
# 750 on the working directories: owner full, group read+enter, nobody else.
# 640 on the files: owner writes, group reads, no execute bit for anyone.
sudo chmod 755 "$ROOT"
sudo chmod 750 "$ROOT/logs" "$ROOT/data"
sudo chmod 644 "$ROOT/deploy.txt"
sudo chmod 640 "$ROOT/logs/app.log" "$ROOT/data/import.csv"

banner "7. prove it: the directory itself"
ls -ld "$ROOT"

banner "8. prove it: the tree"
ls -lR "$ROOT"

banner "9. prove it: one line per object, symbolic and octal"
stat -c '%A  %a  %U:%G  %n' "$ROOT" "$ROOT/logs" "$ROOT/data" \
    "$ROOT/deploy.txt" "$ROOT/logs/app.log" "$ROOT/data/import.csv"

banner "10. read the effective permission bits"
# Checked as the owning user, not as root: root bypasses the permission bits, so a root test would
# report "yes" for everything and prove nothing.
if test -w "$ROOT/logs/app.log"; then
    echo "owner can write app.log:         yes, from the 640 owner bit"
else
    echo "owner cannot write app.log:      unexpected"
fi
if sudo -u nobody cat "$ROOT/logs/app.log" > /dev/null 2>&1; then
    echo "nobody CAN read app.log:         unexpected"
else
    echo "nobody cannot read app.log:      denied, as intended by 640"
fi
if sudo -u nobody ls "$ROOT/data" > /dev/null 2>&1; then
    echo "nobody CAN list data/:           unexpected"
else
    echo "nobody cannot list data/:        denied, as intended by 750"
fi

banner "11. other files that depend on those permissions"
echo "--- newest 5 modified files under /var/log ---"
sudo find /var/log -type f -printf '%TY-%Tm-%Td %TH:%TM  %p\n' 2>/dev/null | sort -r | head -5
echo "--- last 5 log lines ---"
sudo tail -n 5 /var/log/auth.log 2>/dev/null || echo "(no /var/log/auth.log yet)"

banner "done"
echo "To remove the demonstration tree:  sudo rm -rf $ROOT"
