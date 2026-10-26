# Pivis Video Dubbing Agent Kit

A local **English-to-Chinese video dubbing pipeline** for agents such as Hermes or Codex to operate through existing code and [AGENTS.md](AGENTS.md), rather than inventing a pipeline from scratch. These agents are optional operators, not bundled runtimes or official integrations.

[中文 / Full documentation](README.md) · [Quick start (Chinese)](docs/QUICKSTART.md) · [Validation record (Chinese)](VALIDATION.md)

> [!WARNING]
> **Preview seeking early testers, not a mature one-click product.** The current speech backend requires **Apple Silicon macOS, Python 3.11, uv, and FFmpeg** (libx264; libass for burned-in subtitles). The supported content route is a **single English speaker → Chinese speech with bilingual subtitles**.
>
> The public CLI has recorded machine checks on **one 11.007-second, single-sentence sample**, with **no user listening approval yet**. Full-length videos, multiple speakers, a second Mac, and cross-platform operation have not been validated. A fresh project virtual environment is not a second-machine test. The recorded 48 passing unit tests are not evidence of general dubbing quality.

## See the historical examples first

[Five original-vs-dubbed comparisons in the Chinese README](README.md#原片与中文译配对照) · [Sources and clip notes](examples/README.md) · [Media rights](examples/LICENSE.md)

These clips were produced with a **historical pipeline, not the new public CLI**. They are not evidence of its full-video quality. GIFs are silent; open or download the linked MP4 to hear the dubbing. The media and voices are **not MIT-licensed**; publication does not clear third-party source, voice, or redistribution rights.

## Give your agent this instruction

> Read AGENTS.md, README.md, models.json, and docs/SUPPORT.md. Check my hardware and environment. Ask before installing dependencies, downloading models, or using any remote service. Use a compatible local text model and an authorized input to make a short Chinese-dubbed sample first. Verify the output, then ask me to listen and inspect it. Only record approval after my explicit confirmation, and only then attempt the full video. Diagnose failures and resume without weakening quality gates. Do not upload my files or change my agent's accounts or global settings.

Not every agent discovers AGENTS.md automatically: **explicitly ask it to read the file**, and grant only the permissions needed.

## Start with an environment check

```bash
git clone https://github.com/PivisYYY/pivis-video-dubbing-agent-kit.git
cd pivis-video-dubbing-agent-kit
python3 -m dubkit doctor
```

This check does not install dependencies, fetch models, or generate a video. Continue with the [step-by-step quick start](docs/QUICKSTART.md) or the [full commands in Chinese](README.md). Read installation scripts before approving them. Installation uses a project `.venv`; system tools require separate approval. Speech weights are several GB, plus a text model, dependencies, and workspace.

## What the pipeline does — and does not promise

- English ASR and word timestamps → translation and semantic review → Chinese TTS → independent Chinese ASR checks → bilingual subtitles, mixing, rendering, and verification.
- Local MLX speech models; a separate local text backend such as Ollama. Ollama does not install the MLX speech stack. Use a real model name that supports faithful translation and structured output.
- Preset voices by default. Optional Base voice cloning requires authorized reference audio and an accurate transcript; a synthetic-reference probe is **not** full-video cloning validation. No arbitrary-person voice-cloning guarantee.
- Resume and explicit translation revision are available. `MACHINE_COMPLETE` means machine checks passed, **not human acceptance**. Subtitle alignment uses ASR word boundaries, not guaranteed phoneme-level alignment.
- No automatic multi-speaker identification or role assignment; no supported Windows, Linux, CUDA, or CPU speech backend. No promise that every preset voice or source URL works.

Requests are local-only by default. A remote HTTPS text API requires explicit `--allow-remote-llm`; transcripts will be sent to that service and charges may apply. Credentials are supplied only through the user's own `DUBKIT_API_KEY` environment variable, never in issues, source, or command arguments. Do not share `.env`, job data, transcripts, or full logs. See [privacy](docs/PRIVACY.md), [support](docs/SUPPORT.md), and [model provenance](docs/MODELS.md) (Chinese).

## Share safe feedback

- [Trial feedback / 试用反馈](https://github.com/PivisYYY/pivis-video-dubbing-agent-kit/issues/new?template=trial-feedback.yml)
- [Bug report / 故障反馈](https://github.com/PivisYYY/pivis-video-dubbing-agent-kit/issues/new?template=bug-report.yml)

Issues are public. Submit only a **manually reviewed minimal error excerpt and general environment summary**. Do not attach private video, reference audio, full logs or job folders, credentials, signed URLs, personal paths, or device identifiers. Omit anything you cannot safely sanitize. English feedback is welcome.

## License and acknowledgements

Project-owned source and documentation are [MIT](LICENSE), provided as-is. **MIT does not cover all dependencies, models, voices, or media.** In particular, the pinned Whisper conversion's model card does not explicitly declare a license, and an FFmpeg build with libx264 cannot be described as purely LGPL. Check [third-party notices](THIRD_PARTY_NOTICES.md), [acknowledgements](ACKNOWLEDGEMENTS.md), and the [separate media boundary](examples/LICENSE.md) before reuse or redistribution.
