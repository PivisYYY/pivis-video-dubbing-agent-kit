# 快速上手：先做短样片，再由你听审

[返回中文首页](../README.md) · [English entry](../README.en.md) · [支持范围](SUPPORT.md) · [真实验证记录](../VALIDATION.md)

> **这是预览版试用路线，不是一键交付保证。** 当前仅 Apple Silicon Mac、单说话人英文 → 中文；需要 Python 3.11、uv、FFmpeg（libx264；烧字幕还需 libass）。公开 CLI 记录的是 11.007 秒单句样片机器通过，尚无使用者听审批准；全片、多人、第二台 Mac、跨平台未验收。先用你有权处理、不含敏感信息的完整短素材。

## 1. 获取仓库，只检查环境

```bash
git clone https://github.com/PivisYYY/pivis-video-dubbing-agent-kit.git
cd pivis-video-dubbing-agent-kit
python3 -m dubkit doctor
```

`doctor` 不安装依赖、不下载模型。若提示不支持的平台，先停下，不强装 MLX 或臆测其他后端已兼容。缺少 Python 3.11、uv 或所需 FFmpeg 构建时，按工具官方文档准备；系统安装须另获你的授权。

若由 Agent 操作：明确要求先读 [AGENTS.md](../AGENTS.md)、[README.md](../README.md)、`models.json` 与 [SUPPORT.md](SUPPORT.md)，不要假设它自动发现入口。不需要安装另一个 Agent，也不应改其账号、默认模型或全局配置。

## 2. 阅读脚本后，分别授权安装与模型下载

先检查仓库内 `bootstrap.sh` 和 `models.json`，了解依赖、模型来源、许可与磁盘需求。语音权重约数 GB，另需文本模型、依赖和视频工作空间；这不是总磁盘估算。

```bash
# 仅在同意安装后执行；依赖安装到项目 .venv。
bash bootstrap.sh --accept-install
source .venv/bin/activate
python -m dubkit doctor
python -m dubkit models list

# 另行同意下载后执行；默认 ASR + CustomVoice。
python -m dubkit models fetch --accept-download
```

没有 `--accept-download` 时只查匹配缓存，不联网补模型。新终端需在仓库根目录重新激活 `.venv`。许可并非全部由源码 MIT 覆盖，先读 [模型来源](MODELS.md) 与 [第三方声明](../THIRD_PARTY_NOTICES.md)。

## 3. 准备独立的本地文本模型

本地 Ollama 是可选的**文本后端**，不是 MLX ASR/TTS 的安装器。先检查本机真实硬件、已装模型与官方模型库，确认模型支持忠实翻译和 JSON／JSON Schema 输出；下载文本模型也要单独授权。模型小、能输出文字，不等于译文合格。

下面假定你已启动本地 Ollama，并有可用模型。把 `your-text-model` 换成**本机真实模型名**；不要原样运行占位符。其他兼容后端见 [完整说明](../README.md)。默认只允许本机请求；远程 HTTPS 文本 API 需另行授权、显式 `--allow-remote-llm`，转录会外发且可能收费。本地路线不需要提供 API Key。

## 4. 跑一个完整台词的短样片

在仓库根目录放置你有权处理的 `input.mp4`，或将命令改成自己的本地文件路径；输入与所有 job 数据都不要提交到 Git 或 Issue。默认用模型预置 `Vivian` 声线，不需要参考音频。

```bash
python -m dubkit run \
  --input input.mp4 --job work/sample \
  --llm-url http://localhost:11434/v1 --llm-model your-text-model \
  --sample-seconds 20 --voice Vivian --burn-subtitles

python -m dubkit status --job work/sample
python -m dubkit verify --job work/sample
```

`--sample-seconds 20` 裁切源片，不能保证句尾完整；若切断台词，先换完整短素材或调整范围。不是所有预置声线都稳定；机器拒绝时不放宽门禁、不无限重试。烧字幕要求 FFmpeg 含 libass；不烧录时仍有中英两条可选字幕轨。对齐基于最终中文音频 ASR 词边界，不是逐音素强制对齐。

## 5. 机器通过之后，自己连续听、看

- 看 `status` 与 `verify` 的真实结果；报错不算完成。
- 连续试听中文是否忠实、自然、无漏译或异常语速，同时检查画面与双语字幕。
- `MACHINE_COMPLETE` **不等于你已验收**。只有你明确确认听审与画面通过后，Agent 才能记录 `approve`。
- 全片命令与批准合同要求见 [README](../README.md)。全片路线尚未端到端验收；不要因为一个样片机器通过就直接宣布全片可交付。

## 遇到问题或愿意反馈

先查 [故障与续跑说明](SUPPORT.md) 及 [README](../README.md)：环境故障修好后重跑原命令复用已通过阶段；译文有误用 `revise`，不要手改 checkpoint 或放宽质量门禁。更换输入、模型、音色或生成合同时建新 job。

- [试用反馈表单](https://github.com/PivisYYY/pivis-video-dubbing-agent-kit/issues/new?template=trial-feedback.yml)：报告尝试到哪一步、机器状态和是否真的听审。
- [故障反馈表单](https://github.com/PivisYYY/pivis-video-dubbing-agent-kit/issues/new?template=bug-report.yml)：报告最小复现步骤、人工检查后的最小报错和环境概况。

**Issue 是公开的。** 不上传私人视频、参考音频、完整日志／job、转录字幕、凭证、签名 URL、个人路径或设备标识。不要粘贴 `doctor` 或其他工具的完整原始输出；只人工摘录非敏感的系统版本、芯片系列、工具版本、后端类型与失败阶段。不确定是否安全时省略，见 [隐私边界](PRIVACY.md)。
