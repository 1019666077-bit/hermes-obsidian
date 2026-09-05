# Phase 6：GHCR 镜像发布 + VPS / HTTPS 部署指引

在 Phase 5 容器化基础上，通过 GitHub Actions 将 API 镜像推送到 **GHCR**，并在自有 VPS 上用 Compose + Caddy 提供 HTTPS，供微信小程序真机使用。

> **说明**：本仓库无法代替你完成上线——需要你自己的 **VPS、域名、微信公众平台配置**。下列步骤在具备这些条件后即可执行。

## 1. GitHub Actions → GHCR

- 推送到 `main`（或手动 **Actions → Docker publish → Run workflow**）会构建 `server/Dockerfile`（**context = 仓库根目录**，以便复制 `organize_vault.py` / `skills/` 等），并推送：
  - `ghcr.io/1019666077-bit/hermes-obsidian:latest`
  - `ghcr.io/1019666077-bit/hermes-obsidian:<短 sha>`
- Workflow 使用 `packages: write` + 默认 `GITHUB_TOKEN`，无需额外密钥。

### 将 Package 设为公开（推荐，便于 VPS 匿名拉取）

1. 打开仓库 → **Packages** → `hermes-obsidian`（或 https://github.com/users/1019666077-bit/packages ）
2. **Package settings** → **Change visibility** → **Public**

若保持私有，VPS 上需登录：

```bash
# 创建有 read:packages 的 PAT，再：
echo YOUR_PAT | docker login ghcr.io -u 1019666077-bit --password-stdin
```

## 2. VPS 部署

### 准备

1. 一台可访问公网的 Linux VPS，开放 **80 / 443**（防火墙与云安全组）。
2. 域名 **A 记录** 指向该 VPS IP（例如 `api.example.com`）。
3. 安装 Docker + Compose 插件。

### 拉取并启动 API

```bash
git clone https://github.com/1019666077-bit/hermes-obsidian.git
cd hermes-obsidian
cp .env.example .env
# 编辑 .env：填写 WECHAT_APPID / WECHAT_SECRET 等（勿提交 git）

docker compose -f deploy/docker-compose.prod.yml pull
docker compose -f deploy/docker-compose.prod.yml up -d
```

默认 API 仅在 Compose 网络内暴露 `8787`，由 Caddy 反代；调试时可在 `deploy/docker-compose.prod.yml` 中临时取消 `ports: "8787:8787"` 注释。

### HTTPS（Caddy）

1. 将 `deploy/Caddyfile.example` 中的 `{$DOMAIN}` 设为你的域名（环境变量或改写文件）。
2. 取消 `deploy/docker-compose.prod.yml` 中 **caddy** 服务注释，设置 `DOMAIN=api.example.com`，再 `up -d`。
3. Caddy 会自动申请 Let's Encrypt 证书（需 80/443 可达且 DNS 已生效）。

也可在宿主机单独跑 Caddy / Nginx，反代到 `127.0.0.1:8787`（此时需给 api 映射宿主机端口）。

## 3. 微信公众平台：合法域名清单

在 [微信公众平台](https://mp.weixin.qq.com/) → **开发 → 开发管理 → 开发设置 → 服务器域名** 配置（均须 **HTTPS**，无端口号）：

| 类型 | 示例 |
|------|------|
| request 合法域名 | `https://api.example.com` |
| uploadFile 合法域名 | `https://api.example.com` |
| downloadFile 合法域名 | `https://api.example.com` |

小程序代码中的 API 基址改为该域名。开发者工具本地调试仍可用 `http://127.0.0.1:8787` 并关闭域名校验。

另请确认：

- [ ] 已填写真实 `WECHAT_APPID` / `WECHAT_SECRET`（与小程序一致）
- [ ] 域名已备案（若服务器在中国大陆）
- [ ] 证书有效、健康检查 `https://你的域名/health` 返回 ok

## 4. 验证

```bash
curl -s https://你的域名/health
curl -s -X POST https://你的域名/api/login \
  -H 'Content-Type: application/json' -d '{"code":"test"}'
```

真机预览前用微信开发者工具勾选合法域名校验。

## 5. 相关文件

| 路径 | 用途 |
|------|------|
| `.github/workflows/docker-publish.yml` | 推 main 时构建并推送 GHCR |
| `deploy/docker-compose.prod.yml` | 生产拉取镜像 + 可选 Caddy |
| `deploy/Caddyfile.example` | HTTPS 反代到 `api:8787` |
| `.env.example` | 环境变量模板（复制为 `.env`，勿提交密钥） |

## 6. 我们做不到的部分

没有你的 VPS SSH、域名账号和微信后台权限时，无法代为完成：DNS、证书、防火墙、公众平台域名白名单、真机验收。按上文自备环境后，最短路径通常是：

```bash
# 在已 clone 且写好 .env、并设置 DOMAIN 后：
docker compose -f deploy/docker-compose.prod.yml pull && \
docker compose -f deploy/docker-compose.prod.yml up -d
```

然后把小程序 API 地址改为 `https://你的域名`，并在公众平台勾选上述合法域名。
