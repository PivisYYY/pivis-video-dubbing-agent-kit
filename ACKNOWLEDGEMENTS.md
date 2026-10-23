# 致谢 / Acknowledgements

本项目建立在众多开源维护者、研究者与社区贡献者的工作之上。感谢他们提供可供学习、组合和独立运行的基础组件。这里区分真实运行依赖、模型来源和相关工作，不将别人的成果描述成本项目原创，也不暗示任何官方关联或背书。

## 实际使用的核心组件

| 项目 | 在本项目中的作用 | 来源与许可边界 |
|---|---|---|
| MLX / MLX Metal | Apple Silicon 上的本地模型计算 | [ml-explore/mlx](https://github.com/ml-explore/mlx)；MIT，随包原生部分另看上游声明 |
| MLX Whisper | 英文识别与最终中文独立回读，取得词级时间戳 | [mlx-examples/whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)；MIT |
| OpenAI Whisper | ASR 模型与 MLX 实现的上游基础 | [openai/whisper](https://github.com/openai/whisper)；上游实现 MIT，不代替转换模型许可 |
| MLX-Audio | Qwen3-TTS 模型加载和语音生成 | [Blaizzy/mlx-audio](https://github.com/Blaizzy/mlx-audio)；MIT |
| Qwen3-TTS / Qwen 团队 | 公开预置声线与可选授权参考音色合成 | [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)；Apache-2.0，声音与素材权利另核 |
| mlx-community | 提供实际固定版本的 MLX 格式转换模型 | [Hugging Face 社区](https://huggingface.co/mlx-community)；各模型按自己的模型卡，不统一推定许可 |
| Hugging Face Hub | 固定版本模型获取和本地缓存管理 | [huggingface_hub](https://github.com/huggingface/huggingface_hub)；Apache-2.0 |
| NumPy / python-soundfile | 波形运算、音频读取与 PCM 输出 | [NumPy](https://github.com/numpy/numpy)、[python-soundfile](https://github.com/bastibe/python-soundfile)；注意 libsndfile 的独立 LGPL 许可 |
| FFmpeg / ffprobe、libx264、libass | 音轨提取、混音、编码、字幕烧录与媒体检查 | [FFmpeg](https://ffmpeg.org/)、[x264](https://www.videolan.org/developers/x264.html)、[libass](https://github.com/libass/libass)；许可随实际构建变化 |
| yt-dlp | 可选的公开视频 URL 输入 | [yt-dlp](https://github.com/yt-dlp/yt-dlp)；核心 Unlicense，下载与素材使用仍需合法授权 |
| Ollama | 可选的本地翻译和文本审校服务，不负责本项目 ASR/TTS | [ollama/ollama](https://github.com/ollama/ollama)；软件 MIT，加载的模型另行许可 |
| Qwen3 文本模型 | 真实短样片中通过 Ollama 使用 `qwen3:8b` 做翻译和审校 | [Qwen3-8B 模型卡](https://huggingface.co/Qwen/Qwen3-8B)；模型卡声明 Apache-2.0，不与服务软件或同名标签混淆 |
| uv / Python | 独立 Python 3.11 环境与安装工具 | [uv](https://github.com/astral-sh/uv)、[Python](https://www.python.org/)；解释器、工具和第三方原生组件有各自声明 |

完整的直接、间接和构建依赖共 52 项，逐项固定版本、上游链接、许可摘要与原文保留位置见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [third_party/inventory.json](third_party/inventory.json)。感谢包括 PyTorch、Transformers、Tokenizers、SciPy 等在内的全部间接依赖维护者；不因它们不直接出现在 CLI 入口就省略声明。

## 相关工作：OpenCreator（原 KrillinAI）

特别感谢 [OpenCreator（原 KrillinAI）](https://github.com/krillinai/OpenCreator) 在开源视频翻译、字幕、译配与 Agent 创作工作流上的工作。它是本项目相关工作和工作流参考的一部分。

本预览版采用独立的 Python CLI，不捆绑或调用 OpenCreator 应用，也不宣称本项目是它的官方版本、分支或替代品。OpenCreator 自身的 Apache-2.0 许可与贡献者权利不因本项目使用 MIT 而改变。

## 可选的 Agent 操作端

感谢 [Hermes Agent](https://github.com/NousResearch/hermes-agent)、[Codex](https://github.com/openai/codex) 及其他支持文件、终端和审批的 Agent。它们可阅读 AGENTS.md 并协助操作现有代码，但不是本项目内嵌的运行时。本项目不要求特定 Agent，不更改其账号、全局模型、提示词或配置。

## 许可与素材不是一句感谢就能替代

- 本项目 MIT 只覆盖自有源码与文档，不统一授权所有依赖、模型、声音、视频和字幕。
- 所选 Whisper 转换模型的固定模型卡未显式声明许可，清单保留 `unspecified` 警示；OpenAI Whisper 的 MIT 不能自动填补该转换仓库的许可空缺。
- 仓库不分发任何模型权重、音色参考、原片、成片、日志、二进制依赖或运行缓存。
- 声音克隆和素材再分发必须分别取得授权；公开视频可访问不等于声音可克隆、作品可再发布。
- 第三方名称、商标和著作权归各自权利人所有。致谢不是背书、商业合作或许可保证。
