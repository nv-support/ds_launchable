# Generate and Validate a DeepStream Project with Code Agent

DeepStream Code Agent is a guided Jupyter lab for turning a natural-language scenario into a
runnable DeepStream project or workflow. You choose a coding agent, install DeepStream skills,
generate the requested artifacts, run them in a prepared GPU runtime, and inspect the evidence
that the result worked.

Many prompts generate `pyservicemaker` applications, but the prompt catalog is broader than that:
some scenarios produce native message-broker adapters, automatic performance analysis reports,
model-conversion assets, service wrappers, or API specifications.

Use this README as the entry point. The notebook contains the interactive lab; this page helps you
prepare the machine, choose a good first scenario, follow the numbered steps, and know where the
generated code and results are stored.

## What you will build

By the end of the workflow, you will have:

- a DeepStream workspace running inside a GPU-enabled container;
- Claude Code or Codex installed with DeepStream development skills;
- a generated DeepStream project with source, configuration, launch scripts, and notes;
- runtime artifacts such as an annotated MP4, service output, JSON messages, or a PDF report;
- a repeatable place to inspect, copy, or reuse the generated project.

## Before you start

You need a host that can run DeepStream containers and a model-backed coding agent:

- an NVIDIA GPU host;
- Docker and the NVIDIA Container Toolkit;
- access to the configured DeepStream container image;
- Jupyter Lab with this DeepStream repository as the working directory;
- credentials for either Claude Code or Codex;
- network access for image pulls, package installs, model downloads, and agent calls.

For a first run, use the `video_infer_app` prompt. It is short, file-based, and produces an
annotated MP4, so it is the quickest way to confirm the full Generate -> Run -> Results loop.

## Quick start on Brev

Use the Brev path when you open the packaged launchable environment:

1. Start the DeepStream Code Agent launchable from Brev.
2. Open `deploy/brev/deepstream_code_agent_launchable.ipynb`.
3. Run the numbered cells from top to bottom.
4. In the Generate step, start with `video_infer_app` unless you need a specific scenario.

The launchable prepares the repository checkout, machine setup, and notebook runtime for you.

## Walkthrough

Run each notebook step in order and wait for its success message before continuing.

| Step | What you do | Checkpoint |
| --- | --- | --- |
| 1. Configuration | Review paths, image names, container names, and runtime defaults. | The cell prints `Configuration set` and the active values. |
| 2. Check environment and create workspace | Validate the GPU host and start the DeepStream container workspace. | The output reports `Environment ready`, the container name, and the mounted workspace. |
| 3. Install agent and skills | Choose Claude Code or Codex, then install the CLI, DeepStream skills, and runtime dependencies. | The install step finishes without errors and the selected agent is available. |
| 4. Authenticate | Provide account sign-in, API key, or custom endpoint credentials for the selected agent. | Authentication verification succeeds before you continue. |
| 5. Generate | Choose a prompt, edit it if needed, and ask the agent to write the project artifacts. | The generated file preview appears and matches the selected scenario. |
| 6. Run and view results | Run the generated project in the prepared runtime and view its artifacts. | The result viewer shows the expected MP4, JSON, service output, or report. |
| 7. Cleanup | Optionally remove temporary lab containers. | Containers are removed while generated files and artifacts remain. |

Generate and Run are intentionally separate. Generate authors the project and previews the files;
Run validates the project in the current runtime, applies bounded runtime fixes when needed, and
renders the final evidence. Changing the selected prompt or editing its text invalidates the
previous generation result, so Run cannot accidentally use artifacts from another scenario.

Runtime fixes are made on a separate run copy. The original generated source remains available for
review, while the run copy can be adjusted to satisfy the current container, services, model files,
or headless output requirements.

## Choosing a scenario

Start with a scenario that matches the time and evidence you need:

Not every example prompt produces a `pyservicemaker` application. Choose the prompt based on the
artifact you want to demonstrate: an app, a native adapter, an analysis report, a model package, or
a service/API workflow.

| Scenario | Use it when you want | Typical result |
| --- | --- | --- |
| `video_infer_app` | The fastest end-to-end smoke test. | A compact DeepStream app and annotated MP4. |
| `video_object_count` | A simple counting example on video input. | Object counts rendered with the stream. |
| `ds_profiling_efficient_pipeline` | Automatically profile a multi-stream pipeline and explain its bottleneck. | A profiling report with bottleneck analysis, sustainable stream-count estimate, and hardware guidance. |
| `msgconv_kafka` | Convert detection metadata to JSON and publish it directly to Kafka. | A runnable Kafka publisher and captured Kafka JSON messages. |
| `msgbroker_nats` | Build a DeepStream `nvds_msgapi` message broker protocol adapter for NATS. | A native adapter shared library, JetStream/auth/TLS configuration, and local subscriber verification. |
| `multi_stream_tracker` | Multiple live streams with tracking. | A tiled MP4 with persistent track IDs. |
| `import_vision_model_detection_pipeline` | Full model onboarding and benchmarking. | Converted model files, configs, benchmark evidence, and a PDF report. |
| `rtvi_vlm_core_app` | A VLM/video reasoning workflow. | VLM summaries, service output, and supporting artifacts. |

More advanced scenarios may take longer because they pull models, build TensorRT engines, start
services, or require agent-assisted run repair. Cold runs are slower than warm runs with cached
images, packages, models, and engines.

## Where results are stored

By default, generated code and run artifacts are stored under:

```text
deploy/brev/outputs/workspace/
```

Generated projects are grouped by scenario. Agent transcripts and run artifacts are written
under scenario-specific output directories, including files such as MP4 videos, JSON messages,
service logs, OpenAPI specs, and PDF reports. Because the output directory is inside the Jupyter
root, the results can be opened from the left-hand Jupyter file browser.

If the browser page is refreshed, live widget output may disappear even though the kernel and files
remain. To preserve widget output, enable `Settings -> Save Widget State Automatically`. To show
results again without re-running the agent, use `lab.show_generated_code()` after Generate or
`lab.show_results()` after Run.

## Troubleshooting

- If the environment check fails, verify Docker, the NVIDIA Container Toolkit, GPU visibility, and
  access to the configured DeepStream image.
- If authentication fails, rerun the Authenticate step and verify that the selected agent matches
  the credential method you provided.
- If Generate succeeds but Run fails, inspect the run output first. Run uses the selected scenario's
  runtime contract and may need service startup, model files, or a bounded repair iteration.
- If output files are missing, confirm that the selected scenario completed Run and that you are
  looking under `deploy/brev/outputs/workspace/` from the Jupyter file browser.
- If a first run is slow, check whether it is pulling images, downloading models, installing
  packages, or building TensorRT engines. Later runs are usually faster once those assets are
  cached.

## For maintainers

The notebook is generated. Edit the sources, then regenerate the notebook instead of hand-editing
notebook logic.

```text
<deepstream root>/
├── deploy/brev/
│   ├── deepstream_code_agent_launchable.ipynb  # user-facing generated notebook
│   ├── README.md                               # this README
│   ├── scripts/
│   │   ├── build_notebook.py                    # notebook source of truth
│   │   ├── ds_agent_lab.py                      # notebook runtime engine
│   │   ├── ds_lab_config.py                     # prompt catalog and configuration
│   │   ├── brev_post_setup.sh                   # machine setup
│   │   └── serve_vlm.sh                         # VLM scenario launcher
│   └── tests/                                   # regression tests
├── example_prompts/                             # scenario descriptions
└── skills/                                      # DeepStream agent skills
```

Prompt definitions live under `example_prompts/`. The prompt catalog and scenario metadata are
maintained in `deploy/brev/scripts/ds_lab_config.py`. The notebook is generated from
`deploy/brev/scripts/build_notebook.py`, and the runtime implementation lives in
`deploy/brev/scripts/ds_agent_lab.py`.
