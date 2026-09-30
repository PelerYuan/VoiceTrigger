# 配置参考

配置使用 TOML。加载顺序为内置默认值 → 配置文件 → 环境变量 → CLI 的文件输入/调试选项。未知顶层表和字段会报错，不会悄悄忽略拼写错误。

相对路径均相对于**进程工作目录**，不是配置文件所在目录。Docker 工作目录是 `/app`；Compose 覆盖模型和事件路径为持久化卷。

## 输入 `[input]`

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `kind` | `microphone` | `microphone` / `rtsp` / `ffmpeg` / `file` |
| `device` | 空字符串 | 系统默认音频输入，或编号/名称 |
| `url` | 空字符串 | RTSP 地址或文件路径 |
| `ffmpeg` | `ffmpeg` | 可执行文件名称或绝对路径 |
| `input_args` | `[]` | FFmpeg 输入参数数组，不通过 shell 执行 |
| `reconnect_seconds` | `3.0` | 持续输入断开后的重试间隔 |

RTSP 自动使用 TCP 和 15 秒 I/O 超时；程序检测 FFmpeg 4.x 的 `stimeout` 与新版 `timeout`。自定义 FFmpeg 输入必须提供 `input_args`，输出格式由程序统一转换。

## 识别 `[recognition]`

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `model` | `small` | 多语言模型名称或已有 CTranslate2 模型目录 |
| `device` | `cpu` | `cpu` 或 `cuda`，不自动回退 |
| `compute_type` | `int8` | P4 容器覆盖为 `int8_float32` |
| `language` | `zh` | 空字符串允许自动语言检测 |
| `download_root` | `models` | 模型缓存目录 |
| `beam_size` | `1` | 推理解码搜索宽度 |
| `cpu_threads` | `4` | CPU 推理线程，不是进程 CPU 硬配额 |
| `initial_prompt` | 空字符串 | 可选词汇背景，默认不开启 |
| `min_log_probability` | `-1.0` | 接受识别片段的最低平均 log probability |
| `max_no_speech_probability` | `0.6` | 接受识别片段的最高无语音概率 |

这些概率阈值来自识别器，不是“关键词命中置信度”，不能据此保证正确呼叫。

## 音频 `[audio]`

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `sample_rate` | `16000` | 当前必须是 16000 Hz，PCM 单声道 INT16 |
| `frame_seconds` | `0.1` | 每帧长度 |
| `rms_threshold` | `0.012` | 归一化能量门限，不是语音分类器 |
| `pre_roll_seconds` | `0.3` | 发声前保留的音频 |
| `silence_seconds` | `0.7` | 停顿到此长度后送入识别 |
| `min_speech_seconds` | `0.2` | 最短高能量声音长度 |
| `max_segment_seconds` | `8.0` | 连续输入的分段上限 |
| `overlap_seconds` | `0.5` | 长语音切分时的重叠 |
| `queue_size` | `6` | 等待识别的片段上限 |

持续输入积压时丢弃最旧片段并告警；文件输入则等待消费者，不丢片段。

## 检测和输出

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `detection.keywords` | 示例文件为张三、小张 | 非空字符串数组 |
| `detection.cooldown_seconds` | `10.0` | 每个词独立冷却；0 表示关闭冷却 |
| `output.events_file` | `events/triggers.jsonl` | 空字符串关闭文件记录 |
| `output.log_transcripts` | `false` | 是否记录全部识别文字，仅建议调试 |

只有 `detection` 的关键词和冷却时间支持热更新，其他修改必须重启。热更新保留仍存在词的冷却状态；进程重启会清空状态。配置无效时保留上一次检测设置并告警。

## 环境变量

| 环境变量 | 覆盖配置 |
| --- | --- |
| `VOICE_INPUT_KIND` | `input.kind` |
| `VOICE_INPUT_URL` | `input.url` |
| `VOICE_DEVICE` | `recognition.device` |
| `VOICE_COMPUTE_TYPE` | `recognition.compute_type` |
| `VOICE_MODEL` | `recognition.model` |
| `VOICE_MODEL_CACHE` | `recognition.download_root` |
| `VOICE_EVENTS_FILE` | `output.events_file` |

Compose 的 `.env` 只用于 Compose 插值，本地 CLI 不会自动读取它。摄像头凭据只应出现在被忽略的 `.env` 或私有配置中。
