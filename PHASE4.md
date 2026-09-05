# Phase 4：Hermes 优先整理 + 免费配额桩

在 Phase 3 脚手架之上，后端优先走 Hermes Agent；无 Key / 失败时回退到离线脚本。增加按客户端 ID 的每日免费次数限制（演示级）。

## 1. 整理引擎策略

1. 若检测到模型 API Key（`~/.hermes/.env` 或进程环境中的 `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` / …），且存在可执行的 `run_hermes_organize.sh`，则优先调用 Hermes。
2. 脚本支持任务级路径：`INPUT_DIR`、`OUTPUT_DIR`、`OBSIDIAN_VAULT_PATH`（由 API 传入当前 job 目录）。
3. Hermes 超时约 240s（180–300s 带宽内）；失败或缺 Key 时回退 `organize_vault.py`。
4. 响应 JSON 的 `engine` 字段为 `"hermes"` 或 `"script"`。

**注意**：切勿在日志或 API 响应中打印 API Key。

## 2. 配额桩（免费层）

| 项 | 说明 |
|----|------|
| 识别 | 请求头 `X-Client-Id`（缺省为 `anonymous`） |
| 限额 | 每自然日 **5** 次整理（时区 **Asia/Shanghai**） |
| 超限 | HTTP **429**，中文提示 |
| 查询 | `GET /api/quota` → `{client_id, used, limit, remaining}` |
| 存储 | `server/jobs/quota.json`（文件级桩，非生产级） |

小程序在 `utils/config.js` 生成并持久化随机 client id，所有请求带上 `X-Client-Id`；整理页展示引擎与剩余次数，并处理 429。

## 3. 启动与自检

```bash
cd /workspace/hermes-obsidian/server
./start.sh

curl -s http://127.0.0.1:8787/health
# {"status":"ok","phase":4,...}

curl -s -H 'X-Client-Id: demo' http://127.0.0.1:8787/api/quota
```

## 4. 下一步（生产向）

- 微信登录换 session，配额绑定 openid
- 异步队列 + 进度推送；Hermes 长任务与脚本分流
- HTTPS / 合法域名；正式 AppID 与隐私合规
- 配额持久化到 Redis/DB，防多实例漂移

## 5. 目录速查

```
hermes-obsidian/
  server/main.py          # Hermes-first + /api/quota
  run_hermes_organize.sh  # INPUT_DIR / OUTPUT_DIR / OBSIDIAN_VAULT_PATH
  organize_vault.py       # 离线回退
  miniprogram/            # client id + 引擎/配额 UI
  PHASE4.md               # 本文档
```
