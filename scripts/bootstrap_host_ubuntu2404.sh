#!/usr/bin/env bash
set -euo pipefail

RUN_HOST_INSTALL=${RUN_HOST_INSTALL:-0}
DRIVER_LOCAL_REPO_URL=${DRIVER_LOCAL_REPO_URL:-https://us.download.nvidia.com/tesla/590.48.01/nvidia-driver-local-repo-ubuntu2404-590.48.01_1.0-1_amd64.deb}
DRIVER_LOCAL_REPO_DEB=${DRIVER_LOCAL_REPO_DEB:-/tmp/nvidia-driver-local-repo-ubuntu2404-590.48.01_1.0-1_amd64.deb}

if [ "$RUN_HOST_INSTALL" != "1" ]; then
  cat <<'MSG'
Host install is disabled.
To run on a fresh Ubuntu 24.04 Brev instance:
  1. Set RUN_HOST_INSTALL=1 in this cell or notebook environment.
  2. Rerun this script. It downloads and installs NVIDIA driver local repo 590.48.01,
     Docker Engine, and NVIDIA Container Toolkit using sudo.
  3. Reboot if nvidia-smi does not see the driver after cuda-drivers installs.
MSG
  exit 0
fi

if [ "$(. /etc/os-release && echo "$VERSION_ID")" != "24.04" ]; then
  echo "This bootstrap is intended for Ubuntu 24.04 only." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https wget

if [ ! -f "$DRIVER_LOCAL_REPO_DEB" ]; then
  wget -O "$DRIVER_LOCAL_REPO_DEB" "$DRIVER_LOCAL_REPO_URL"
fi
sudo dpkg -i "$DRIVER_LOCAL_REPO_DEB"
sudo cp /var/nvidia-driver-local-repo-ubuntu2404-590.48.01/nvidia-driver-local-D948D85A-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get install -y cuda-drivers

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
else
  echo "Docker already installed: $(docker --version)"
fi
sudo usermod -aG docker "$USER" || true

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd || true

echo "Install complete. Reboot if nvidia-smi does not see the driver yet, then rerun prerequisite checks."
