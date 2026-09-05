# Phase 7：微信真登录联调

本地 DEV 桩已能跑通登录与配额。本文说明如何换成公众平台 **真实 AppID / AppSecret**，以及 `wx.login` → `/api/login` → Bearer 的联调步骤。

> 不买云、不代部署。真机 HTTPS / 合法域名见 [`PHASE6.md`](PHASE6.md)。**不要**把 `.env`、AppSecret 提交进 git。

## 1. 在公众平台拿到 AppID / AppSecret

打开 [微信公众平台](https://mp.weixin.qq.com/) → 登录你的**小程序**账号。

- [ ] **开发 → 开发管理 → 开发设置**
- [ ] 复制 **AppID（小程序 ID）** → 对应 `WECHAT_APPID`
- [ ] 同页 **AppSecret（小程序密钥）**：生成或重置 → 对应 `WECHAT_SECRET`
- [ ] AppSecret **只出现一次**，立刻写入服务器环境变量；丢失就重置（旧 Secret 立即失效）
- [ ] 小程序 `project.config.json` 的 `appid` 必须与上述 AppID **一致**（不要再用 `touristappid` 做真登录）

AppSecret 不要写进小程序代码、不要发到群、不要提交仓库。

## 2. 写入服务器 `.env`

在仓库根目录（与 `docker-compose.yml` 同级）：

```bash
cp .env.example .env          # 若还没有
# 编辑 .env：
# WECHAT_APPID=wx................
# WECHAT_SECRET=你的Secret
```

- [ ] 只改本机 / VPS 上的 `.env`，确认 `.gitignore` 已忽略 `.env`
- [ ] 改完重启：`docker compose up -d` 或停掉再跑 `server/start.sh`
- [ ] 检查：`curl -s http://127.0.0.1:8787/health` 中 `wechat_login` 应为 `"live"`
- [ ] 未填或只填了一项 → 仍是 **DEV 模式**（`wechat_login: "dev"`）

Compose / 生产示例会把 `.env` 注入容器，无需把密钥写进镜像。

## 3. DEV 模式 vs 真登录

| | DEV（默认） | 真登录（live） |
|--|-------------|---------------|
| 条件 | `WECHAT_APPID` 或 `WECHAT_SECRET` 为空 | 两项都已设置 |
| `/health` | `"wechat_login": "dev"` | `"wechat_login": "live"` |
| `POST /api/login` | 接受任意 `code`，签发假 `openid`（`dev_openid_*`） | 用 `code` 调微信 `jscode2session`，返回真实 `openid` |
| 适用 | 开发者工具 + 本机 API | 真机 / 体验版 / 正式版 |
| 配额 | 仍按 session 的 openid（假或真）计次 | 按真实 openid，换设备也算同一人 |

两种模式都签发 **7 天** `session_token`，存在 `server/jobs/sessions.json`。后续请求带：

```http
Authorization: Bearer <session_token>
```

未带 token 时回退 `X-Client-Id`（与 Phase 4 兼容，换设备会变成另一个配额桶）。

## 4. 登录流程（小程序 → API）

```
小程序启动 / 进入整理页
    → wx.login() 拿到 code（5 分钟内一次性）
    → POST /api/login  { "code": "<wx.login code>" }
    → 保存 session_token、openid
    → 之后 /api/quota、/api/organize、/api/download
       请求头：Authorization: Bearer <token>
               X-Client-Id: <本机备份 id>
```

本地自检（DEV，任意 code）：

```bash
curl -s -X POST http://127.0.0.1:8787/api/login \
  -H 'Content-Type: application/json' \
  -d '{"code":"test"}'
# 应有 session_token、mode=dev、openid=dev_openid_...

TOKEN=...   # 上一步的 session_token
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/me
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8787/api/quota
```

真登录自检：必须用**小程序里 `wx.login` 刚拿到的 code**。用 curl 随便写一个 code 会得到「code 无效」。

小程序 API 基址：`miniprogram/utils/config.js` 默认 `http://127.0.0.1:8787`。也可在开发者工具控制台执行：

```js
wx.setStorageSync('hermes_api_base', 'https://你的域名')
```

无需改代码即可指向 HTTPS（真机必须 HTTPS）。

## 5. 合法域名清单（真机）

正式版 / 真机预览不能走裸 `http://IP:8787`。在公众平台配置（均须 **HTTPS、无端口号**）：

| 类型 | 必须勾选 | 示例 |
|------|----------|------|
| request 合法域名 | `/api/login`、`/api/quota`、`/api/me` | `https://api.example.com` |
| uploadFile 合法域名 | `/api/organize` | 同上 |
| downloadFile 合法域名 | `/api/download/{job_id}` | 同上 |

完整 VPS / Caddy / GHCR 步骤见 [`PHASE6.md` §3](PHASE6.md)。

开发者工具本机调试：

- [ ] 详情 → 本地设置 → **不校验合法域名**
- [ ] `config.js` 保持 `http://127.0.0.1:8787`
- [ ] 本机 `server/start.sh` 或 `docker compose up` 已启动

真机预览前：

- [ ] 域名 HTTPS 健康检查：`curl -s https://你的域名/health` → `wechat_login: live`
- [ ] 公众平台三项合法域名已填且与小程序 `baseUrl` 一致
- [ ] 开发者工具勾选合法域名校验，再预览

## 6. 常见错误

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| `/health` 仍是 `dev` | `.env` 未生效或只填了一项 | 确认进程能读到两个变量后重启 |
| `errcode=40029` / code 无效 | code 过期、已用过、或 AppID 与小程序不一致 | 重新 `wx.login`；核对 `project.config.json` 的 appid |
| `errcode=40163` / code 已使用 | 同一 code 打了两次 `/api/login` | 每次登录拿新 code，成功后复用 token |
| `errcode=40125` / secret 错误 | `WECHAT_SECRET` 填错或已重置 | 公众平台重置 Secret，更新 `.env`，重启 |
| `errcode=40013` / AppID 无效 | `WECHAT_APPID` 填错或不是小程序 AppID | 用开发设置页的小程序 AppID |
| 合法域名 / url not in domain list | 未配置或 HTTP/带端口 | 见 §5 与 [PHASE6](PHASE6.md) |
| 开发者工具登录成功、真机失败 | 真机走了 HTTP 或域名未备案 | 上 HTTPS；大陆服务器通常要备案 |
| 配额对不上 | 未带 Bearer，或 DEV 假 openid 与真 openid 混用 | 看 `/api/me` 的 `auth` / `openid` |

接口失败时响应 `detail` 为中文说明（或 `{ code, message }`）。**响应里不会出现 AppSecret。**

## 7. 相关文件

| 路径 | 用途 |
|------|------|
| `.env.example` | 变量模板（复制为 `.env`） |
| `server/main.py` | `jscode2session` / DEV 桩 / Bearer |
| `miniprogram/utils/config.js` | `baseUrl`、`wx.login`、Bearer |
| `PHASE5.md` | Docker + 登录桩总览 |
| `PHASE6.md` | HTTPS / 合法域名 / VPS |
