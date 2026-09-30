# 快速开始

## 环境

本地使用 64 位 Python 3.11/3.12。容器使用 Python 3.10，项目支持 Python 3.10–3.12。麦克风由 sounddevice 采集；RTSP 或文件输入需要 FFmpeg。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config.example.toml config.local.toml
.\.venv\Scripts\voice-trigger.exe devices
```

如果本地配置已经存在，不要覆盖，直接编辑。修改现有 `[detection]`：

```toml
[detection]
keywords = ["张三", "小张", "指定短语"]
cooldown_seconds = 10.0
```

配置 `[input].device` 后启动：

```powershell
.\.venv\Scripts\voice-trigger.exe run --config config.local.toml --log-transcripts
```

本地默认使用 CPU INT8，容器环境变量切换为 P4 CUDA INT8/FP32。首次加载需要下载模型，后续复用缓存。日志出现 `Audio input connected` 后说触发词，观察 JSON 输出。Ctrl+C 停止。

## 文件回归

```powershell
.\.venv\Scripts\voice-trigger.exe run --config config.local.toml --input-file test.wav --log-transcripts
```

需要 FFmpeg。文件输入处理至结束退出；音频路径应放在本地私有目录，不要上传真实录音。文件模式的捕获时间是处理时的墙钟时间，不是录音原始时间。

## 文档预览

```powershell
.\.venv\Scripts\python.exe -m pip install "mkdocs[i18n]==1.6.1"
.\.venv\Scripts\python.exe -m mkdocs serve
```

完整参数见 [配置参考](configuration.md)，服务器上线见 [P4 部署](deployment.md)。
