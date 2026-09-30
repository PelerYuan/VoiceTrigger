# VoiceTrigger

VoiceTrigger 将摄像头或麦克风音频在本地转写，检测自定义名字、昵称或短语，并输出结构化事件。目标场景是 Linux 服务器 + Tesla P4，Windows 可用 CPU 开发验证。

## 当前能力

- microphone、RTSP、FFmpeg/ALSA 和音频文件输入。
- 能量分段、Silero VAD、本地 Whisper 转写。
- 中文空格容错、英文词边界、每个词独立冷却。
- 关键词配置热更新、RTSP 重连、容量受限的内存队列。
- stdout / JSONL 事件，非特权 Docker 部署。

## 当前边界

本项目仍是早期版本，并非已验收的生产系统。尚未实现桌面通知、网络事件 API、身份认证、事件重放、说话人识别或持久化去重。JSONL 不自动轮转；不能保证零误报、零漏报或固定延迟。

核心测试使用模拟音频和识别器，不代表 P4、摄像头或真实语音精度已经验证。GitHub Actions 的容器测试也没有真实 GPU。

## 阅读顺序

1. [快速开始](getting-started.md)：本地运行和修改关键词。
2. [P4 部署](deployment.md)：容器、GPU 和摄像头输入。
3. [配置参考](configuration.md)：参数、覆盖顺序及热更新。
4. [架构与边界](architecture.md) / [事件格式](events.md)：理解处理和输出。
5. [故障排查](troubleshooting.md) / [验收与维护](operations.md)：上线前检查。
