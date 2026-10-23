# 模型来源与运行时

精确标识、commit revision、模型卡许可字段、下载体积元数据及完整性布局见仓库根目录 `models.json`。不要把别人的缓存路径当作配置。

| 用途 | 公开模型／后端 | 获取方式 |
|---|---|---|
| 源语音 ASR、最终中文独立回读 | [mlx-community/whisper-large-v3-turbo](https://huggingface.co/mlx-community/whisper-large-v3-turbo) | Hugging Face，mlx-whisper |
| 参考音色克隆，与原有 Base 系列对应 | [mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit) | Hugging Face，mlx-audio；自备授权参考音频 |
| 无私人 ref 的默认 TTS | [mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit) | Hugging Face，mlx-audio；预置声线 |
| 翻译和文本语义复核 | 使用者选定的 Ollama 或兼容文本模型 | 不与语音权重混为一谈；按真实设备和授权获取 |

ASR 模型转换卡没有显式 license 字段，因此清单标 unspecified 并指向上游 [OpenAI Whisper](https://github.com/openai/whisper) 许可核对；不能替未声明的转换仓库擅自填 MIT。两款 Qwen 转换模型的模型卡声明 Apache-2.0；这不代替对运行时、音色和输入视频许可的审查。

本首版使用 MLX Whisper 做最终中文独立识别，未包含第二路 whisper.cpp 交叉检查；不能把单路严格词匹配描述为已经包含多模型交叉门禁。

Ollama 官方入口：[文档](https://docs.ollama.com/)、[模型库](https://ollama.com/library)。库中的当前型号、大小和硬件适配由接收者的 Agent 实查。项目没有携带文本模型权重或自动默认拉取一个型号，避免擅自消耗资源。真实样片所用的文本型号记录在验证说明，不作为对所有电脑的推荐。
