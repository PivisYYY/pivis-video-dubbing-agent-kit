# Pivis Video Dubbing Agent Kit

[源码许可：MIT](LICENSE) · [致谢](ACKNOWLEDGEMENTS.md) · [第三方许可声明](THIRD_PARTY_NOTICES.md) · [验证边界](VALIDATION.md)

把这个项目交给 Hermes、Codex 或其他具备文件、终端和网络工具的 AI Agent，让它根据 **AGENTS.md** 操作现成代码，准备模型、跑样片并验收视频，而不是从零猜一套管线。

> 当前为 Apple Silicon Mac 单说话人路线的可运行预览版。语音使用 MLX，文本翻译可用 Ollama 或授权的兼容接口。真实验收边界见 VALIDATION.md。不承诺全平台、一键零审批、自动多说话人或所有视频自动达到交付质量。

## 原片与中文译配对照

先看真实效果：下列 **5 组**来自此前完成的历史管线，左侧打开官方原片，右侧动图预览画面并链接到中文 MP4。原片链接从对应时间附近开始；不重新上传整部原片。

**这些是历史作品展示，不是由本仓库新版 CLI 批量生成的验收案例。** 历史字幕样式可能为单语或独立时间轨；新版 CLI 的真实运行范围仍以 [VALIDATION.md](VALIDATION.md) 为准。

| 内容 | 原片 · 官方发布 | 中文译配 · 历史真实片段 |
|---|---|---|
| **ChatPRD · 新时代的产品经理**<br>历史中英字幕 | [<img src="https://i.ytimg.com/vi/4CAFK-rc26A/hqdefault.jpg" width="360" alt="官方原片封面">](https://www.youtube.com/watch?v=4CAFK-rc26A&t=75s)<br>[观看原片 · Cursor](https://www.youtube.com/watch?v=4CAFK-rc26A&t=75s) | [<img src="examples/assets/pm-workflow/preview.gif" width="360" alt="真实中文译配片段动图">](examples/assets/pm-workflow/dubbed.mp4?raw=true)<br>[查看／下载中文 MP4 · 约 38 秒](examples/assets/pm-workflow/dubbed.mp4?raw=true) |
| **Anthropic · AI 时代的内容设计**<br>历史中文字幕 | [<img src="https://i.ytimg.com/vi/l5VRhrNeidY/hqdefault.jpg" width="360" alt="官方原片封面">](https://www.youtube.com/watch?v=l5VRhrNeidY&t=13s)<br>[观看原片 · Figma](https://www.youtube.com/watch?v=l5VRhrNeidY&t=13s) | [<img src="examples/assets/content-design/preview.gif" width="360" alt="真实中文译配片段动图">](examples/assets/content-design/dubbed.mp4?raw=true)<br>[查看／下载中文 MP4 · 约 55 秒](examples/assets/content-design/dubbed.mp4?raw=true) |
| **Notion · 设计系统**<br>历史中英字幕 | [<img src="https://i.ytimg.com/vi/u7_Qof3AJ1g/hqdefault.jpg" width="360" alt="官方原片封面">](https://www.youtube.com/watch?v=u7_Qof3AJ1g&t=30s)<br>[观看原片 · Figma](https://www.youtube.com/watch?v=u7_Qof3AJ1g&t=30s) | [<img src="examples/assets/design-system/preview.gif" width="360" alt="真实中文译配片段动图">](examples/assets/design-system/dubbed.mp4?raw=true)<br>[查看／下载中文 MP4 · 约 45 秒](examples/assets/design-system/dubbed.mp4?raw=true) |
| **Cursor · Closer to the Material**<br>历史中英字幕 | [<img src="https://i.ytimg.com/vi/az6OEZV8iHw/hqdefault.jpg" width="360" alt="官方原片封面">](https://www.youtube.com/watch?v=az6OEZV8iHw&t=15s)<br>[观看原片 · Cursor](https://www.youtube.com/watch?v=az6OEZV8iHw&t=15s) | [<img src="examples/assets/software-craft/preview.gif" width="360" alt="真实中文译配片段动图">](examples/assets/software-craft/dubbed.mp4?raw=true)<br>[查看／下载中文 MP4 · 约 45 秒](examples/assets/software-craft/dubbed.mp4?raw=true) |
| **OpenAI · 开发者主题演讲**<br>历史中英字幕 | [<img src="https://i.ytimg.com/vi/Fls_onRviPM/hqdefault.jpg" width="360" alt="官方原片封面">](https://www.youtube.com/watch?v=Fls_onRviPM&t=30s)<br>[观看原片 · OpenAI](https://www.youtube.com/watch?v=Fls_onRviPM&t=30s) | [<img src="examples/assets/developer-keynote/preview.gif" width="360" alt="真实中文译配片段动图">](examples/assets/developer-keynote/dubbed.mp4?raw=true)<br>[查看／下载中文 MP4 · 约 45 秒](examples/assets/developer-keynote/dubbed.mp4?raw=true) |

[查看全部来源与片段说明](examples/README.md) · [演示媒体权利边界](examples/LICENSE.md)

这里展示真实历史译配片段，视频、声音和截图不按源码 MIT 授权；原作品与声音权利仍归各自权利人，不因仓库公开而转让。动图为无声画面预览；要听配音，请点中文 MP4，若 GitHub 未直接播放，可下载后观看。

## 给你的 Agent 这句话

> 阅读仓库根目录 AGENTS.md、README.md、models.json。按我的电脑配置检查和准备环境、选择兼容的本地文本模型，在我授权后安装依赖及下载模型。先为我提供的视频做完整中文译配短样片；机器检查后交给我试听确认，再跑全片。遇到问题定位后局部修复、断点续跑，不放宽质量门禁，不上传我的任何资料。

不是所有 Agent 都自动读取 AGENTS.md；**明确让它阅读**，并给予完成任务所需但不过量的权限。

## 实际流程

```text
输入视频 → 提取音轨 → 英文 ASR／词时间戳 → 语义句
        → 忠实翻译／双语短句 → 文本语义审校
        → 预置声线或授权参考音色 TTS → 时长门禁
        → 最终中文音频独立 ASR → 精确文本匹配／真实词边界
        → 中英共轴字幕 → 原声垫底混音／视频渲染
        → 解码／字幕／时长／哈希检查 → 人工试听确认
```

## 环境准备

首版需要 **Apple Silicon macOS、Python 3.11、uv、FFmpeg（含 libx264、字幕烧录时含 libass）**。安装过程仅创建项目 `.venv`，不更改 Hermes/Codex 的账号、全局模型、配置或技能。其他平台检测为不支持，不会自动换成未经验证的后端。

在仓库根目录：

```bash
python3 -m dubkit doctor
# 阅读安装脚本并授权后：
bash bootstrap.sh --accept-install
source .venv/bin/activate
python -m dubkit doctor
python -m dubkit models list
# 另行同意语音模型下载后（默认 ASR + CustomVoice）：
python -m dubkit models fetch --accept-download
```

默认语音权重约数 GB，另需文本模型、Python 依赖和视频工作空间。准确固定版本见 `models.json`，不要把预估体积当作磁盘总需求。可复用本机完整、匹配版本的 Hugging Face 缓存；没有 `--accept-download` 时只查缓存，不会联网补模型。

**Ollama 是可选文本后端，不负责安装这里的 MLX ASR/TTS。** Agent 应检查已装模型与真实硬件，按官方模型库选择、经授权下载，再传入实际模型名。需要支持 JSON／JSON Schema 输出与忠实翻译。小模型可能漏译或不遵守格式，程序会拒绝，不以能出字作为合格标准。

## 从短样片开始

以下 `your-text-model` 是占位符，需替换为本机真实可用模型；`input.mp4` 由使用者提供。

```bash
python -m dubkit run \
  --input input.mp4 --job work/sample \
  --llm-url http://localhost:11434/v1 --llm-model your-text-model \
  --sample-seconds 20 --voice Vivian --burn-subtitles

python -m dubkit status --job work/sample
python -m dubkit verify --job work/sample
```

`--sample-seconds` 裁切源片，不会替你把台词截成半句。若末尾不完整或字幕布局、TTS 语速／内容不合格，先按证据修复或换完整短素材。默认 `Vivian` 为模型预置声线；也可按公开模型支持列表选择其他预置音色。各声线的稳定性不同，不能推定全部验证通过。

本地文件与公开、非凭证型视频 URL 均有输入实现；URL 依赖 `yt-dlp` 与平台网络条件，登录受限／签名 URL 应由使用者安全下载后提供本地文件。URL 下载路线的实测状态以 VALIDATION.md 为准。

不烧录时仍嵌入中、英两条可选择字幕轨。烧录时中文上、英文下，各一行，字号会按实际语义句长度缩小；过小则拒绝。时间取最终中文音频的 ASR 词边界，不按字符比例摊时间。该方法是 **ASR 词边界映射，不是宣称无误差的逐音素强制对齐**。

## 故障、续跑与修订

job 内保存 `state.json`、原文 ASR、`translations.json`、`semantic_review.json`、逐组音频／ASR／拒绝证据、字幕、`placement.json` 和 `verification.json`。这些是使用者的私密运行数据，不要提交 Git。

- 环境／网络故障修复后原命令续跑。命中相同输入和合同的阶段复用，已通过的音频不重配。
- 内容／时长拒绝先查看实际音频、预期文本与独立 ASR，不盲重试、不放宽门禁、不删掉事实。
- 翻译确有问题时，以 `translations.json` 的完整列表格式编辑修订文件，并保留所有英文词和组 ID：

```bash
python -m dubkit revise --job work/sample --translations revised-translations.json
# 然后重跑完全相同的 run 命令。
```

未改动的音频按自身指纹复用；改过的翻译需要重新审校和合成。换模型、音色、原片、采样范围或生成合同应建新 job。手动篡改缓存文件会触发完整性错误，不能通过篡改 checkpoint 骗过门禁。

## 样片确认后全片

**只有实际获得使用者的听审和画面确认后，Agent 才能记录批准：**

```bash
python -m dubkit approve --job work/sample --note '使用者已明确确认试听与画面通过'
python -m dubkit run \
  --input input.mp4 --job work/full \
  --llm-url http://localhost:11434/v1 --llm-model your-text-model \
  --voice Vivian --burn-subtitles --approved-sample work/sample
python -m dubkit verify --job work/full
```

全片不带 `--sample-seconds`。原片、模型、音色和生成合同须与已批样片相同；程序核对批准样片哈希。`MACHINE_COMPLETE` 表示机器检查通过，**不是人已验收**。

## 可选：原管线同类 Base 克隆模型

```bash
python -m dubkit models fetch --alias tts --accept-download
python -m dubkit run \
  --input input.mp4 --job work/reference-sample \
  --llm-model your-text-model --sample-seconds 20 \
  --ref-audio local/reference.wav --ref-text-file local/reference.txt \
  --burn-subtitles
```

参考音频和逐字对应的转录由使用者提供并确认授权。`ref_text` 在内部传内容，不传文本文件路径。不要默认克隆视频中的人，不把公开视频自动当成声音使用许可。当前 Base 接口和门禁实测状态见 VALIDATION.md。

## 其他文本服务与隐私

默认只允许本机请求。远程 HTTPS 服务需显式 `--allow-remote-llm`，并了解转录会发送给该服务及可能费用。凭证只从使用者自己的 `DUBKIT_API_KEY` 环境变量读取，不写代码、状态或命令参数。项目不会自动读取 Agent 的登录信息或配置。根目录 `.env.example` 仅为无真实凭证的配置参考，程序不会自动加载 `.env`；请在自己的安全环境中配置，不要提交真实值。

源码主包不含原始私人参考音频、原片、完整成片、模型权重、账号凭证、密钥或运行日志。仓库另含 [examples](examples/README.md) 中明确挑选的历史译配短片、动图和截图；这些演示保留历史合成声线，不等于声线匿名化，也不属于源码 MIT 授权范围。第三方素材、声音使用与后续再分发须独立核查。详见 [隐私边界](docs/PRIVACY.md)、[支持范围](docs/SUPPORT.md)、[模型来源](docs/MODELS.md)。

## 测试与许可

```bash
python -B -m unittest discover -s tests -v
```

单元测试中的 mock 只验证代码逻辑，不冒充真实模型推理。真实运行结果另记在 VALIDATION.md。

本项目自有源码和文档采用 [MIT](LICENSE)，允许在保留版权与许可声明的前提下使用、修改、商用和再分发；软件按原样提供，不作质量保证。

**MIT 不统一覆盖第三方依赖、模型、音色或媒体。** 特别注意：固定 Whisper 转换模型的模型卡未显式声明许可；FFmpeg 启用 libx264 等 GPL 组件后的构建也不能描述为纯 LGPL。项目不捆绑二进制依赖、模型权重或参考音色；演示媒体遵守 [独立边界](examples/LICENSE.md)，不授予 MIT 媒体许可。

## 致谢与相关工作

感谢 **MLX、MLX Whisper / OpenAI Whisper、MLX-Audio、Qwen / Qwen3-TTS、mlx-community、Hugging Face、NumPy、python-soundfile、FFmpeg / libx264 / libass、yt-dlp、Ollama、uv / Python** 以及全部间接依赖的维护者与贡献者。

特别感谢 **[OpenCreator（原 KrillinAI）](https://github.com/krillinai/OpenCreator)** 的开源视频翻译与创作工作流；它在这里作为相关工作致谢，本 CLI 不内嵌或调用其应用。**Hermes Agent、Codex** 等可作为可选操作端，不是内嵌运行时，也不表示官方关联。

完整项目链接与分工见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。52 项 Python 依赖的固定版本、许可摘要及保留的原文见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [third_party/inventory.json](third_party/inventory.json)。源码许可与演示媒体权利分开；仓库公开不构成第三方素材、声音或再分发的统一许可。未来若打包应用、依赖二进制或模型／媒体，必须重新核对实际再分发义务。
