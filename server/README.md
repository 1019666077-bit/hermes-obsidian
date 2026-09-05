# Hermes×Obsidian API（Phase 5）

将杂乱笔记上传整理为 Obsidian vault，并返回可下载的 zip。  
默认脚本引擎；可选 Hermes。含微信登录桩与每日免费配额（按 openid 或 client id）。

## 启动

```bash
cd server && ./start.sh
# 或：python3 -m uvicorn main:app --host 0.0.0.0 --port 8787
# 或仓库根目录：docker compose up --build
```

默认监听 `http://127.0.0.1:8787`。依赖见 `requirements.txt`。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 跳转到本地试用页 `/web/try.html` |
| GET | `/web/*` | 静态试用页（仓库 `web/`） |
| GET | `/health` | 健康检查（`phase: 5`，`wechat_login`） |
| POST | `/api/login` | `{code}` → `session_token` / `openid`（无 WECHAT_* 为 DEV 模式） |
| GET | `/api/me` | 当前身份 + 配额 |
| GET | `/api/quota` | 配额；优先 Bearer→openid，否则 `X-Client-Id` |
| POST | `/api/organize` | multipart 上传 → `job_id`、`engine`、`quota` |
| GET | `/api/download/{job_id}` | 下载 vault zip |
| GET | `/api/jobs/{job_id}` | 任务状态 |

### 登录

- 设置 `WECHAT_APPID` + `WECHAT_SECRET` → 调用微信 `jscode2session`
- 否则 **DEV 模式**：任意 `code` 换假 `openid`（`dev_openid_*`）与 token（7 天，存 `jobs/sessions.json`）
- 真登录联调清单见仓库根目录 [`PHASE7.md`](../PHASE7.md)

### 整理引擎

环境变量 `ORGANIZE_ENGINE=auto|hermes|script`（容器默认 `script`）。

### 配额

- 有 `Authorization: Bearer <token>` → 按 openid
- 否则 `X-Client-Id`（缺省 `anonymous`）
- 每日 `FREE_QUOTA_LIMIT`（默认 5，北京时间）；超限 429，文案含免费试用说明与「开通会员」提示（演示，无在线支付）

## curl 示例

```bash
curl -s http://127.0.0.1:8787/health
TOKEN=$(curl -s -X POST http://127.0.0.1:8787/api/login -H 'Content-Type: application/json' -d '{"code":"dev1"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/me
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/quota

cd /path/to/hermes-obsidian
zip -r /tmp/messy.zip fixtures/messy-input
RESP=$(curl -s -H "Authorization: Bearer $TOKEN" -H 'X-Client-Id: demo' -F "files=@/tmp/messy.zip" http://127.0.0.1:8787/api/organize)
echo "$RESP"
```

## Docker 说明

见仓库根目录 `PHASE5.md`、`Dockerfile`、`docker-compose.yml`。  
**不要**把 `.env` / API Key / AppSecret 提交进 git。可选挂载 `~/.hermes` 以启用 Hermes（进阶）。
