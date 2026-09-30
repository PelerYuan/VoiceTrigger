# 事件格式

stdout 每行一个命中事件；诊断日志在 stderr。可选 JSONL 文件追加写入并刷新。结构定义见项目中的 `schemas/keyword-event.schema.json`。

```json
{
  "schema_version": 1,
  "type": "keyword_detected",
  "id": "b4292b2d-fb9e-4515-aed2-b16b065585a3",
  "detected_at": "2026-09-30T02:00:01+00:00",
  "audio_end_at": "2026-09-30T02:00:00+00:00",
  "keywords": ["张三"],
  "text": "张三，请过来一下。",
  "audio_seconds": 2.1,
  "recognition_seconds": 0.4
}
```

示例仅用于说明格式，耗时不是性能承诺。

| 字段 | 语义 |
| --- | --- |
| `schema_version` | 格式版本，当前为 1 |
| `type` | 固定为 `keyword_detected` |
| `id` | 当前事件的 UUID；不是对原始呼叫的稳定标识 |
| `detected_at` | 推理完成并命中时的 UTC 时间 |
| `audio_end_at` | 片段捕获结束的 UTC 时间；文件输入为处理时间 |
| `keywords` | 本次命中且未处于冷却的词 |
| `text` | 接受的识别片段拼接文字，可能含周围内容 |
| `audio_seconds` | PCM 片段长度，含预缓冲/静音/重叠 |
| `recognition_seconds` | 当前片段的转写耗时，不含队列等待 |

消费者应忽略未知字段，对未知 `schema_version` 明确拒绝或隔离处理。增加可选字段可保持版本 1；删除、重命名或改变字段类型需要新格式版本。当前没有网络传输和事件重放能力。
