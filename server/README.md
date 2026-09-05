# Hermes×Obsidian API（Phase 3）

将杂乱笔记上传整理为 Obsidian vault，并返回可下载的 zip。

## 启动

```bash
cd /workspace/hermes-obsidian/server
./start.sh
# 或：python3 -m uvicorn main:app --host 0.0.0.0 --port 8787
```

默认监听 `http://127.0.0.1:8787`。依赖：`fastapi`、`uvicorn`、`python-multipart`（见 `requirements.txt`）。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/organize` | multipart 上传 `.zip` 或多文件 → 返回 `job_id` |
| GET | `/api/download/{job_id}` | 下载整理后的 vault zip |
| GET | `/api/jobs/{job_id}` | 查询任务状态 |

整理引擎默认调用仓库根目录的 `organize_vault.py --input … --output …`（离线确定性脚本，适合演示）。后续可用 Hermes（`run_hermes_organize.sh`）替换。

## curl 示例

```bash
# 健康检查
curl -s http://127.0.0.1:8787/health

# 用 fixtures 打成 zip 后整理
cd /workspace/hermes-obsidian
zip -r /tmp/messy.zip fixtures/messy-input
RESP=$(curl -s -F "files=@/tmp/messy.zip" http://127.0.0.1:8787/api/organize)
echo "$RESP"
JOB=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['job_id'])" "$RESP")
curl -s -o /tmp/vault-out.zip "http://127.0.0.1:8787/api/download/$JOB"
unzip -l /tmp/vault-out.zip | head
```

也可直接上传多个文件：

```bash
curl -s -F "files=@fixtures/messy-input/产品想法.txt" \
        -F "files=@fixtures/messy-input/meeting-notes-raw.md" \
        http://127.0.0.1:8787/api/organize
```

## 说明

- CORS 已对本地开发开放。
- 响应中不含 API Key；请勿在日志中打印密钥。
- 任务结果保存在 `server/jobs/` 临时目录（进程内内存登记，重启后 job_id 失效）。
