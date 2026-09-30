# 故障排查

## GPU 不可用

依次检查宿主机 `nvidia-smi`、CUDA 容器的 `nvidia-smi` 和 `voice-trigger check`。诊断报告含 `cuda_error` 时停止部署；`check` 的成功退出码只代表诊断命令运行，不代表 GPU 可用。真实模型推理仍需验证。

不要盲目升级推理依赖或 NVIDIA 驱动。保持项目 CUDA/cuDNN/CTranslate2 组合，先确认所用驱动支持 P4。启动失败不会自动回退 CPU。

## RTSP 有画面但没有识别

确认摄像头麦克风启用、准确 RTSP 路径包含音轨，并用部署指南的 ffprobe 命令检查。鉴权失败、网络不通和只有视频均无法监听。日志为保护凭据会隐藏 FFmpeg 原始错误，请在私有环境直接诊断。

## 麦克风不断重试

检查设备编号、系统麦克风权限、单声道 16 kHz 是否受支持。Linux USB 容器还需 `/dev/snd` 映射和实际音频组。不是映射 `/dev/video0`。

## 漏报或误报

先短暂开启 `--log-transcripts`。确认声音能被分段、模型转写中确实包含关键词，然后检查冷却和同音异字。只听到同音字不等于字符串匹配会成功。电视背景声也可能触发；该项目不识别呼叫者身份。

## Recognition is behind

持续输入处理跟不上。查看 GPU、推理耗时、模型大小和并发负载。可测试 `base` 模型或更短的停顿等待，但不要仅靠增大队列掩盖积压。增大队列通常增加通知延迟并消耗更多内存。

## 模型下载失败

检查服务器能否访问模型源及 `/models` 权限。可准备已转换的 CTranslate2 模型目录并挂载，再将 `recognition.model` 设置为容器内路径。不要把模型缓存提交到仓库。

## Docker 安装依赖时报 pip AssertionError

Ubuntu 基础镜像自带的旧 pip 可能在解析复杂依赖图时崩溃。Dockerfile 先安装固定的 pip 25.2 再安装项目，不要删除此步骤或用宿主机 pip 版本代替容器内的检查。

## 导入 faster-whisper 时缺少 requests

固定的 faster-whisper 1.1.1 直接使用 requests，但其元数据没有显式声明该依赖。项目显式安装 requests，并限制 Hugging Face Hub 为兼容的 0.x 系列；不要只安装 faster-whisper 后省略项目的其他依赖。

## JSONL 占满磁盘

当前不自动轮转 JSONL。使用外部 logrotate 或定期清理并重启服务重新打开文件；普通文件重命名后进程仍可能写到原句柄。Docker stdout 日志轮转和 JSONL 文件轮转是两回事。
