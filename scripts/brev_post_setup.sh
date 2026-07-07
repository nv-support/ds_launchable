#!/bin/bash
set -Eeuo pipefail

POST_SETUP_VERSION=2026-07-07.2
WORK_ROOT=${WORK_ROOT:-"$HOME"}
DEEPSTREAM_IMAGE=${DEEPSTREAM_IMAGE:-nvcr.io/nvidia/deepstream:9.0-triton-multiarch}
SKIP_HOST_SETUP=${SKIP_HOST_SETUP:-0}
SKIP_IMAGE_PULL=${SKIP_IMAGE_PULL:-0}
SKIP_JUPYTER_SETUP=${SKIP_JUPYTER_SETUP:-0}

TARGET_DIR="$WORK_ROOT/deepstream"

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

prepare_jupyter_environment() {
  if [[ "$SKIP_JUPYTER_SETUP" == "1" ]]; then
    section "Jupyter environment"
    printf 'Skipped because SKIP_JUPYTER_SETUP=1\n'
    return
  fi

  section "Jupyter environment"
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

  require_command curl
  local attempt
  for attempt in $(seq 1 60); do
    if curl -fsS --max-time 5 \
      -H 'Referer: http://127.0.0.1:8888/' \
      http://127.0.0.1:8888/api/status >/dev/null 2>&1; then
      printf 'Jupyter dependencies, widget MIME, and HTTP API are ready.\n'
      return
    fi
    sleep 2
  done

  die "Jupyter HTTP API did not become ready within 120 seconds"
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

install_launchable_clone_hook() {
  section "Install launchable clone hook"
  require_command git
  require_command tar

  local deepstream_repo_url=${DEEPSTREAM_REPO_URL:-https://github.com/NVIDIA/DeepStream.git}
  local launchable_repo_url=${LAUNCHABLE_REPO_URL:-https://github.com/nv-support/ds_launchable.git}
  local template_dir="$HOME/.local/share/ds-launchable/git-template"
  local hook_path="$template_dir/hooks/post-checkout"

  mkdir -p "$template_dir/hooks"
  cat >"$hook_path" <<HOOK
#!/bin/bash
set -Eeuo pipefail

expected_remote=$(printf '%q' "$deepstream_repo_url")
launchable_repo_url=$(printf '%q' "$launchable_repo_url")
template_dir=$(printf '%q' "$template_dir")

origin=\$(git remote get-url origin 2>/dev/null || true)
hook_path=\$(git rev-parse --git-path hooks/post-checkout)
if [[ "\${origin%.git}" != "\${expected_remote%.git}" ]]; then
  rm -f "\$hook_path"
  exit 0
fi

unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX

configured_template=\$(git config --global --get init.templateDir || true)
if [[ "\$configured_template" == "\$template_dir" ]]; then
  git config --global --unset-all init.templateDir
fi
rm -rf "\$template_dir"

temp_dir=\$(mktemp -d "\${TMPDIR:-/tmp}/ds-launchable.XXXXXX")
cleanup() { rm -rf "\$temp_dir"; }
trap cleanup EXIT

printf '\n=== Install launchable overlay after DeepStream clone ===\n'
git clone --depth 1 "\$launchable_repo_url" "\$temp_dir/ds_launchable"
mkdir -p deploy/brev
git -C "\$temp_dir/ds_launchable" archive --format=tar HEAD \
  | tar -xf - -C deploy/brev

[[ ! -e deploy/brev/.git ]] \
  || { printf 'ERROR: unexpected nested Git metadata under deploy/brev\n' >&2; exit 1; }
[[ -f deploy/brev/deepstream_code_agent_launchable.ipynb ]] \
  || { printf 'ERROR: launchable notebook is missing under deploy/brev\n' >&2; exit 1; }

rm -f "\$hook_path"
printf 'Launchable overlay installed under %s/deploy/brev\n' "\$PWD"
HOOK

  chmod 0755 "$hook_path"
  git config --global init.templateDir "$template_dir"
  printf 'One-time Git template installed: %s\n' "$template_dir"
  printf 'It will overlay ds_launchable when Brev clones: %s\n' "$deepstream_repo_url"
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

main() {
  printf 'Post-setup version: %s\n' "$POST_SETUP_VERSION"
  install_host_prerequisites
  install_launchable_clone_hook
  pull_and_verify_image
  prepare_jupyter_environment

  section "Brev post-setup complete"
  printf 'Expected DeepStream repository: %s\n' "$TARGET_DIR"
  printf 'Launchable notebook after clone: %s\n' \
    "$TARGET_DIR/deploy/brev/deepstream_code_agent_launchable.ipynb"
}

main "$@"
