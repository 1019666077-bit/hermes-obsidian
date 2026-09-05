# Hermes × Obsidian 笔记整理

微信小程序壳 + 整理 API：上传乱笔记 → 整理成 Obsidian Vault → 下载。

**Phase 5**：Docker 部署包装 + 微信登录桩（无 `WECHAT_*` 时为本地 DEV 模式）+ 配额可按 openid。详见 `PHASE5.md`。

**Phase 6**：GHCR 自动构建推送 + VPS / Caddy HTTPS 部署指引。详见 [`PHASE6.md`](PHASE6.md)。

**Phase 7**：微信真登录联调（AppID / AppSecret、DEV vs live、`wx.login` → Bearer、合法域名、常见错误）。详见 [`PHASE7.md`](PHASE7.md)。

## 目录

- `miniprogram/` — 微信小程序（开发者工具导入）
- `web/` — 本地浏览器试用页（无需微信开发者工具）
- `server/` — FastAPI 整理服务（默认脚本引擎；可选 Hermes）
- `docker-compose.yml` / `server/Dockerfile` — 容器部署
- `.env.example` — 环境变量模板（勿提交真实密钥）
- `skills/obsidian-vault-organize/` — Hermes 技能
- `fixtures/messy-input/` — 样例乱笔记
- `deploy/` — 生产 Compose / Caddy 示例
- `.github/workflows/docker-publish.yml` — 推 main 时发布 GHCR 镜像
- `PHASE1.md` … `PHASE7.md` — 阶段说明

## 快速开始

```bash
# 本地 API
cd server && ./start.sh

# 或 Docker（推荐部署）
cp .env.example .env    # 可选：填写 WECHAT_APPID / WECHAT_SECRET
docker compose up --build

# 健康检查 / 登录（DEV）/ 配额
curl -s http://127.0.0.1:8787/health
curl -s -X POST http://127.0.0.1:8787/api/login -H 'Content-Type: application/json' -d '{"code":"test"}'
curl -s -H 'X-Client-Id: demo' http://127.0.0.1:8787/api/quota

# 离线整理
python3 organize_vault.py --input fixtures/messy-input --output /tmp/demo-vault
```

微信真机需 **HTTPS 反代**（Caddy/Nginx），并在公众平台配置 request/upload/download 合法域名。真登录步骤见 [`PHASE7.md`](PHASE7.md)：在 `.env` 填入公众平台的 AppID 与 AppSecret（不要提交 git）。

Hermes Agent 请自行 clone：https://github.com/NousResearch/hermes-agent  
安装与 DeepSeek 配置见 `PHASE2.md`（**不要把 API Key 提交进仓库**）。无本地 Hermes / Key 时 API 使用 `organize_vault.py`。

## 本地网页试用

无需微信开发者工具，用浏览器走同一套整理 API：

```bash
cd server && ./start.sh
# open http://127.0.0.1:8787/  or /web/try.html
```

页面会显示 API 健康状态、`wechat_login` 模式与配额；点 DEV 登录（`POST /api/login`，code 为 `web-try`），再多选笔记文件整理，完成后可下载 vault zip。正式产品是微信小程序，本页仅本地试用。

## 微信开发者工具

导入 `miniprogram/`，开发阶段关闭域名校验；API 默认 `http://127.0.0.1:8787`。启动时 `wx.login` → `/api/login`，请求带 `Authorization: Bearer`；仍保留 `X-Client-Id` 备份。
