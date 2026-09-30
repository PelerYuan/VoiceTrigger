# 贡献指南

请先阅读 [架构](docs/architecture.md) 与 [配置参考](docs/configuration.md)。修改应聚焦一个行为，避免在功能补丁中同时升级 GPU 依赖。

## 本地验证

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
py -3.12 scripts/check_docs.py
py -3.12 -m compileall -q src tests scripts
```

核心逻辑应优先使用模拟音频和识别器测试，不在单元测试里访问麦克风、GPU、网络或下载模型。Python 3.10 使用 `tomli` 兼容 TOML。

GPU、摄像头和模型精度相关补丁需另附实际环境与验收结果，不能用普通 CI 通过代替。涉及事件字段时同步 Schema、事件文档和测试；涉及参数时同步示例配置与参考文档。

## 提交前

- 不提交 `.env`、`config.local.toml`、模型、日志或真实录音。
- 检查 Git 暂存区及文档中的个人地址和凭据。
- 新增外部依赖要说明必要性与 P4 兼容性。
- 提供复现步骤、验证命令和行为变化说明。

可本地执行 `python -m mkdocs build --strict` 验证文档站。工具安装见 [快速开始](docs/getting-started.md)。
