# DeepStream Code Agent -- launchable

A guided Jupyter notebook that turns a **natural-language prompt into a runnable DeepStream
`pyservicemaker` app**. You pick a coding agent (Claude Code or Codex), install it into a stock
DeepStream container, give it a scenario prompt, and it generates the app + configs + run scripts,
runs it, and shows the result (MP4 / Kafka JSON / PDF report / VLM summary / FastAPI service).

The notebook is six steps plus an optional cleanup:

1. **Configuration** -- set the shared paths, image/container names, and runtime defaults (exported to env).
2. **Check environment & create a DeepStream container workspace** -- check the GPU host, then start the stock DeepStream container with a mounted workspace.
3. **Install your agent, DeepStream skills & runtime dependencies** -- choose Claude or Codex; installs the CLI + DeepStream skills + runtime deps.
4. **Authenticate** -- provide credentials via account sign-in, an API key, or a custom endpoint (pick one from the method dropdown).
5. **Generate** -- pick (or paste/edit) a scenario prompt; the agent writes the code, shown inline.
6. **Run and view results** -- start the services the scenario needs, run + fix the app (modifying the generated code for the current runtime), and render the result.
7. **Cleanup** _(optional)_ -- remove the lab containers; generated code + artifacts stay in the output workspace.

Generate and Run are separate stateful operations. Generate leaves implementation choices to the
agent; a prompt may cause the agent to run its own checks, but the notebook does not require a
general application run during this step. Run applies the selected scenario's runtime instructions
and validates the resulting artifacts. While either operation is active, the prompt selector,
prompt editor, and the other operation button are disabled. Changing the selected prompt or editing
its text invalidates the previous Generate result, so Run cannot accidentally use artifacts from a
different prompt.

Run works on an isolated copy so any runtime repair leaves the Generate output unchanged. The copy
keeps application source, configuration, prompt-specific resources, ONNX models, TensorRT engines,
parser shared libraries, and other generated artifacts. It excludes virtual environments,
dependency installations, repository metadata, and disposable language/tool caches (`venv`,
`.venv`, `node_modules`, `__pycache__`, `.cache`, test/type-check caches, and `.git`). If an
application needs a runtime environment, its Run-stage setup creates one in the Run copy; a
Generate-stage virtual environment is not treated as portable application content.

## Files

```
<deepstream root>/                           # repository root = Jupyter root_dir
  deploy/brev/
    deepstream_code_agent_launchable.ipynb   # the notebook (GENERATED -- do not hand-edit for logic)
    README.md
    scripts/
      brev_post_setup.sh  # fresh-Brev host, clone hook, image, and readiness setup
      build_notebook.py    # SOURCE OF TRUTH for the .ipynb (run it to regenerate)
      ds_lab_config.py     # config + PROMPT_CATALOG (paths, images, endpoints, prompts) -- data only
      ds_agent_lab.py      # the engine the notebook imports as `lab` (docker/agent/generate/run/results + ensure_ipywidgets)
      serve_vlm.sh         # local VLM service launcher used only by VLM scenarios
    tests/                 # notebook/runtime/deployment regression contracts
  example_prompts/         # the 14 prompt .md (1:1 with PROMPT_CATALOG) + rtvi_vlm_openapi_spec.png attachment
  skills/                  # deepstream-dev + deepstream-import-vision-model + deepstream-profile-pipeline (the Install step copies these into the agent)
```

`example_prompts/` and `skills/` sit at the **repo root, as siblings of `deploy/`** -- both are
required. At import the catalog is loaded from `example_prompts/*.md`; the environment/workspace step (`%%bash`) stages
`example_prompts/` into the mounted `/workspace`; and the Install step (`install_agent`) `docker cp`s the
named skills into the agent. `REPO_ROOT` is derived from the module's own location
(`deploy/brev/scripts/ds_agent_lab.py`, three levels up), never hard-coded.

## Brev deployment

Configure the Brev launchable repository as `https://github.com/NVIDIA/DeepStream.git`, then use
`scripts/brev_post_setup.sh` as the post-setup script. Brev runs this script before its repository
clone, so the script installs a one-time Git `post-checkout` hook under the current user's HOME.
When Brev finishes cloning DeepStream, Git runs the hook, which clones `ds_launchable` and overlays
it under `$HOME/deepstream/deploy/brev`. The hook removes itself and its HOME template after the
overlay succeeds. The script deliberately starts with `#!/bin/bash`, uses the Brev-managed `uv`
and Python environment, and does not replace that environment. It completes after the host and
hook readiness gates pass:

- Docker and the NVIDIA Container Toolkit are installed/configured and the daemon is reachable.
- The Brev Python environment contains `pip`, `ipywidgets`, and the Jupyter widget extension; a
  kernel-level widget MIME smoke test succeeds.
- The HOME Git clone template is armed; the DeepStream clone hook validates the notebook after checkout.
- `nvcr.io/nvidia/deepstream:9.0-triton-multiarch` is fully pulled, has a repository digest, and
  passes an NVIDIA GPU container smoke test.
- `poppler-utils` is installed so PDF reports can be rendered as notebook images.
- Jupyter's HTTP API is responding.

The script is intentionally fail-fast: a successful Brev post-setup means the host and clone hook
are ready, not merely that installation commands were started. The subsequent Brev DeepStream clone
fails if the hook cannot install the notebook. The script accepts optional environment overrides
including `WORK_ROOT`, `DEEPSTREAM_REPO_URL`, `LAUNCHABLE_REPO_URL`, `DEEPSTREAM_IMAGE`,
`SKIP_HOST_SETUP`, `SKIP_IMAGE_PULL`, and `SKIP_JUPYTER_SETUP`.

The deployment assumes the DeepStream checkout is Jupyter's `ServerApp.root_dir`. Open
`deploy/brev/deepstream_code_agent_launchable.ipynb` and run the cells top to bottom. All paths in
this document are relative to that DeepStream root unless stated otherwise.

Authenticate at the Authenticate step -- account sign-in, an API key, or a custom endpoint
(held in memory, injected per agent call -- never written to disk). Advanced users can instead
set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, or `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
environment variables and skip the Authenticate step.

**Where outputs go.** Generated code + run results land in **`deploy/brev/outputs/`** (the default
`OUTPUT_ROOT`, right next to the notebook and below the supported Jupyter roots), so they show up in the
**left-hand file browser** and survive a page refresh:
- `deploy/brev/outputs/workspace/<app_dir>/` -- the generated code
- `deploy/brev/outputs/workspace/agent_outputs/<prompt_id>/` -- the run artifacts (mp4 / openapi.json / ...)

To put outputs elsewhere, set `OUTPUT_ROOT` -- but keep it **under your Jupyter `root_dir`** if you
want them in the file browser:
```bash
OUTPUT_ROOT="$PWD/ds_outputs" jupyter lab --ServerApp.root_dir="$PWD" ...
```

Artifact links are derived from the running Jupyter server's actual DeepStream `root_dir`. Report
results prefer the generated PDF and render its pages as images. Markdown is used only as a fallback
when a PDF is absent or cannot be rasterized.

If you refresh the page (F5), live step outputs clear (your kernel + files are safe). Turn on
**Settings -> Save Widget State Automatically**, or re-show a result with `lab.show_generated_code()`
(Generate step) / `lab.show_results()` (Run step).

## Update your own notebook

The `.ipynb` is **generated** -- edit the sources, not the notebook:

- **Steps / markdown / cell code** -> edit `scripts/build_notebook.py`, then regenerate:
  ```bash
  python3 deploy/brev/scripts/build_notebook.py
  ```
- **Engine logic** -> edit `scripts/ds_agent_lab.py` (or `ds_lab_config.py` for config/prompts).
  The step widgets are built inline in `build_notebook.py`, not in a separate module.
- **Add a prompt** -> drop a `.md` in `example_prompts/` and add a matching entry to
  `PROMPT_CATALOG` in `scripts/ds_lab_config.py`.

Pick up changes in a running notebook:

- After editing a **`.py`** -> re-run the **Install step** (the first cell that loads `lab`; it
  reloads the lab modules fresh -- no kernel restart needed). The Generate/Run steps reuse the
  loaded module, so your agent / creds / selection survive.
- After regenerating the **`.ipynb`** -> reload it in the browser (**File -> Reload Notebook from Disk**).

## Regression tests

Run the Brev regression suite from the repository root:

```bash
JUPYTER_PLATFORM_DIRS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s deploy/brev/tests -v
```

The suite uses temporary directories rather than machine-specific paths. Its contracts cover:

- prompt selection/edit invalidation and agent-only selection preservation;
- Generate/Run prerequisite enforcement, cross-control locking, failure recovery, and success state;
- autonomous Generate behavior plus prompt-specific report requirements;
- exact PDF/report ownership and profiling-report semantic validation;
- PDF-first rendering with Markdown fallback;
- Jupyter-root-relative artifact paths and URL escaping;
- prompt catalog behavior for complete and partial checkouts;
- generated-notebook parity with `build_notebook.py`;
- the Brev post-setup, removed legacy bootstrap, and required VLM launcher.

`serve_vlm.sh` is not a general startup service. `ds_agent_lab.py` invokes it only for scenarios
whose prompt metadata requires a local VLM endpoint, so it must remain beside the other Brev
scripts even when most test cases do not use it.

## Configurable env vars (all optional; sensible defaults)

`OUTPUT_ROOT`, `DEEPSTREAM_IMAGE`, `AGENT_CONTAINER`, `SAMPLE_VIDEO`, `KAFKA_BOOTSTRAP`,
`KAFKA_TOPIC`, `RTSP_BASE`, `VLM_ENDPOINT`, `VLM_MODEL`, `RTVI_SERVICE_PORT`, `DEMO_MAX_SECONDS`,
`RUN_DEMO_TIMEOUT`, `IMPORT_VISION_TIMEOUT`. Credentials come from the Authenticate step (account
sign-in, API key, or custom endpoint), or optionally from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`
/ `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` env vars.
