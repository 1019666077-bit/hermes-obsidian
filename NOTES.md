# Hermes Agent — Skills & Config Notes (Phase 1)

Inspected from local clone: `/workspace/hermes-obsidian/hermes-agent` (shallow clone of https://github.com/NousResearch/hermes-agent, MIT).

## Install (pointers)

- One-liner: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
- Windows: `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`
- After install: `hermes` interactive CLI; managed layout typically under `~/.hermes/`
- Dev / local clone: `uv venv` + `uv pip install -e ".[all,dev]"` (see README / README.zh-CN.md)
- Docs: https://hermes-agent.nousresearch.com/docs/getting-started/quickstart

## How skills work

- Each skill is a folder with a **`SKILL.md`** file.
- YAML frontmatter requires at least `name` and `description`; repo standard also uses `version`, `author`, `license`, `platforms`, `metadata.hermes.tags`.
- **Discovery locations:**
  1. **Bundled (in-repo):** `skills/<category>/<skill-name>/SKILL.md`
  2. **Optional (in-repo):** `optional-skills/<category>/<skill-name>/SKILL.md` — install via `hermes skills install official/<category>/<skill>`
  3. **User-local:** `~/.hermes/skills/<maybe-category>/<name>/SKILL.md` — personal; create via agent `skill_manage(action='create')`
- Compatible with [agentskills.io](https://agentskills.io). Browse in CLI: `/skills` or `/<skill-name>`
- Authoring guide: `skills/software-development/hermes-agent-skill-authoring/SKILL.md`
- Existing Obsidian file ops skill: `skills/note-taking/obsidian/SKILL.md` (read/search/create notes; uses `OBSIDIAN_VAULT_PATH`)

## How to add our custom skill

**Recommended for Phase 1 (no Hermes install required yet):**

```bash
# Copy standalone skill into Hermes user skills dir
mkdir -p ~/.hermes/skills/note-taking
cp -R /workspace/hermes-obsidian/skills/obsidian-vault-organize \
      ~/.hermes/skills/note-taking/obsidian-vault-organize
```

Or into the cloned repo (so a local `hermes` run from this tree discovers it):

```bash
cp -R /workspace/hermes-obsidian/skills/obsidian-vault-organize \
      /workspace/hermes-obsidian/hermes-agent/skills/note-taking/obsidian-vault-organize
```

(A copy is already placed under `hermes-agent/skills/note-taking/obsidian-vault-organize/` for convenience.)

Then restart Hermes / open `/skills` and invoke `obsidian-vault-organize`.

## Model config pointers

- CLI: `hermes model` — choose provider + model (no code change)
- In chat: `/model [provider:model]`
- Providers (README): Nous Portal, OpenRouter, NVIDIA NIM, Xiaomi MiMo, z.ai/GLM, Kimi/Moonshot, MiniMax, Hugging Face, OpenAI, custom endpoints
- Config docs: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Skills docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Env: typically `${HERMES_HOME:-~/.hermes}/.env` (e.g. API keys, `OBSIDIAN_VAULT_PATH`)
- Example CLI config: `cli-config.yaml.example` in repo root

## Phase 1 offline path

Until API keys are set, use `/workspace/hermes-obsidian/organize_vault.py` to prove vault layout end-to-end without an LLM.
