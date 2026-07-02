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

## Files

```
<repo root>/                                 # = the Jupyter server's root_dir
  deploy/brev/
    deepstream_code_agent_launchable.ipynb   # the notebook (GENERATED -- do not hand-edit for logic)
    README.md
    scripts/
      build_notebook.py    # SOURCE OF TRUTH for the .ipynb (run it to regenerate)
      ds_lab_config.py     # config + PROMPT_CATALOG (paths, images, endpoints, prompts) -- data only
      ds_agent_lab.py      # the engine the notebook imports as `lab` (docker/agent/generate/run/results + ensure_ipywidgets)
  example_prompts/         # the 14 prompt .md (1:1 with PROMPT_CATALOG) + rtvi_vlm_openapi_spec.png attachment
  skills/                  # deepstream-dev + deepstream-import-vision-model + deepstream-profile-pipeline (the Install step copies these into the agent)
```

`example_prompts/` and `skills/` sit at the **repo root, as siblings of `deploy/`** -- both are
required. At import the catalog is loaded from `example_prompts/*.md`; the environment/workspace step (`%%bash`) stages
`example_prompts/` into the mounted `/workspace`; and the Install step (`install_agent`) `docker cp`s the
named skills into the agent. `REPO_ROOT` is derived from the module's own location
(`deploy/brev/scripts/ds_agent_lab.py`, three levels up), never hard-coded.

## Deploy / run

Prereqs: a GPU host with **Docker + the NVIDIA Container Toolkit**, and access to the DeepStream
image `nvcr.io/nvidia/deepstream:9.0-triton-multiarch`.

1. Get the files: the **repo root that contains `deploy/`, `example_prompts/`, and `skills/`**
   (clone the repo, or copy those three together).
2. Launch JupyterLab with **`root_dir` = that repo root**:
   ```bash
   jupyter lab --no-browser --ip=0.0.0.0 --port=8899 \
     --ServerApp.token=<your-token> \
     --ServerApp.root_dir=/path/to/REPO        # the dir containing deploy/ example_prompts/ skills/
   ```
3. Open `deploy/brev/deepstream_code_agent_launchable.ipynb` and run the cells top to bottom.
   Authenticate at the Authenticate step -- account sign-in, an API key, or a custom endpoint
   (held in memory, injected per agent call -- never written to disk). Advanced users can instead
   set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, or `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`
   env vars and skip the Authenticate step.

**Where outputs go.** Generated code + run results land in **`deploy/brev/outputs/`** (the default
`OUTPUT_ROOT`, right next to the notebook and still under `root_dir`), so they show up in the
**left-hand file browser** and survive a page refresh:
- `deploy/brev/outputs/workspace/<app_dir>/` -- the generated code
- `deploy/brev/outputs/workspace/agent_outputs/<prompt_id>/` -- the run artifacts (mp4 / openapi.json / ...)

To put outputs elsewhere, set `OUTPUT_ROOT` -- but keep it **under your Jupyter `root_dir`** if you
want them in the file browser:
```bash
OUTPUT_ROOT=<root_dir>/ds_outputs jupyter lab --ServerApp.root_dir=<root_dir> ...
```

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

## Configurable env vars (all optional; sensible defaults)

`OUTPUT_ROOT`, `DEEPSTREAM_IMAGE`, `AGENT_CONTAINER`, `SAMPLE_VIDEO`, `KAFKA_BOOTSTRAP`,
`KAFKA_TOPIC`, `RTSP_BASE`, `VLM_ENDPOINT`, `VLM_MODEL`, `RTVI_SERVICE_PORT`, `DEMO_MAX_SECONDS`,
`RUN_DEMO_TIMEOUT`, `IMPORT_VISION_TIMEOUT`. Credentials come from the Authenticate step (account
sign-in, API key, or custom endpoint), or optionally from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`
/ `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` env vars.
