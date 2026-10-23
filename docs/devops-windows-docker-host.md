# Standing up a Docker host on Windows 10 build 18363

Docker Desktop 4.x refuses to install below Windows 10 22H2 (build 19045) and WSL2 needs
19041 or newer, so neither of the usual paths exists on this machine. What does exist is
**Hyper-V**, which is built into Windows 10 Pro — and Hyper-V is exactly the layer Docker
Desktop itself sits on when it runs a Linux VM hosting `dockerd`. Rebuilding that shape by
hand is a better viva answer than a GUI installer, and it costs nothing.

The VM lives on `D:` (246 GB free), so the 23 GB left on `C:` is not involved.

```
Windows 10 Pro 18363
└── Hyper-V  →  Ubuntu 24.04 Server VM  (6 GB RAM, 60 GB VHDX on D:)
     └── Docker Engine + Compose v2  (installed by get.docker.com)
          └── the same docker compose up -d --build as everywhere else in this repo
```

---

## 1. Enable Hyper-V (one reboot)

PowerShell **as administrator**:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -NoRestart
Restart-Computer
```

If the cmdlet is not found, use Control Panel → Programs → Turn Windows features on or off
→ tick **Hyper-V** (all sub-items) → OK → reboot.

## 2. Get the ISO

Download **Ubuntu Server 24.04 LTS (64-bit)** from <https://ubuntu.com/download/server> —
the `live-server` amd64 image, about 2.7 GB. Save it as `D:\vm\ubuntu.iso` (create the
`D:\vm` folder first). Server, not Desktop: there is no need for a GUI inside the VM, and
the SSH session from Windows is what you screenshot.

## 3. Create the VM

PowerShell as administrator. `Default Switch` is created by the Hyper-V install and gives
the VM outbound internet plus an address the Windows host can reach.

```powershell
New-Item -ItemType Directory -Force D:\vm | Out-Null
$vm = New-VM -Name devops-lab -MemoryStartupBytes 6GB -Path D:\vm `
             -NewVHDPath D:\vm\devops-lab.vhdx -NewVHDSizeBytes 60GB `
             -SwitchName "Default Switch"
Set-VMDynamicMemory -VMName devops-lab -MemoryMinimumBytes 2GB -MemoryMaximumBytes 6GB
Add-VMDvdDrive -VMName devops-lab -Path D:\vm\ubuntu.iso
Set-VMFirmware -VMName devops-lab -FirstBootDevice (Get-VMDvdDrive -VMName devops-lab)
Start-VM devops-lab
Connect-VM devops-lab          # opens the console window
```

Press Enter at the "Press Enter to reboot" screen if it boots straight past the ISO, and it
will load the installer from the DVD.

## 4. Install Ubuntu Server

Answer the prompts like this — the only one that matters for the lab is OpenSSH:

| Screen | Choose |
| --- | --- |
| Language / keyboard | English, English (US) |
| Install type | Ubuntu Server (default, "Try or Install Ubuntu Server") |
| SSH setup | **Install OpenSSH server** — tick it |
| Snaps | none |
| Profile | your name, server name `devops-lab`, username `devops-lab`, a password |
| Ubuntu Pro | Skip |
| Storage | Use an entire disk → the 64 GB `LVM`/`SCSI` device → **Create partitions** → Done |
| Upgrade | "Update and install third-party drivers" — no |

Reboot when it finishes, and in the VM console log in with the user you just made. If the
VM comes back to "Boot failed", run the `Set-VMFirmware` line again without the DVD, or
just let it boot from the VHDX.

## 5. Find its address and connect from Windows

In the VM:

```bash
ip -4 a show scope global      # e.g. 172.x.x.x — Default Switch hands out a fresh address per boot
```

Then from **Git Bash on Windows**, which is the window you will screenshot:

```bash
ssh devops-lab@172.x.x.x
```

The app is then reachable in a Windows browser at `http://172.x.x.x:3000` — that is how you
take the frontend and dashboard screenshots with a normal browser, not a console one.

## 6. Install Docker and bring the stack up

```bash
sudo apt-get update && sudo apt-get install -y git curl
git clone --branch devops-lab \
  https://github.com/Fatima-Khalidd/Ad-Optimization_Product.git ad-optimizer
cd ad-optimizer
sudo BRANCH=devops-lab bash scripts/bootstrap-ec2.sh
```

`bootstrap-ec2.sh` was written for EC2 and does the same job here: it installs Docker
Engine and the Compose plugin from `get.docker.com`, adds your user to the `docker` group,
generates a mode-600 `.env` with random secrets, builds both images, starts the stack and
seeds the demo client. Off AWS there is no metadata service, so the health endpoint labels
the node with the VM hostname instead of an instance id — the script prints
`az=not-aws` to say so.

Then, as your normal user (log out and back in once so the `docker` group applies):

```bash
cd ~/ad-optimizer
docker compose ps
docker compose --profile seed run --rm seed
bash scripts/linux-admin-demo.sh
bash scripts/demo-volume-persistence.sh
pip install -r tests/selenium/requirements.txt
APP_BASE_URL=http://localhost:3000 DEMO_PASSWORD="$(cat .demo-password)" pytest tests/selenium -v
```

## 7. Capture the evidence from here

Everything in [devops-evidence-checklist.md](devops-evidence-checklist.md) is capturable
from this VM, and two items get *better*:

- `03b` — `systemctl is-active docker` genuinely applies, because Ubuntu Server runs
  systemd. On Docker Desktop that command does not exist on the host.
- `02a`–`02e` — the Linux administration task runs on a real Linux install as a real user,
  with `chown` and `groupadd` available, instead of inside a container.

Use Windows Snipping Tool on the SSH window for terminal shots, and on the browser for
`05f` and `01h`.

## 8. Housekeeping

```powershell
Stop-VM devops-lab -TurnOff          # when you are done for the day; frees the 6 GB
Get-VM | Format-Table Name,State,Uptime
```

The whole VM is one file, `D:\vm\devops-lab.vhdx` — copy it elsewhere and you have a backup
of the graded environment.

---

## If Hyper-V is not an option

VirtualBox 7 works on this build with no Windows feature changes: create a Linux/Ubuntu
(64-bit) VM with 4 GB RAM and a 60 GB disk on `D:`, attach the same ISO, set the network to
**Bridged Adapter** so it gets an address on your LAN, and continue from step 4. The only
difference is which screen the VM is on. Do not install both: VirtualBox 7 can run on a
Hyper-V host but it is slower and not worth the confusion before an exam.

## Why not the other paths

- **Docker Desktop** — hard requirement of build 19045; the installer you ran is correct
  and no setting inside it changes that.
- **WSL2** — needs 19041+ for the inbox `wsl --install`; on 18363 you would get WSL1, which
  has no real Linux kernel, so `dockerd` cannot run in it.
- **Windows containers** — the images here are Linux (`python:3.11-slim`,
  `node:24-alpine`, `postgres:16-alpine`); they will not run as Windows containers.
- **Codespaces / a cloud box** — works, but "install Docker" (task 3) then has nothing to
  show, and you are paying a network round trip for every debug cycle.
