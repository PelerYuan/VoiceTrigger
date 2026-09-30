# VoiceTrigger

持续监听音频，使用本地 faster-whisper 转写中文/英文，命中自定义触发词时输出 JSON 事件。当前只实现监听和事件输出，**还没有电脑推送通知**。

流程：音频输入 → 能量门限分段 → Silero VAD → Whisper 转写 → 关键词匹配 → 冷却去重 → JSONL。

这是分段近实时识别，不是毫秒级唤醒词引擎。触发延迟包括等待停顿、音频分段和推理。匹配依赖转写结果，人名同音字可能漏报；需现场测试。默认不保存录音。

## 1. Windows 本地验证（可选，使用 CPU）

需要安装 64 位 Python 3.11/3.12。若没有 `py` 命令，安装 Python Launcher，或者用实际 Python 可执行文件路径代替 `py -3.12`。本地没有 P4 不影响开发，部署到服务器时才使用 P4。

```powershell
cd D:\Programming\CodexProject\VoiceTrigger
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config.example.toml config.local.toml
Copy-Item .env.example .env
.\.venv\Scripts\voice-trigger.exe devices
.\.venv\Scripts\voice-trigger.exe run --config config.local.toml --log-transcripts
```

从示例创建本地配置后，修改 `[detection]`。若配置已存在，保留现有文件，不要执行上述覆盖复制：

```toml
[detection]
keywords = ["你的名字", "你的昵称", "指定短语"]
cooldown_seconds = 10.0
```

不要新建第二个同名 TOML 表，直接修改现有表。`[input].device` 默认为系统默认输入；可填 `devices` 输出的设备编号（整数）或设备名称。确认 Windows 允许终端访问麦克风。按 Ctrl+C 停止。

安装依赖和首次加载模型需要网络。模型缓存到 `models/`。加载完成后音频在本地处理，不上传云端。运行中更新关键词和冷却时间会自动重载，其他配置修改需重启。

麦克风输入不依赖 FFmpeg；RTSP、文件和自定义 FFmpeg 输入需要 FFmpeg 在 PATH 中，或填写 `[input].ffmpeg` 绝对路径。容器已经安装 FFmpeg。

## 2. 确认服务器条件

以下部署步骤假设服务器为 **Linux x86-64**，已安装 Docker Engine、Compose v2、支持 P4 的 NVIDIA 驱动和 NVIDIA Container Toolkit。不要为此盲目升级到最新 NVIDIA 驱动，先确认其仍支持 P4。

在服务器执行：

```bash
nvidia-smi
docker --version
docker compose version
nvidia-ctk --version
```

先确认 `nvidia-smi` 能看到 Tesla P4。如果驱动不可用，先解决宿主机驱动，而不是进入容器排查。

如果 Toolkit 已安装但 Docker 尚未配置 GPU runtime，可执行：

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**重启 Docker 会影响已有容器，选择合适维护时间。** Rootless Docker 的配置不同，不应直接套用上述命令。Toolkit 尚未安装时，按服务器发行版使用 NVIDIA 官方安装文档：<https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>。

验证 Docker 能使用 P4：

```bash
docker run --rm --gpus all nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

成功显示 P4 才继续。这里验证的是容器 GPU 可见性，仍不是模型推理测试。

## 3. 本地构建镜像

先启动 Docker Desktop 并切换到 Linux containers。构建机器不需要 GPU。

```powershell
cd D:\Programming\CodexProject\VoiceTrigger
docker build --platform linux/amd64 -t voice-trigger:p4 .
docker save -o voice-trigger-p4.tar voice-trigger:p4
```

默认依赖组合：`faster-whisper==1.1.1`、`ctranslate2==4.4.0`、CUDA 12.2/cuDNN 8。P4 使用 `cuda + int8_float32`，不使用 FP16。固定的是兼容组合，不是最新版本，也不是对目标机器兼容性的保证。

依据：

- P4 硬件：<https://developer.nvidia.com/cuda/gpus/legacy>
- CTranslate2 量化支持：<https://opennmt.net/CTranslate2/quantization.html>
- faster-whisper GPU 依赖说明：<https://github.com/SYSTRAN/faster-whisper#gpu>

## 4. 配置摄像头输入

### A. 网络摄像头 / RTSP（默认 Compose 配置）

摄像头必须启用麦克风并在 RTSP 流中包含音轨，只有视频不能监听。向摄像头文档确认准确地址，不要假定示例路径可用。

编辑本地 `.env`：

```dotenv
CAMERA_RTSP_URL=rtsp://username:password@192.168.1.100:554/stream
VOICE_MODEL=small
```

密码中的特殊字符需要正确 URL 编码。不要把 `.env` 提交到 Git。启动前可在服务器检查音轨：

```bash
read -r -s -p 'RTSP URL: ' CAMERA_RTSP_URL; echo
docker run --rm --entrypoint ffprobe voice-trigger:p4 \
  -v error -rtsp_transport tcp -stimeout 15000000 \
  -select_streams a -show_entries stream=codec_name,sample_rate,channels \
  -of json "$CAMERA_RTSP_URL"
unset CAMERA_RTSP_URL
```

`streams` 中应有音频流。上面的探测命令针对镜像内 FFmpeg 4.x；监听程序会自动检测旧版 `-stimeout` / 新版 `-timeout`，不要把两个参数混用。没有音频、鉴权失败或无法连接时先修复摄像头输入；以上命令可能产生含地址的 FFmpeg 诊断，不要公开分享含密码的输出。

### B. USB 摄像头麦克风（Linux ALSA）

这类输入读取音频设备，不是 `/dev/video0`。在服务器用 `arecord -l` 确认设备编号，修改 `config.local.toml`：

```toml
[input]
kind = "ffmpeg"
input_args = ["-f", "alsa", "-i", "hw:1,0"]
```

同时在 `compose.yaml` 中移除 `VOICE_INPUT_KIND`、`VOICE_INPUT_URL` 两行，并在服务下增加：

```yaml
devices:
  - /dev/snd:/dev/snd
group_add:
  - "29"
```

`hw:1,0` 和组号 `29` 都是示例。用 `stat -c '%g' /dev/snd/pcm*` 查询实际组号。不要为了访问音频设备开启 privileged。

## 5. 传到服务器

以下命令里的 `USER@SERVER` 必须替换为真实 SSH 用户和服务器地址。

```powershell
ssh USER@SERVER "mkdir -p ~/VoiceTrigger"
scp voice-trigger-p4.tar compose.yaml config.local.toml .env USER@SERVER:~/VoiceTrigger/
```

不必上传本地虚拟环境、源码、录音或模型缓存，运行所需代码已经包含在镜像里。配置文件和 `.env` 不包含在镜像中。

也可以将源码部署到服务器并执行 `docker compose build`，但这不是上述本地打包流程。

## 6. 加载、检查和启动

服务器执行：

```bash
cd ~/VoiceTrigger
chmod 600 .env
docker load -i voice-trigger-p4.tar
docker compose config --quiet
docker compose run --rm --no-deps voice-trigger check
```

诊断报告中的 `cuda_compute_types` 必须含 `int8_float32`。出现 `cuda_error` 时不要继续，也不要把 `check` 的退出码当作 GPU 验证结果，它是诊断命令。

先在前台验证：

```bash
docker compose run --rm --no-deps voice-trigger run \
  --config /app/config.toml --log-transcripts
```

第一次会下载 Whisper 模型到持久化卷；服务器需要能访问模型源，也可以事先准备本地 CTranslate2 模型目录并调整配置/挂载。等到日志显示 `Audio input connected` 和识别结果后，对摄像头说配置的名字，确认输出 `keyword_detected` JSON。按 Ctrl+C 退出。

验证成功再后台运行（使用导入镜像，不在服务器构建）：

```bash
docker compose up -d --no-build
docker compose logs -f --tail=100
```

查看事件文件和 GPU：

```bash
docker compose exec voice-trigger tail -f /events/triggers.jsonl
nvidia-smi
```

GPU 利用率不需要始终很高，静音时不应持续跑 Whisper。命中事件包含 UUID、UTC ISO 时间、命中的词、转写文本、音频长度和识别耗时。每个词独立冷却；服务重启后冷却状态清空。

停止服务：`docker compose down`。不要加 `-v`，否则会删除命名卷中的模型缓存和事件日志。

## 7. 验收和调参

- 连续呼叫名字、昵称和短语，确认命中；说相似发音，检查误报。
- 静音、电视背景声、连续聊天和断开摄像头网络分别测试。
- 若日志出现 `Recognition is behind`，说明识别积压、最旧音频被丢弃，可能漏报。先检查 GPU 是否在工作，再尝试 `base` 模型。
- 小声说话经常漏掉时降低 `audio.rms_threshold`，噪声太多则提高它。
- 默认等待 0.7 秒停顿后识别；连续讲话最多 8 秒分段，保留 0.5 秒重叠，不能承诺瞬时触发。
- 中文使用多语言 `small`，不要选择 `.en` 模型。准确率不足时实际评估 `medium`，不要假定 P4 对所有模型都能实时处理。
- 中文关键词允许字间空格。英文关键词忽略大小写并按词边界匹配。没有模糊/拼音匹配，同音异字需要明确添加可接受的变体。
- `initial_prompt` 可提供词汇背景，但可能影响误报，默认不开启。

## 日志、隐私与测试

音频只在内存处理，不保存全天录音。默认不记录所有转写，但命中事件会保留附近的文字；只对有权采集的音频启用监听。

日志写到 stderr，命中事件写到 stdout 和 JSONL。生产环境不要开启 `--log-transcripts`。JSONL 当前不自动轮转，需要定期清理或外部 logrotate；Docker stdout 日志已限制 10 MB × 3 文件。设置 `output.events_file = ""` 可关闭事件文件。

持续输入队列有容量限制，识别跟不上时丢弃最旧片段并告警；文件输入则等待，不丢片段。RTSP 断开后自动重连，TCP I/O 超时为 15 秒。

核心测试无需安装推理依赖、访问麦克风或下载模型：

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```

音频文件回归需要 FFmpeg：

```powershell
.\.venv\Scripts\voice-trigger.exe run --config config.local.toml --input-file test.wav --log-transcripts
```

真实麦克风、RTSP、Docker 镜像构建与 P4 模型推理必须在相应设备上测试，核心单元测试不能替代这些验收。

后续可将命中事件接入 WebSocket、Webhook 或电脑通知客户端。本版本不开放网络端口。
