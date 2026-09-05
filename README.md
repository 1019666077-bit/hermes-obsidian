# Hermes × Obsidian 笔记整理

微信小程序壳 + 本地整理 API：上传乱笔记 → 整理成 Obsidian Vault → 下载。

## 目录

- `miniprogram/` — 微信小程序（开发者工具导入）
- `server/` — FastAPI 整理服务（默认调用 `organize_vault.py`）
- `skills/obsidian-vault-organize/` — Hermes 技能
- `fixtures/messy-input/` — 样例乱笔记
- `PHASE1.md` / `PHASE2.md` / `PHASE3.md` — 阶段说明

## 快速开始

```bash
# API
cd server && ./start.sh

# 离线整理
python3 organize_vault.py --input fixtures/messy-input --output /tmp/demo-vault
```

Hermes Agent 请自行 clone：https://github.com/NousResearch/hermes-agent  
安装与 DeepSeek 配置见 `PHASE2.md`（**不要把 API Key 提交进仓库**）。

## 微信开发者工具

导入 `miniprogram/`，开发阶段关闭域名校验；API 默认 `http://127.0.0.1:8787`。
