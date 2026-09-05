# obsidian-vault-organize

Custom Hermes skill: turn a messy folder of notes into a clean Obsidian vault.

## Install into Hermes

```bash
# User-local (recommended)
mkdir -p ~/.hermes/skills/note-taking
cp -R "$(dirname "$0")" ~/.hermes/skills/note-taking/obsidian-vault-organize

# Or into a hermes-agent checkout
cp -R "$(dirname "$0")" \
  /path/to/hermes-agent/skills/note-taking/obsidian-vault-organize
```

Then in Hermes: `/skills` → load `obsidian-vault-organize`, or ask to organize a vault.

## Offline demo (no API)

```bash
cd /workspace/hermes-obsidian
python3 organize_vault.py
# → writes output-vault/
```

See `SKILL.md` for procedure rules; see `../../PHASE1.md` for the full demo walkthrough.
