#!/usr/bin/env python3
"""Generate the DeepStream Code Agent Brev launchable notebook.

SOURCE OF TRUTH for deepstream_code_agent_launchable.ipynb. The heavy engine (docker
orchestration, the prompt catalog, the agent install script, result rendering) lives in
deploy/brev/scripts/ds_agent_lab.py. The notebook shows the **trunk steps** -- readable
main code -- without the low-level detail:

  * Step 1 (Configuration) is plain Python and Step 2 (Check environment & create workspace) is a `%%bash` cell.
  * Step 3 (Install agent + skills + deps) = agent dropdown + Install.
  * Step 4 (Authenticate) = method dropdown (account sign-in / API key / endpoint) + its fields.
  * Step 5 (Generate) = prompt dropdown + a linked, editable textarea + Generate.
  * Step 6 (Run & view results) = a couple of named lab.* trunk calls.

    python3 deploy/brev/scripts/build_notebook.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


MD_INTRO = """\
# DeepStream Code Agent

**From a natural-language idea to a generated, runtime-validated DeepStream
`pyservicemaker` application.**

This guided lab demonstrates the complete handoff between a coding **agent** and NVIDIA
DeepStream development **skills**. You choose Claude Code or Codex, install it inside a stock
DeepStream container, describe a video analytics scenario, and guide the agent from source
generation through execution and evidence of a working result. The output is a real project --
application code, configuration, launch scripts, documentation, logs, and scenario-specific
artifacts -- rather than a single code snippet.

### What you will learn

By the end of the lab, you will have practiced how to:

- turn an application requirement into an actionable prompt for a DeepStream coding agent;
- use DeepStream skills to keep generated code aligned with `pyservicemaker` conventions;
- separate code generation from runtime validation, so failures can be diagnosed and repaired;
- locate, inspect, and reuse the generated project and its run artifacts.

### Lab flow

```text
Scenario prompt -> coding agent + DeepStream skills -> generated project
                -> runtime services + validation   -> viewable artifacts
```

| Stage | What you do | What the agent/skill does |
| --- | --- | --- |
| 1. Configuration | Review paths, image names, container names, and runtime defaults | Establishes one consistent configuration for every later cell |
| 2. Check environment &amp; create workspace | Validate the GPU host and start the DeepStream container | Creates an isolated, GPU-ready workspace for tools and generated code |
| 3. Install agent, skills &amp; deps | Choose Claude Code or Codex | Installs the selected CLI, DeepStream skills, `pyservicemaker`, and scenario dependencies |
| 4. Authenticate | Select account sign-in, API key, or custom endpoint | Verifies that the selected CLI can reach its model provider |
| 5. Generate | Choose and refine a scenario prompt | Writes the application, configs, launch contract, and supporting documentation |
| 6. Run &amp; view results | Launch the generated project in the prepared runtime | Starts required services, runs and repairs the project, and renders evidence of success |
| 7. Cleanup _(optional)_ | Remove the lab containers | Releases runtime resources while preserving generated code and artifacts |

### Before you start

Make sure the Jupyter host has an NVIDIA GPU, Docker, and the NVIDIA Container Toolkit, and can
pull the configured DeepStream image. Keep `deploy/`, `example_prompts/`, and `skills/` together
under the Jupyter root directory. You will also need credentials for the agent you select.
Image pulls, package installation, model downloads, and agent generation require network access
and can take several minutes on the first run.

Run the numbered cells from top to bottom and wait for the success message in each step before
continuing. The visible cells show the main orchestration; lower-level container, service, and
result-rendering logic lives in `deploy/brev/scripts/ds_agent_lab.py`.

> **Security model:** credentials are accepted at runtime, held in memory, and injected only for
> the relevant agent invocation. They are never baked into the DeepStream image or printed by
> the notebook. Generated projects and artifacts are written to the configured output workspace.

> **Tip — if you refresh the page (F5):** each step renders its result into a live output area,
> which the browser may clear on refresh. Your kernel and generated files are **not** lost. To keep
> these outputs across refreshes, turn on **Settings → Save Widget State Automatically**. To re-show
> a result at any time without re-running the agent, run `lab.show_generated_code()` (Generate step) or
> `lab.show_results()` (Run step).
"""

MD_CONFIG = """\
## 1. Configuration

This cell defines the shared contract for the entire lab. It exports workspace paths, image and
container names, service endpoints, sample media, and minimum driver requirements through
`os.environ`, allowing both Bash cells and the Python lab module to read exactly the same values.

Review these groups before running:

- **Storage:** `OUTPUT_ROOT` is the persistent host-side output location; `WORKSPACE` is mounted
  into the container at `/workspace`. Keep the output root under the Jupyter root if you want to
  browse generated files from the left-hand file browser.
- **Runtime:** `DEEPSTREAM_IMAGE`, `AGENT_CONTAINER`, and `AGENT_HOME` identify the stock
  DeepStream environment in which the agent and generated application will run. `ANTHROPIC_MODEL`
  selects the Claude agent model (default **Claude Opus 4.8** for best code quality; set
  `claude-sonnet-4-6` for cheaper/faster, or empty to use Claude Code's own default).
- **Scenario services:** Kafka, NATS, and VLM settings are consumed only when the selected prompt
  needs those services. The defaults target services started locally by this lab.
- **Input and compatibility:** `SAMPLE_VIDEO` provides a known DeepStream sample, while
  `MIN_DRIVER_VERSION` protects the lab from an unsupported host driver.

The cell assigns every value unconditionally and overwrites existing environment variables each
time it runs. Edit defaults directly in the cell, then re-run it whenever settings change. For all
settings except `AGENT_TIMEOUT`, re-run Step 3 (**Install**) afterward because the lab module
captures those values when imported; `AGENT_TIMEOUT` takes effect on the next Generate instead.

**Checkpoint:** the output should end with `Configuration set` and print the active values you
will use in Step 2. Confirm the paths and image name now; correcting them later may require
recreating the container workspace.
"""

# Plain command-line cell (no `lab` yet) -- colored with the SAME ANSI scheme as klog
# (cyan headers, green OK) so Step 1 reads consistently with the widget steps below.
CODE_CONFIG = '''\
import os, pathlib

_C = {"head": "\\033[1;36m", "ok": "\\033[1;32m", "key": "\\033[0;36m", "off": "\\033[0m"}

_repo = next((p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
              if (p / "deploy/brev/scripts/ds_agent_lab.py").exists()), pathlib.Path.cwd())

# All values below are assigned UNCONDITIONALLY (`os.environ[k] = v`, not `setdefault`): EDIT any of
# them and re-run this cell to change it. `setdefault` would be a no-op on re-run, because os.environ
# persists in the kernel and setdefault only writes when the key is absent. NOTE: for everything
# except AGENT_TIMEOUT you must ALSO re-run the Install cell afterwards -- the lab module snapshots
# these at import time; AGENT_TIMEOUT alone is re-read on the next Generate, so it takes effect at once.
os.environ["REPO_ROOT"] = str(_repo)
# Outputs live in a dir NEXT TO this notebook (deploy/brev/outputs) -- under the Jupyter root_dir, so
# they show in the left file browser. Edit here to relocate.
os.environ["OUTPUT_ROOT"] = str(pathlib.Path(os.environ["REPO_ROOT"]) / "deploy" / "brev" / "outputs")
os.environ["WORKSPACE"] = str(pathlib.Path(os.environ["OUTPUT_ROOT"]) / "workspace")
os.environ["DEEPSTREAM_IMAGE"] = "nvcr.io/nvidia/deepstream:9.0-triton-multiarch"
os.environ["AGENT_CONTAINER"] = "ds-agent-work"
os.environ["AGENT_HOME"] = "/home/agent"
# Agent model for the 'claude' agent. Default = Claude Opus 4.8 (best code quality). Set to
# "claude-sonnet-4-6" for cheaper/faster, or "" to let Claude Code pick its own default.
# (Requires your account/key to have access to the chosen model. Codex uses its own default.)
os.environ["ANTHROPIC_MODEL"] = "claude-opus-4-8"
os.environ["KAFKA_TOPIC"] = "deepstream-agent-demo"
os.environ["KAFKA_BOOTSTRAP"] = "127.0.0.1:9092"
os.environ["NATS_URL"] = "nats://127.0.0.1:4222"
os.environ["NATS_SUBJECT"] = "deepstream.detections"
os.environ["VLM_ENDPOINT"] = "http://127.0.0.1:8000/v1"
os.environ["VLM_MODEL"] = "Qwen/Qwen2.5-VL-3B-Instruct"
os.environ["SAMPLE_VIDEO"] = "/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.mp4"
os.environ["MIN_DRIVER_VERSION"] = "550.0.0"
# Overall BACKSTOP (seconds) on one Generate run -- how long the agent may write + debug before it is
# killed. 3000 = 50 min (heavy prompts like profiling can legitimately need this). Does NOT affect
# demo runtime or MP4 length: live/RTSP runs are bounded separately at the Run step.
os.environ["AGENT_TIMEOUT"] = "3000"

print(f"{_C['head']}=== Global configuration ==={_C['off']}")
for key in [
    "REPO_ROOT", "OUTPUT_ROOT", "WORKSPACE", "DEEPSTREAM_IMAGE",
    "AGENT_CONTAINER", "AGENT_HOME", "ANTHROPIC_MODEL", "AGENT_TIMEOUT", "MIN_DRIVER_VERSION",
]:
    print(f"  {_C['key']}{key}{_C['off']}={os.environ[key]}")
print(f"{_C['ok']}\\u2705 Configuration set -- continue to Step 2 (Check Environment & Create a DeepStream container workspace).{_C['off']}")
'''

MD_PREPARE = """\
## 2. Check Environment & Create a DeepStream container workspace

Build and validate the sandbox before asking an agent to write code. Keeping generation inside
a stock DeepStream container makes the resulting project testable against the same SDK,
plugins, Python environment, and GPU runtime that it is expected to use.

The command-line cell performs four phases:

1. **Validate the host:** detect the GPU and driver, confirm Docker access, exercise the NVIDIA
   Container Toolkit, and report available disk space.
2. **Prepare the image:** apply the local Docker/NVCR workaround and pull the configured
   DeepStream image when it is not already cached.
3. **Stage the workspace:** create the persistent output directories, copy the example prompt
   catalog, and expose the workspace at `/workspace` inside the container.
4. **Start the sandbox:** replace any existing lab container with a clean long-lived container,
   pass in the scenario service settings, and stage the sample video when available.

Run Step 1 first, then run this cell once and allow any first-time image pull to finish. Re-running
the cell recreates the container but preserves files in the host-mounted workspace, making it a
useful recovery step when the container becomes stale.

**Checkpoint:** look for `Environment ready`, the container name, and the mounted workspace path.
If the cell stops earlier, fix the first red error before continuing -- the most common causes
are an inaccessible Docker daemon, a missing NVIDIA Container Toolkit, insufficient image-registry
access, or a driver older than `MIN_DRIVER_VERSION`.
"""

# Command-line (bash) step. Colored with the SAME ANSI scheme as klog -- section()/ok()/fail()
# emit cyan headers, green success, red errors, so this step reads consistently with the
# widget steps (which use step_status's HTML banner). `%%bash` must stay the first line.
CODE_PREPARE = '''\
%%bash
set -euo pipefail

C_HEAD='\\033[1;36m'; C_OK='\\033[1;32m'; C_ERR='\\033[1;31m'; C_OFF='\\033[0m'
section() { printf "${C_HEAD}=== %s ===${C_OFF}\\n" "$1"; }
ok()      { printf "${C_OK}%s${C_OFF}\\n" "$1"; }
fail()    { printf "${C_ERR}ERROR: %s${C_OFF}\\n" "$*" >&2; exit 1; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 is not installed or not on PATH"
}

version_ge() {
    [ "$(printf '%s\\n%s\\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

section "NVIDIA Driver & GPU"
require_command nvidia-smi
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader

GPU_COUNT=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l | tr -d ' ')
[ "$GPU_COUNT" -gt 0 ] || fail "No NVIDIA GPUs detected"
ok "Detected $GPU_COUNT GPU(s)"

DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d ' ')
version_ge "$DRIVER_VERSION" "$MIN_DRIVER_VERSION" \\
    || fail "NVIDIA driver $DRIVER_VERSION is older than required $MIN_DRIVER_VERSION"
ok "NVIDIA driver: OK ($DRIVER_VERSION >= $MIN_DRIVER_VERSION)"
echo ""

section "Docker"
require_command docker
docker ps >/dev/null 2>&1 \\
    || fail "Docker daemon is not reachable by this user. Add the user to the docker group or start Docker."
ok "Docker daemon: OK"
echo ""

section "Disk Space"
df -h / | tail -1 | awk '{print "Root:", $4, "available of", $2}'
ok "Prerequisites check passed."
echo ""

section "Prepare DeepStream sandbox"

for required_var in \\
    REPO_ROOT OUTPUT_ROOT WORKSPACE DEEPSTREAM_IMAGE AGENT_CONTAINER AGENT_HOME \\
    KAFKA_TOPIC KAFKA_BOOTSTRAP NATS_URL NATS_SUBJECT VLM_ENDPOINT VLM_MODEL \\
    SAMPLE_VIDEO MIN_DRIVER_VERSION; do
    [ -n "${!required_var:-}" ] || fail "$required_var is not set. Run the Step 1 configuration cell first."
done

python3 "$REPO_ROOT/deploy/brev/scripts/configure_docker_nvcr_workaround.py"

if ! docker image inspect "$DEEPSTREAM_IMAGE" >/dev/null 2>&1; then
    if [[ "$DEEPSTREAM_IMAGE" == nvcr.io* ]] && [ -n "${NGC_API_KEY:-}" ]; then
        printf '%s' "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
    fi
    echo "Pulling $DEEPSTREAM_IMAGE ..."
    docker pull "$DEEPSTREAM_IMAGE"
else
    ok "DeepStream image present: $DEEPSTREAM_IMAGE"
fi

# Validate the NVIDIA Container Toolkit only after the image is present, so a missing
# image or NVCR credential failure is not misreported as a toolkit failure.
section "NVIDIA Container Toolkit"
docker run --rm --gpus all "$DEEPSTREAM_IMAGE" nvidia-smi >/dev/null 2>&1 \\
    || fail "NVIDIA Container Toolkit is not functional. Install or repair it: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
ok "NVIDIA Container Toolkit: OK"

mkdir -p "$WORKSPACE/agent_outputs"
rm -rf "$WORKSPACE/example_prompts"
cp -a "$REPO_ROOT/example_prompts" "$WORKSPACE/example_prompts"

if docker ps -aq -f "name=^${AGENT_CONTAINER}$" | grep -q .; then
    docker rm -f "$AGENT_CONTAINER" >/dev/null
fi

docker run -d \\
    --name "$AGENT_CONTAINER" \\
    --gpus all \\
    --network host \\
    -w /workspace \\
    -e "HOME=$AGENT_HOME" \\
    -e "KAFKA_TOPIC=$KAFKA_TOPIC" \\
    -e "KAFKA_BOOTSTRAP=$KAFKA_BOOTSTRAP" \\
    -e "NATS_URL=$NATS_URL" \\
    -e "NATS_SUBJECT=$NATS_SUBJECT" \\
    -e "VLM_ENDPOINT=$VLM_ENDPOINT" \\
    -e "VLM_MODEL=$VLM_MODEL" \\
    -v "$WORKSPACE:/workspace" \\
    "$DEEPSTREAM_IMAGE" \\
    sleep infinity

docker exec "$AGENT_CONTAINER" bash -lc "true"

if [ ! -f "$WORKSPACE/sample_720p.mp4" ]; then
    docker exec "$AGENT_CONTAINER" cp "$SAMPLE_VIDEO" /workspace/sample_720p.mp4 \\
        || echo "NOTE: could not stage $SAMPLE_VIDEO into the workspace; continuing."
fi

echo ""
ok "✅ Environment ready. Container '$AGENT_CONTAINER' is running."
ok "Workspace mounted at: $WORKSPACE"
'''

MD_STEP2 = """\
## 3. Install your agent & DeepStream skills & Runtime dependencies

Choose the coding agent that will interpret the prompt and author the project, then click
**Install**. The installation happens inside the container created in Step 2; it does not modify
the host Python environment.

The installer adds:

- the selected agent CLI (**Claude Code** or **Codex**);
- the DeepStream skill bundle that supplies domain-specific implementation and validation guidance;
- `pyservicemaker` and the runtime packages required by the included scenarios.

This step deliberately separates software installation from authentication. You can therefore
inspect or repeat the setup without placing credentials in an image layer. Installation can take
several minutes when packages are not cached, so leave the kernel connected until it completes.

**Checkpoint:** wait for the green completion banner before opening Step 4. Re-run **Install** if
you recreate the container in Step 2, switch to the other agent, or update the lab's Python
modules and want the notebook kernel to reload them.
"""

CODE_STEP2 = '''\
try:
    import ipywidgets as w
    from IPython.display import display
except ImportError:
    w = None

if w is not None:
    agent_dd = w.Dropdown(options=["claude", "codex"], value="claude", description="Agent:")
    install_btn = w.Button(description="Install", button_style="primary", icon="download")
    out2 = w.Output(layout=w.Layout(border="1px solid #ccc"))

    def _on_install(_):
        lab.AGENT = agent_dd.value                          # read the dropdown on the UI thread
        lab.set_selection(lab.AGENT, None)
        lab.run_step(out2, install_btn, "Install agent", lab.install_agent,
                              success_flag="installed")

    install_btn.on_click(_on_install)
    print("Pick an agent and click Install (CLI + DeepStream skills + deps). This may take a few minutes.")
    display(w.VBox([w.HBox([agent_dd, install_btn]), out2]))
else:
    print("ipywidgets unavailable -- plain fallback:")
    print("  lab.AGENT = 'claude'              # or 'codex'")
    print("  lab.set_selection(lab.AGENT, None); lab.install_agent()")
'''

MD_AUTH = """\
## 4. Authenticate

Authenticate the CLI installed in Step 3. Choose exactly one method from the dropdown; the form
shows only the fields required for that method.

| Method | Use it when | What to do |
| --- | --- | --- |
| **Account sign-in** | You use a Claude subscription or an Anthropic Console account | Choose the account type, click **Start sign-in**, open the URL, complete sign-in, paste the returned code, and click **Submit** |
| **API key** | You have a direct Anthropic key for Claude or OpenAI key for Codex | Paste the key and click **Apply & verify** |
| **Custom endpoint** | Your organization exposes an Anthropic-compatible proxy or gateway | Enter its base URL and token, then click **Apply & verify** |

For Claude account sign-in, use **Claude subscription (`--claudeai`)** for Pro, Max, or Team
accounts. Use **Anthropic Console (`--console`)** for API-billing accounts or when organizational
policy blocks subscription sign-in. The completed flow is verified with `claude auth status`.

> **Codex account sign-in:** Codex uses a `localhost:1455` callback rather than the paste-code
> flow shown by this widget. Tunnel that port to the container environment and run `codex login`,
> or use an OpenAI API key here.

Credentials entered in the widget are held in kernel memory and injected per agent call; they
are not printed or added to the container image. Advanced users may instead define
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_BASE_URL` plus
`ANTHROPIC_AUTH_TOKEN` before launch.

**Checkpoint:** do not continue until verification succeeds. Authentication errors at Generate
time are usually resolved by returning here and reapplying the credential; if you restarted the
kernel, credentials held only in memory must be entered again.
"""

CODE_AUTH = '''\
try:
    import ipywidgets as w
    from IPython.display import display
except ImportError:
    w = None

if w is not None:
    method = w.Dropdown(
        options=[("Account sign-in", "account"), ("API key", "key"), ("Custom endpoint", "endpoint")],
        value="account", description="Method:",
    )

    # -- Account sign-in (OAuth paste-code) --
    acct_kind = w.Dropdown(
        options=[("Claude subscription (--claudeai)", "claudeai"),
                 ("Anthropic Console / API billing (--console)", "console")],
        value="claudeai", description="Account:", layout=w.Layout(width="55%"),
    )
    start_btn = w.Button(description="Start sign-in", button_style="primary", icon="sign-in")
    code_in = w.Text(description="Code:", placeholder="paste the code from the browser",
                     layout=w.Layout(width="55%"))
    submit_btn = w.Button(description="Submit", button_style="success", icon="check")
    account_box = w.VBox([acct_kind, w.HBox([start_btn, code_in, submit_btn])])

    # -- API key --
    key_in = w.Password(description="API key:", layout=w.Layout(width="55%"),
                        placeholder="Anthropic key (claude) or OpenAI key (codex)")
    key_apply = w.Button(description="Apply & verify", button_style="info", icon="key")
    key_box = w.VBox([key_in, key_apply])

    # -- Custom endpoint (Anthropic-compatible, Claude) --
    base_in = w.Text(description="Base URL:", layout=w.Layout(width="55%"),
                     placeholder="https://your-proxy/v1")
    tok_in = w.Password(description="Token:", layout=w.Layout(width="55%"),
                        placeholder="token for the custom endpoint")
    ep_apply = w.Button(description="Apply & verify", button_style="info", icon="key")
    endpoint_box = w.VBox([base_in, tok_in, ep_apply])

    out2 = w.Output(layout=w.Layout(border="1px solid #ccc"))
    _boxes = {"account": account_box, "key": key_box, "endpoint": endpoint_box}

    def _show(which):
        for _k, _b in _boxes.items():
            _b.layout.display = "" if _k == which else "none"

    def _on_method(change):
        if change["name"] == "value":
            _show(change["new"])

    method.observe(_on_method, names="value")
    _show(method.value)

    def _on_start(_):
        use_console = acct_kind.value == "console"
        lab.run_step(out2, start_btn, "Start sign-in", lambda: lab.login_start(use_console))

    def _on_submit(_):
        code = code_in.value
        # login_submit prints `claude auth status`, which is the verification for OAuth
        # (check_auth's smoke only fires for env-based key/endpoint creds, not stored OAuth).
        lab.run_step(out2, submit_btn, "Sign in", lambda: lab.login_submit(code))

    def _apply_key():
        if key_in.value:
            setattr(lab, "ANTHROPIC_API_KEY" if lab.AGENT == "claude" else "OPENAI_API_KEY", key_in.value)
        lab.check_auth()

    def _apply_endpoint():
        lab.ANTHROPIC_BASE_URL = base_in.value.strip()
        lab.ANTHROPIC_AUTH_TOKEN = tok_in.value.strip()
        lab.check_auth()

    start_btn.on_click(_on_start)
    submit_btn.on_click(_on_submit)
    key_apply.on_click(lambda _: lab.run_step(out2, key_apply, "Apply & verify", _apply_key))
    ep_apply.on_click(lambda _: lab.run_step(out2, ep_apply, "Apply & verify", _apply_endpoint))

    display(w.VBox([method, account_box, key_box, endpoint_box, out2]))
else:
    print("ipywidgets unavailable -- plain fallback, run ONE of:")
    print("  #  account : lab.login_start(); lab.login_submit('<code>')        # --claudeai (default)")
    print("  #            lab.login_start(use_console=True); lab.login_submit('<code>')  # --console")
    print("  #  api key : lab.ANTHROPIC_API_KEY='sk-...'  (or lab.OPENAI_API_KEY); lab.check_auth()")
    print("  #  endpoint: lab.ANTHROPIC_BASE_URL='https://.../v1'; lab.ANTHROPIC_AUTH_TOKEN='...'; lab.check_auth()")
'''

MD_STEP3 = """\
## 5. Pick a prompt and generate

This is the authoring stage: a natural-language requirement becomes a structured DeepStream
`pyservicemaker` project. Select an example from the dropdown to load its full text into the
editor, then use it as-is, refine it, or replace it with your own scenario.

### Prompt guide and approximate time

Use the table below to choose a scenario that matches what you want to demonstrate. The time
columns are intentionally coarse planning estimates, not service-level guarantees. **Generate**
covers Step 5; **Run & validate** covers service preparation, agent-assisted execution and repair,
and result rendering in Step 6.

| Prompt | Typical usage | Expected result | Generate | Run & validate |
| --- | --- | --- | ---: | ---: |
| `import_vision_model_detection_pipeline` | Onboard an object-detection model end to end: convert it, build a TensorRT engine, benchmark it, and document the result | Model files, DeepStream configs, benchmark evidence, and a PDF report | ~15–30 min | ~1–2 min |
| `ds_profiling_efficient_pipeline` | Measure a multi-stream pipeline, identify its bottleneck, and estimate the sustainable stream count | Nsight-based profiling report and an optimized pipeline project | ~7–12 min | ~12–20 min |
| `msgbroker_nats` | Publish DeepStream object metadata through a NATS/JetStream message adapter | Runnable publisher plus captured NATS JSON messages | ~10–15 min | ~7–12 min |
| `msgconv_kafka` | Convert DeepStream metadata and publish it to a Kafka topic | Runnable pipeline plus captured Kafka JSON messages | ~3–6 min | ~5–10 min |
| `multi_stream_tracker` | Combine four RTSP sources with inference, tracking, and a tiled display | Annotated tiled MP4 with persistent track IDs | ~3–6 min | ~15–25 min |
| `nvdsanalytics_config_sample` | Demonstrate ROI filtering, line crossing, overcrowding, and direction rules | Annotated MP4 showing `nvdsanalytics` results | ~5–10 min | ~4–8 min |
| `nvdsdynamicsrcbin_app` | Exercise dynamic source addition and removal in a running DeepStream pipeline | Runnable dynamic-source app and lifecycle logs | ~3–6 min | ~4–8 min |
| `rtvi_vlm_core_app & rtvi_vlm_openapi_spec` | Build the RTVI VLM pipeline, then add a FastAPI service around it in a second generation stage | VLM summaries, Kafka output, service code, OpenAPI spec, and API response | ~15–25 min | ~8–15 min |
| `single_view_3d_tracker` | Track objects in 3D from a single camera and render the tracked result | Annotated MP4 from the single-view 3D tracker | ~7–12 min | ~8–15 min |
| `video_infer_app` | Start with a compact file-based TrafficCamNet inference and OSD example | Runnable starter project and annotated MP4 | ~2–5 min | ~3–6 min |
| `video_object_count` | Count detected objects in a video and present the counts with the stream | Object-count application and annotated MP4 | ~2–5 min | ~3–6 min |
| `video_parallel_infer_app` | Run parallel inference branches and merge their metadata into one output | Multi-model pipeline and annotated merged MP4 | ~12–20 min | ~20–30 min |
| `yolov26s_detection` | Convert YOLO26s for DeepStream and build a complete detection application | Converted model, DeepStream project, and annotated MP4 | ~5–10 min | ~8–15 min |

> **Timing notes:** the ranges are coarse, derived from a measured warm run (DeepStream image,
> Python packages, model files, and TensorRT engines already cached). A first/cold run adds time
> for image pulls, model downloads, VLM startup, or engine builds — e.g. `import_vision` does its
> engine build + benchmark at **Generate** (cached ~15 min; a cold first-ever TensorRT engine build
> can add significant time on top).
> **Run & validate** time is dominated by how many run-and-repair iterations the agent needs, so
> the harder scenarios (live multi-stream RTSP, multi-model parallel) sit at the high end and vary
> the most. Actual time also depends on GPU performance, network bandwidth, and prompt edits.

<sub>Measured with Claude Code's default agent model **`claude-sonnet-4-6`** (no `ANTHROPIC_MODEL` override) and default thinking mode (no override set).</sub>

A productive prompt states the desired **input**, **processing or model**, **output**,
**integration constraints**, and **evidence of success**. Be explicit about details that matter
to your deployment -- for example, RTSP versus a file source, message schema, service ports,
model format, expected artifact, or a bounded run duration. The DeepStream skills supply
framework conventions, but they cannot infer unstated product requirements.

When you click **Generate**, the notebook combines the edited scenario with the mounted workspace,
service contracts, and DeepStream skill instructions. The agent is expected to create:

- readable `pyservicemaker` application code and scenario configuration;
- scripts or commands that provide a repeatable run contract;
- a concise README describing the project, dependencies, and usage;
- generation transcripts and downloadable output under the configured workspace.

Generation is intentionally separate from execution. This step authors and previews the files;
it does not yet prove that service images, models, streams, or external endpoints work in the
current runtime. That validation -- including bounded agent-assisted repair -- happens in Step 6.

**Checkpoint:** inspect the rendered file preview and confirm that the generated project matches
the selected scenario before running it. Files are stored beneath the host-side `WORKSPACE`
(mounted as `/workspace`), while agent transcripts and later run artifacts are grouped under
`WORKSPACE/agent_outputs/<prompt_id>/`. Use `lab.show_generated_code()` to redisplay the preview
without spending another agent call.
"""

CODE_STEP3 = '''\
try:
    import ipywidgets as w
    from IPython.display import display
except ImportError:
    w = None

if w is not None:
    default_prompt = ("video_infer_app" if "video_infer_app" in lab.MENU_PROMPT_IDS
                      else lab.MENU_PROMPT_IDS[0])
    prompt_dd = w.Dropdown(options=lab.MENU_PROMPT_IDS, value=default_prompt,
                           description="Prompt:", layout=w.Layout(width="60%"))
    prompt_status = w.HTML()   # visible confirmation a pick loaded (prompts share a first line)
    prompt_tx = w.Textarea(value=lab.prompt_text(prompt_dd.value),
                           layout=w.Layout(width="98%", height="240px"))
    lab.set_selection(lab.AGENT, prompt_dd.value)

    def _set_status(pid):
        prompt_status.value = (f"<span style='color:#1a7f37'>&#9989; loaded prompt: "
                               f"<b>{pid}</b> &mdash; edit below or pick another</span>")

    def _on_pick(change):   # dropdown -> textarea: load the picked prompt's text (live link)
        lab.set_selection(lab.AGENT, change["new"])
        prompt_tx.value = lab.prompt_text(change["new"])
        _set_status(change["new"])      # green line changes even when the text's first line looks the same

    def _on_prompt_edit(change):
        if change["name"] == "value":
            lab.state["generated"] = False
            run_control = globals().get("run_btn")
            if run_control is not None:
                run_control.disabled = True

    prompt_dd.observe(_on_pick, names="value")
    prompt_tx.observe(_on_prompt_edit, names="value")
    _set_status(prompt_dd.value)

    gen_btn = w.Button(description="Generate", button_style="primary", icon="cogs")
    out3 = w.Output()

    def _on_generate(_):
        pid, txt = prompt_dd.value, prompt_tx.value          # read widgets on the UI thread
        generated_ok = lab.run_step(out3, gen_btn, "Generate",
                              lambda: (lab.select_from_ui(pid, txt), lab.generate()),
                              requires="installed", success_flag="generated",
                              controls=tuple(c for c in (
                                  prompt_dd, prompt_tx, globals().get("run_btn")
                              ) if c is not None))
        run_control = globals().get("run_btn")
        if run_control is not None:
            run_control.disabled = not generated_ok

    gen_btn.on_click(_on_generate)
    display(prompt_dd, prompt_status, prompt_tx, gen_btn, out3)
else:
    print("ipywidgets unavailable -- run the loader cell, or:  "
          "lab.set_selection(lab.AGENT, 'video_infer_app'); lab.generate()")
'''

MD_STEP4 = """\
## 6. Run and view results

Now validate the generated project against the current DeepStream runtime. This step may modify
the generated files: the goal is not merely to launch the first draft, but to leave behind a
version that has been exercised and adapted to the actual container, services, and media inputs.

Click **Run & view results** to execute three coordinated phases:

1. **Prepare services:** start only the infrastructure required by the selected scenario, such
   as an RTSP source, Kafka, NATS, or the optional VLM endpoint.
2. **Run and repair:** re-invoke the agent with a bounded runtime contract, execute the generated
   project, inspect concrete failures, patch its files when necessary, and retry within the
   configured time limits.
3. **Render evidence:** collect and display the scenario-specific result rather than relying on
   a process exit code alone.

Depending on the prompt, evidence can be an annotated video preview, Kafka or NATS messages, a
PDF or profiling report, service logs, an OpenAPI document, or a live API response. Long-running
video and service scenarios are intentionally bounded so that control returns to the notebook.

**Checkpoint:** review both the inline result and the corresponding directory under
`WORKSPACE/agent_outputs/<prompt_id>/`. Agent transcripts explain what was attempted; application
logs and artifacts provide the stronger proof that the scenario ran. Use `lab.show_results()` to
render saved artifacts again after a page refresh without repeating generation or execution.
"""

CODE_STEP4 = '''\
try:
    import ipywidgets as w
    from IPython.display import display
except ImportError:
    w = None

if w is not None:
    run_btn = w.Button(description="Run & view results", button_style="success", icon="play",
                       disabled=not lab.state["generated"])
    out4 = w.Output()

    def _on_run(_):
        # Start services, then RE-INVOKE the agent to run + fix the app it wrote, then show results.
        lab.run_step(out4, run_btn, "Run",
                              lambda: (lab.prepare_services(), lab.run_and_fix(), lab.show_results()),
                              requires="generated",
                              controls=tuple(c for c in (
                                  globals().get("prompt_dd"), globals().get("prompt_tx"),
                                  globals().get("gen_btn")
                              ) if c is not None))

    run_btn.on_click(_on_run)
    display(run_btn, out4)
else:
    print("ipywidgets unavailable -- run: lab.prepare_services(); lab.run_and_fix(); lab.show_results()")
'''

MD_CLEANUP = """\
## 7. Cleanup _(optional)_

Use cleanup when you have finished inspecting the demo or need to release GPU, container, and
service resources. Clicking **Cleanup containers** removes the DeepStream agent lab containers
and any scenario services managed by the lab.

By default, cleanup does **not** remove the host-mounted generated project or its result
artifacts. They remain beneath `OUTPUT_ROOT`, where you can review, download, version, or adapt
them for a real application. Outputs are removed only when cleanup is explicitly called with
`remove_outputs=True` or `REMOVE_AGENT_OUTPUTS=1` is set. If you want another run later, start
again at Step 2 to recreate the container, then repeat installation and authentication before
generating or running a scenario.

**Before leaving the lab:** capture the final generated project, its README, the relevant result
artifact, and the run transcript. Together they record the requirement, implementation, and
runtime evidence needed to reproduce or continue the work outside this notebook.
"""

CODE_CLEANUP = '''\
try:
    import ipywidgets as w
    from IPython.display import display
except ImportError:
    w = None

if w is not None:
    clean_btn = w.Button(description="Cleanup containers", button_style="danger", icon="trash")
    outc = w.Output()

    def _on_cleanup(_):
        lab.run_step(outc, clean_btn, "Cleanup", lab.cleanup_containers)

    clean_btn.on_click(_on_cleanup)
    display(clean_btn, outc)
else:
    print("ipywidgets unavailable -- run: lab.cleanup_containers()")
'''

# Prepended to every step cell: the FIRST one to run loads `lab` AND ensures the control deps,
# then renders -- so "load the kernel" and "show the controls" are ONE step (no separate loader
# cell). Idempotent: skips if `lab` is already defined.
_BOOT = '''\
import sys, pathlib  # first step cell to run loads the lab + control deps, then renders
if "lab" not in globals():
    _r = next((p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
               if (p / "deploy/brev/scripts/ds_agent_lab.py").exists()), pathlib.Path.cwd())
    sys.path.insert(0, str(_r / "deploy/brev/scripts")); import ds_agent_lab as lab
    lab.ensure_ipywidgets()

'''

# FIRST lab-loading cell ONLY (Step 3, Install): (re)load the lab modules FRESH -- drop any cached
# copies first -- so a REDEPLOY of the .py files takes effect just by re-running it (no kernel
# restart needed). Later steps use _BOOT (reuse the already-loaded `lab`) so the agent/creds/
# selection set in the Install/Sign-in/Generate steps survive across cells.
_BOOT_FRESH = '''\
import sys, pathlib  # Install step: (re)load the lab modules fresh, ensure control deps, then render
_r = next((p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]
           if (p / "deploy/brev/scripts/ds_agent_lab.py").exists()), pathlib.Path.cwd())
sys.path.insert(0, str(_r / "deploy/brev/scripts"))
for _m in ("ds_agent_lab", "ds_lab_config"):
    sys.modules.pop(_m, None)
import ds_agent_lab as lab
lab.ensure_ipywidgets()

'''


def build_cells():
    # Step 1 (config) is plain Python and Step 2 (prepare) is a `%%bash` cell -- neither loads
    # `lab`, so the FIRST lab-loading cell is Step 3 (Install): it gets _BOOT_FRESH so re-running
    # it picks up a redeployed .py without a kernel restart. Later steps use _BOOT (reuse the
    # already-loaded `lab`) so the agent/creds/selection set in Steps 3-5 survive across cells.
    return [
        ("md", MD_INTRO),
        ("md", MD_CONFIG),
        ("code", CODE_CONFIG),
        ("md", MD_PREPARE),
        ("code", CODE_PREPARE),
        ("md", MD_STEP2),
        ("code", _BOOT_FRESH + CODE_STEP2),
        ("md", MD_AUTH),
        ("code", _BOOT + CODE_AUTH),
        ("md", MD_STEP3),
        ("code", _BOOT + CODE_STEP3),
        ("md", MD_STEP4),
        ("code", _BOOT + CODE_STEP4),
        ("md", MD_CLEANUP),
        ("code", _BOOT + CODE_CLEANUP),
    ]


def main() -> int:
    nb = new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    cells = []
    for idx, (kind, src) in enumerate(build_cells()):
        src = src.rstrip("\n")
        if kind == "md":
            cell = new_markdown_cell(src)
        else:
            cell = new_code_cell(src)
            cell["execution_count"] = None
            cell["outputs"] = []
        cell["id"] = f"cell-{idx:02d}"
        cells.append(cell)
    nb["cells"] = cells

    out_path = Path(__file__).resolve().parents[1] / "deepstream_code_agent_launchable.ipynb"
    with out_path.open("w") as f:
        nbformat.write(nb, f)
    text = out_path.read_text()
    if not text.endswith("\n"):
        out_path.write_text(text + "\n")
    print(f"Wrote {out_path} ({len(cells)} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
