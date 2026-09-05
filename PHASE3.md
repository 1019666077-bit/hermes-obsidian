# Phase 3：微信小程序壳 + 整理 API

将杂乱笔记上传 → 后端整理成 Obsidian vault → 下载 zip。本阶段为可本地跑通的脚手架；整理引擎默认使用离线脚本 `organize_vault.py`（后续可换 Hermes）。

## 1. 启动 API

```bash
cd /workspace/hermes-obsidian/server
./start.sh
```

浏览器或 curl 访问：`http://127.0.0.1:8787/health`，应返回 `{"status":"ok",...}`。

更多接口与示例见 `server/README.md`。

## 2. 打开微信小程序

1. 安装并打开 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 选择「导入项目」或「小程序」
3. 目录选：`/workspace/hermes-obsidian/miniprogram/`
4. AppID 可用测试号 / 游客 `touristappid`（`project.config.json` 已占位）
5. 详情 → 本地设置：勾选「不校验合法域名…」（仅开发）
6. 确保本机 API 已在 `:8787` 运行，小程序配置见 `utils/config.js`（`baseUrl: http://127.0.0.1:8787`）

流程：首页「开始整理」→ 选择 zip/文件 → 上传整理 → 下载 vault zip。

## 3. 限制（重要）

| 环境 | 说明 |
|------|------|
| 开发者工具 | 可用本地 `http://127.0.0.1`（需关闭域名校验） |
| 真机预览 / 正式版 | **必须** HTTPS + 微信后台配置的合法 request/upload/download 域名 |
| 本阶段 | 无登录、无配额；任务存在进程内存，重启后 `job_id` 失效 |

生产部署需要：云主机或云函数 + HTTPS 证书 + 域名备案/微信校验文件。

## 4. 下一步

> **Phase 4 已完成**：Hermes 优先 + 免费配额桩，详见 [`PHASE4.md`](./PHASE4.md)。

- ~~用 Hermes 替换离线脚本 / 用量配额~~ → 见 Phase 4
- 用户登录（微信 `code` 换 session），配额绑定 openid
- 任务持久化（Redis/DB）、进度推送、更大文件与异步队列
- 正式 AppID、隐私协议与合规说明

## 5. 目录速查

```
hermes-obsidian/
  server/           # FastAPI：/health, /api/organize, /api/download/{job_id}
  miniprogram/      # 微信小程序项目
  organize_vault.py # 演示用离线整理器
  fixtures/         # 样例杂乱笔记
  PHASE3.md         # 本文档
```
