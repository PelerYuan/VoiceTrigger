# VoiceTrigger

本地持续语音监听与自定义触发词检测，面向 **Linux + Tesla P4** 部署，支持 Windows CPU 开发。命中名字、昵称或短语后输出结构化 JSON 事件，不需要把音频上传到云端。

**状态：早期版本。** 当前没有桌面通知和网络事件 API。真实摄像头、P4 推理及准确率仍需现场验收；完善文档和 CI 不等于已经达到生产可靠性。

## 功能

- 麦克风、RTSP、FFmpeg/ALSA 和音频文件输入。
- 能量分段 + Silero VAD + faster-whisper 本地转写。
- 中文字间空格容错、英文词边界、独立冷却去重。
- 触发词热更新、输入重连、有界音频队列。
- stdout / JSONL 事件；默认不保存录音。
- CUDA/cuDNN/CTranslate2 兼容组合、非特权 Docker 和持久化模型缓存。

## 快速开始

使用 64 位 Python 3.11/3.12，在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config.example.toml config.local.toml
.\.venv\Scripts\voice-trigger.exe devices
.\.venv\Scripts\voice-trigger.exe run --config config.local.toml --log-transcripts
```

本地配置已存在时不要覆盖。修改 `config.local.toml` 中现有 `[detection]` 的 `keywords` 和 `cooldown_seconds`。首次加载模型需要网络；本地默认 CPU INT8，服务器容器使用 P4 `int8_float32`。

RTSP / 文件输入需要 FFmpeg；容器已安装。日志调试可能暴露转写内容，生产环境关闭 `--log-transcripts`。

## 文档

| 文档 | 内容 |
| --- | --- |
| [项目概览](docs/index.md) | 当前能力、边界和阅读顺序 |
| [快速开始](docs/getting-started.md) | 本地运行与文件回归 |
| [P4 部署](docs/deployment.md) | 本地打包、服务器 GPU、RTSP / USB 输入 |
| [配置参考](docs/configuration.md) | 所有参数、环境变量和热更新规则 |
| [架构](docs/architecture.md) | 线程、队列、检测及故障语义 |
| [事件格式](docs/events.md) | 版本化 JSON 和字段语义 |
| [故障排查](docs/troubleshooting.md) | GPU、音频、误报、积压与日志 |
| [验收与维护](docs/operations.md) | 实测清单、升级和回滚 |

文档站配置为 MkDocs；GitHub Pages 工作流已提供，实际发布需要仓库管理员启用 Pages 和 `PUBLISH_DOCS` 变量。

## 开发与验证

核心测试不安装模型、不访问麦克风：

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
py -3.12 scripts/check_docs.py
```

Python 3.10 额外需要 `tomli`。文档预览：

```powershell
.\.venv\Scripts\python.exe -m pip install "mkdocs[i18n]==1.6.1"
.\.venv\Scripts\python.exe -m mkdocs serve
```

CI 配置覆盖 Windows / Linux、Python 3.10–3.12、Python 分发包、文档检查和容器导入 smoke test。真实 P4 与摄像头验收不在 GitHub 托管 CI 的覆盖范围内。

## 发布到 GitHub

`scripts/Publish-GitHub.ps1` 使用已有 `gh` 登录创建公开仓库，显式只提交源代码、示例配置和文档，不提交 `.env`、私有配置、录音、模型或日志。已有 Git 仓库或已有同名远程仓库时请先检查，不进行覆盖或强制推送。

```powershell
.\scripts\Publish-GitHub.ps1 -Repository VoiceTrigger -EnablePages
```

该脚本需要本机 Git 身份、GitHub CLI 登录及网络权限。没有附带开源许可证，许可证应由维护者另行选择。

## 贡献与安全

参见 [贡献指南](CONTRIBUTING.md)、[安全说明](SECURITY.md) 和 [变更记录](CHANGELOG.md)。不要在公开 Issue 附带 RTSP 密码、真实录音或个人转写。
