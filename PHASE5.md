# Phase 5：Docker 部署包装 + 微信登录桩

在 Phase 4 基础上增加容器化部署、环境变量模板，以及微信小程序登录换 session（无 AppID/Secret 时为本地开发模式）。

## 1. Docker 快速启动

```bash
cd /path/to/hermes-obsidian
cp .env.example .env          # 可选；填入 WECHAT_* 以启用真登录
docker compose up --build -d

curl -s http://127.0.0.1:8787/health
# {"status":"ok","phase":5,"wechat_login":"dev",...}
```

默认镜像使用 **脚本整理引擎**（`ORGANIZE_ENGINE=script`），不捆绑完整 Hermes Agent（体积大、依赖重）。

### 可选：挂载 Hermes（进阶）

```yaml
# docker-compose.yml volumes 中取消注释：
# - ${HOME}/.hermes:/root/.hermes:ro
```

并在 `.env` 中设置 `ORGANIZE_ENGINE=auto`（或 `hermes`），确保 `~/.hermes/.env` 内有模型 API Key。容器内仍需自行安装/挂载 `hermes-agent` 与 `hermes` CLI 才能真正跑通 Hermes；多数部署仅用脚本引擎即可。

## 2. 微信真机：必须 HTTPS 反代

微信小程序正式版 / 真机预览要求：

1. **HTTPS** 合法域名（不能用裸 `http://IP:8787`）
2. 在 [微信公众平台](https://mp.weixin.qq.com/) → **开发 → 开发管理 → 开发设置 → 服务器域名** 中配置：
   - request 合法域名
   - uploadFile 合法域名
   - downloadFile 合法域名  
   均指向你的 API 域名，例如 `https://api.example.com`

### Caddy 示例

```caddyfile
api.example.com {
    reverse_proxy 127.0.0.1:8787
}
```

### Nginx 示例

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;
    # ssl_certificate     /path/fullchain.pem;
    # ssl_certificate_key /path/privkey.pem;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

开发者工具本地调试可继续用 `http://127.0.0.1:8787`，并关闭「不校验合法域名」。

## 3. 微信登录桩

| 条件 | 行为 |
|------|------|
| 设置了 `WECHAT_APPID` + `WECHAT_SECRET` | `POST /api/login` 调用 `jscode2session`，返回真实 `openid` + `session_token` |
| **未设置**（默认） | **开发模式**：接受任意 `code`，签发假 `openid`（`dev_openid_*`）与 token，便于本机联调 |

- Token 有效期 **7 天**，映射保存在 `server/jobs/sessions.json`
- 请求头带 `Authorization: Bearer <token>` 时，**配额按 openid** 计量
- 未登录时回退 `X-Client-Id`（与 Phase 4 兼容）
- `GET /api/me`：返回身份（openid / client_id）与配额

### 如何填写 WECHAT_*（真登录）

完整联调清单（AppID/Secret、DEV vs live、`wx.login` 流程、合法域名、常见错误）见 **[`PHASE7.md`](PHASE7.md)**。

1. 登录微信公众平台 → 你的小程序
2. **开发 → 开发管理 → 开发设置**，复制 **AppID(小程序ID)** → 写入 `.env` 的 `WECHAT_APPID=`
3. 同页生成/重置 **AppSecret** → 写入 `WECHAT_SECRET=`（只放服务器环境变量，**不要**写进小程序代码或 git）
4. 重启 API / `docker compose up -d`
5. `/health` 中 `wechat_login` 应为 `"live"`

## 4. 环境变量（`.env.example`）

| 变量 | 说明 |
|------|------|
| `WECHAT_APPID` / `WECHAT_SECRET` | 微信登录；空=dev 模式 |
| `ORGANIZE_ENGINE` | `auto` \| `hermes` \| `script` |
| `HERMES_TIMEOUT_SEC` | Hermes 超时（默认 240） |
| `FREE_QUOTA_LIMIT` | 每日免费整理次数（默认 5，北京时间）。用完 429，文案提示明天恢复或开通会员（演示，无支付） |

## 5. 小程序

启动或进入整理页时：`wx.login` → `POST /api/login` → 本地保存 `session_token`；后续 API 带 `Authorization: Bearer`，并保留 `X-Client-Id` 作备份。

## 6. 接口一览（相对 Phase 4 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | `{code}` → token / openid |
| GET | `/api/me` | 当前身份 + 配额 |
| GET | `/health` | `phase: 5`，含 `wechat_login` |

## 7. 目录速查

```
hermes-obsidian/
  docker-compose.yml
  .env.example
  PHASE5.md                 # 本文档
  server/Dockerfile
  server/main.py            # 登录 + 配额按 openid
  miniprogram/utils/config.js
```
