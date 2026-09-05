# Phase 1 演示说明（Hermes × Obsidian 笔记整理）

面向中文创始人的 Phase-1 可运行 demo：**不依赖付费 API**，用确定性脚本证明「脏笔记 → 干净 Obsidian vault」端到端格式。

## 目录一览

| 路径 | 作用 |
|------|------|
| `hermes-agent/` | 已 shallow-clone 的 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)（MIT） |
| `skills/obsidian-vault-organize/` | 自定义技能（`SKILL.md` + 安装说明 README） |
| `hermes-agent/skills/note-taking/obsidian-vault-organize/` | 同上技能的副本，便于本地 Hermes 发现 |
| `fixtures/messy-input/` | 5–8 个中英混杂、故意凌乱的样例笔记 |
| `organize_vault.py` | **离线**整理脚本（无需 LLM） |
| `output-vault/` | 脚本已跑通后的示例 vault |
| `NOTES.md` | Hermes 技能机制 / 安装 / 模型配置摘记 |
| `PHASE1.md` | 本文件 |

## 如何跑通 Demo（推荐路径）

在 box 上（或任意已装 Python 3 的环境）：

```bash
cd /workspace/hermes-obsidian
python3 organize_vault.py
# 等价于：
# python3 organize_vault.py \
#   --input  /workspace/hermes-obsidian/fixtures/messy-input \
#   --output /workspace/hermes-obsidian/output-vault
```

脚本会：

1. 读取 `fixtures/messy-input/` 下的 `.md` / `.txt` / `.csv`
2. 按规则分类到 `00-Inbox/`、`01-Topics/`、`02-Sources/`
3. 为笔记写入 YAML frontmatter（`title` / `tags` / `created`）
4. 近重复检测（含跨中英概念指纹），候选放入 Inbox 并 `[[wikilink]]` 指向保留版
5. 生成 `03-MOC/`、`_templates/note.md`、根目录 `Home.md` / `README.md`
6. 在终端打印简短汇总

用 Obsidian「Open folder as vault」打开 `output-vault/` 即可预览。

## Hermes 之后如何替代 / 增强脚本

| 现在（Phase 1） | 之后（接上 Hermes + API） |
|-----------------|---------------------------|
| `organize_vault.py` 关键词 / 规则分类 | 加载技能 `obsidian-vault-organize`，由模型理解主题与去重 |
| 固定概念指纹做跨语言近似去重 | LLM 语义去重 + 合并互补段落（仍禁止编造事实） |
| 模板化 MOC / Home | 更自然的中文导航文案与交叉链接 |
| 本地路径写死在 demo | 使用 `OBSIDIAN_VAULT_PATH` + Hermes `write_file` / `read_file` |

安装技能到用户目录：

```bash
mkdir -p ~/.hermes/skills/note-taking
cp -R /workspace/hermes-obsidian/skills/obsidian-vault-organize \
      ~/.hermes/skills/note-taking/obsidian-vault-organize
```

然后：`hermes` → `hermes model` 选模型 → `/skills` 启用 `obsidian-vault-organize`，对某输入目录说「整理成 Obsidian vault」。细节见 `NOTES.md`。

脚本可保留为：**无 Key 时的 CI / 回归基线**，或 Hermes 失败时的 fallback。

## 下一步还需要什么

1. **API Key / 模型**  
   - 任选：Nous Portal、OpenRouter、OpenAI、GLM、Kimi、MiMo 等（见 Hermes README）  
   - 配置：`hermes model` 或 `~/.hermes/.env`  
   - **本 Phase 故意不花钱、不调在线 API**

2. **Hermes 本机安装（可选）**  
   - `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`  
   - 或对已 clone 的 `hermes-agent/` 做 `uv pip install -e ".[all,dev]"`

3. **微信小程序（明确不在 Phase 1）**  
   - 后续：上传笔记包 → 调用整理服务 → 下载 vault zip  
   - 需要：微信 MP 账号、后端鉴权、存储与配额  
   - 产品契约可先锁定为与本 demo 相同的 vault 目录结构

4. **产品打磨**  
   - 更稳的去重 / 主题 taxonomy  
   - 与现有 `obsidian` 技能协作（读写已有库 vs 从零生成）  
   - 一键 zip 导出给小程序下载

## 成功标准对照

- [x] hermes-agent 已 clone  
- [x] 技能 + fixtures + `organize_vault.py` + 已生成 `output-vault` + `PHASE1.md`  
- [x] 离线可演示，无需 LLM  

有问题先看 `NOTES.md`；技能规则以 `skills/obsidian-vault-organize/SKILL.md` 为准。
