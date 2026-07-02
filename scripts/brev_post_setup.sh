#!/bin/bash
set -Eeuo pipefail

POST_SETUP_VERSION=2026-07-02.6
WORK_ROOT=${WORK_ROOT:-"$HOME"}
DEEPSTREAM_REPO_URL=${DEEPSTREAM_REPO_URL:-https://github.com/NVIDIA/DeepStream.git}
LAUNCHABLE_REPO_URL=${LAUNCHABLE_REPO_URL:-https://github.com/nv-support/ds_launchable.git}
DEEPSTREAM_IMAGE=${DEEPSTREAM_IMAGE:-nvcr.io/nvidia/deepstream:9.0-triton-multiarch}
SKIP_HOST_SETUP=${SKIP_HOST_SETUP:-0}
SKIP_IMAGE_PULL=${SKIP_IMAGE_PULL:-0}
SKIP_JUPYTER_SETUP=${SKIP_JUPYTER_SETUP:-0}
INSTALL_LAUNCHABLE_OVERLAY=${INSTALL_LAUNCHABLE_OVERLAY:-1}

TARGET_DIR="$WORK_ROOT/deepstream"
TEMP_DIR=""

section() {
  printf '\n=== %s ===\n' "$1"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found"
}

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

install_host_prerequisites() {
  if [[ "$SKIP_HOST_SETUP" == "1" ]]; then
    section "Host setup"
    printf 'Skipped because SKIP_HOST_SETUP=1\n'
    return
  fi

  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf 'Detected host OS: %s %s\n' "${ID:-unknown}" "${VERSION_ID:-unknown}"
  else
    printf 'WARNING: /etc/os-release is unavailable; continuing with capability checks.\n' >&2
  fi

  require_command sudo
  sudo -n true 2>/dev/null \
    || die "passwordless sudo is required for Brev presetup"

  section "Base packages and Docker"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      ca-certificates curl git gnupg poppler-utils
  else
    printf 'WARNING: apt-get is unavailable; using preinstalled host packages.\n' >&2
  fi

  if ! command -v docker >/dev/null 2>&1; then
    require_command apt-get
    require_command curl
    require_command dpkg
    local docker_codename
    docker_codename=$(. /etc/os-release && printf '%s' "${VERSION_CODENAME:-}")
    [[ -n "$docker_codename" ]] \
      || die "VERSION_CODENAME is required to configure Docker's Ubuntu repository"

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | sudo gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    printf '%s\n' \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $docker_codename stable" \
      | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    docker --version
  fi

  local login_user=${SUDO_USER:-${USER:-}}
  [[ -n "$login_user" ]] || login_user=$(id -un)
  sudo usermod -aG docker "$login_user" || true

  section "NVIDIA Container Toolkit"
  if command -v nvidia-ctk >/dev/null 2>&1; then
    printf 'NVIDIA Container Toolkit already installed: '
    nvidia-ctk --version
  else
    require_command apt-get
    require_command curl
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | sudo gpg --batch --yes --dearmor \
        -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nvidia-container-toolkit
  fi
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
}

install_jupyter_widgets() {
  if [[ "$SKIP_JUPYTER_SETUP" == "1" ]]; then
    section "Jupyter widgets"
    printf 'Skipped because SKIP_JUPYTER_SETUP=1\n'
    return
  fi

  section "Jupyter widgets"
  local uv_bin=${UV_BIN:-"$HOME/.local/bin/uv"}
  local venv_python=${BREV_PYTHON:-"$HOME/.venv/bin/python3"}
  local jupyter_bin=${BREV_JUPYTER:-"$HOME/.venv/bin/jupyter"}

  [[ -x "$uv_bin" ]] \
    || die "Brev-managed uv executable not found: $uv_bin"
  [[ -x "$venv_python" ]] \
    || die "Brev-managed Python executable not found: $venv_python"
  [[ -x "$jupyter_bin" ]] \
    || die "Brev-managed Jupyter executable not found: $jupyter_bin"

  "$uv_bin" pip install --python "$venv_python" \
    pip ipywidgets jupyterlab_widgets nbclient nbformat
  "$venv_python" -m pip --version
  "$venv_python" -c 'import ipywidgets, jupyterlab_widgets'

  local labextensions
  labextensions=$("$jupyter_bin" labextension list 2>&1)
  printf '%s\n' "$labextensions"
  grep -Eq '@jupyter-widgets/jupyterlab-manager.*enabled.*OK' <<<"$labextensions" \
    || die "JupyterLab widget manager is not enabled and healthy"

  "$venv_python" -c '
import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_notebook

notebook = new_notebook(cells=[new_code_cell(
    "import ipywidgets as w\n"
    "from IPython.display import display\n"
    "display(w.Button(description=\"widget-smoke\"))"
)])
NotebookClient(notebook, kernel_name="python3", timeout=60).execute()
output = notebook.cells[0].outputs[0]
mime_types = output.get("data", {})
required = "application/vnd.jupyter.widget-view+json"
if required not in mime_types:
    raise SystemExit(f"widget MIME missing: {sorted(mime_types)}")
print("Jupyter widget kernel smoke test: PASS")
'

  printf 'Jupyter widget environment verified; service restart is deferred to the final readiness gate.\n'
}

select_docker_command() {
  if docker info >/dev/null 2>&1; then
    DOCKER=(docker)
  elif [[ "$SKIP_HOST_SETUP" != "1" ]] && sudo docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
  else
    die "Docker daemon is not reachable"
  fi
}

assemble_workspace() {
  section "Clone public repositories"
  require_command git
  require_command tar
  [[ "$INSTALL_LAUNCHABLE_OVERLAY" == "0" || "$INSTALL_LAUNCHABLE_OVERLAY" == "1" ]] \
    || die "INSTALL_LAUNCHABLE_OVERLAY must be 0 or 1"

  [[ ! -e "$TARGET_DIR" ]] \
    || die "target already exists; refusing to modify it: $TARGET_DIR"

  mkdir -p "$WORK_ROOT"
  TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ds-launchable.XXXXXX")

  git clone --depth 1 "$DEEPSTREAM_REPO_URL" "$TARGET_DIR"
  if [[ "$INSTALL_LAUNCHABLE_OVERLAY" == "1" ]]; then
    git clone --depth 1 "$LAUNCHABLE_REPO_URL" "$TEMP_DIR/ds_launchable"

    mkdir -p "$TARGET_DIR/deploy/brev"
    git -C "$TEMP_DIR/ds_launchable" archive --format=tar HEAD \
      | tar -xf - -C "$TARGET_DIR/deploy/brev"

    [[ ! -e "$TARGET_DIR/deploy/brev/.git" ]] \
      || die "unexpected nested Git metadata under deploy/brev"
  else
    printf 'Launchable overlay disabled; using deploy/brev from the DeepStream repository.\n'
  fi

  [[ -f "$TARGET_DIR/deploy/brev/deepstream_code_agent_launchable.ipynb" ]] \
    || die "launchable notebook is missing under $TARGET_DIR/deploy/brev"
}

pull_and_verify_image() {
  if [[ "$SKIP_IMAGE_PULL" == "1" ]]; then
    section "DeepStream image"
    printf 'Skipped because SKIP_IMAGE_PULL=1\n'
    return
  fi

  section "Pull and verify DeepStream image"
  require_command nvidia-smi
  nvidia-smi >/dev/null
  select_docker_command
  "${DOCKER[@]}" pull "$DEEPSTREAM_IMAGE"

  local image_id image_digests
  image_id=$("${DOCKER[@]}" image inspect --format '{{.Id}}' "$DEEPSTREAM_IMAGE")
  image_digests=$("${DOCKER[@]}" image inspect --format '{{json .RepoDigests}}' "$DEEPSTREAM_IMAGE")
  [[ -n "$image_id" ]] || die "DeepStream image has no local image ID"
  [[ -n "$image_digests" && "$image_digests" != "null" && "$image_digests" != "[]" ]] \
    || die "DeepStream image has no repository digest after pull"
  printf 'DeepStream image ID: %s\n' "$image_id"
  printf 'DeepStream image digests: %s\n' "$image_digests"

  "${DOCKER[@]}" run --rm --gpus all "$DEEPSTREAM_IMAGE" nvidia-smi
}

restart_and_wait_for_jupyter() {
  if [[ "$SKIP_JUPYTER_SETUP" == "1" ]]; then
    section "Jupyter readiness"
    printf 'Skipped because SKIP_JUPYTER_SETUP=1\n'
    return
  fi

  section "Jupyter final readiness"
  require_command systemctl
  require_command curl
  sudo systemctl restart jupyter

  local attempt notebook_url
  notebook_url=http://127.0.0.1:8888/api/contents/deepstream/deploy/brev/deepstream_code_agent_launchable.ipynb
  for attempt in $(seq 1 60); do
    if systemctl is-active --quiet jupyter \
      && curl -fsS --max-time 5 \
        -H 'Referer: http://127.0.0.1:8888/' \
        http://127.0.0.1:8888/api/status >/dev/null 2>&1 \
      && curl -fsS --max-time 5 \
        -H 'Referer: http://127.0.0.1:8888/' \
        "$notebook_url" >/dev/null 2>&1; then
      printf 'jupyter.service, HTTP API, and launchable notebook are ready.\n'
      return
    fi
    sleep 2
  done

  systemctl status jupyter --no-pager -l || true
  die "Jupyter did not become ready within 120 seconds"
}

main() {
  printf 'Post-setup version: %s\n' "$POST_SETUP_VERSION"
  install_host_prerequisites
  install_jupyter_widgets
  assemble_workspace
  pull_and_verify_image
  restart_and_wait_for_jupyter

  section "Brev post-setup complete"
  printf 'DeepStream repository: %s\n' "$TARGET_DIR"
  printf 'Launchable notebook:    %s\n' \
    "$TARGET_DIR/deploy/brev/deepstream_code_agent_launchable.ipynb"
}

main "$@"
