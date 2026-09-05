# Hermes×Obsidian API（Phase 4）

将杂乱笔记上传整理为 Obsidian vault，并返回可下载的 zip。  
优先调用 Hermes（需模型 API Key）；失败或缺 Key 时回退 `organize_vault.py`。含演示级每日免费配额。

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
| GET | `/health` | 健康检查（`phase: 4`） |
| GET | `/api/quota` | 查询当日配额；请求头可选 `X-Client-Id` |
| POST | `/api/organize` | multipart 上传 → 返回 `job_id`、`engine`、`quota` |
| GET | `/api/download/{job_id}` | 下载整理后的 vault zip |
| GET | `/api/jobs/{job_id}` | 查询任务状态 |

### 整理引擎

1. 有 API Key（`~/.hermes/.env` 或环境变量）且 `run_hermes_organize.sh` 可执行 → Hermes（超时 ~240s）
2. 否则 / 失败 → `organize_vault.py`（`engine: "script"`）

`run_hermes_organize.sh` 接受 `INPUT_DIR` / `OUTPUT_DIR` / `OBSIDIAN_VAULT_PATH`。

### 配额桩

- Header `X-Client-Id`（缺省 `anonymous`）
- 每自然日 5 次（Asia/Shanghai）；超限 HTTP 429
- 状态文件：`server/jobs/quota.json`

## curl 示例

```bash
curl -s http://127.0.0.1:8787/health
curl -s -H 'X-Client-Id: demo' http://127.0.0.1:8787/api/quota

cd /workspace/hermes-obsidian
zip -r /tmp/messy.zip fixtures/messy-input
RESP=$(curl -s -H 'X-Client-Id: demo' -F "files=@/tmp/messy.zip" http://127.0.0.1:8787/api/organize)
echo "$RESP"
JOB=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['job_id'])" "$RESP")
curl -s -o /tmp/vault-out.zip "http://127.0.0.1:8787/api/download/$JOB"
unzip -l /tmp/vault-out.zip | head
```

## 说明

- CORS 已对本地开发开放。
- **响应与日志不含 API Key**；请勿打印密钥。
- 任务结果在 `server/jobs/`；进程内登记，重启后 `job_id` 失效。
- 发布树不含 `hermes-agent` / `.env`；无本地 Hermes 时自动用脚本引擎。
