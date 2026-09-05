---
name: obsidian-vault-organize
description: "Organize messy notes into a structured Obsidian vault."
version: 0.1.0
author: Phase1 Demo, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Obsidian, Vault, Organize, Markdown, Chinese]
    related_skills: [obsidian]
---

# Obsidian Vault Organize Skill

Organize a folder of messy notes/files (`.md` / `.txt` / `.csv` excerpts) into a clean Obsidian vault. Do **not** invent facts beyond the given content; only restructure, classify, dedupe, and link.

## When to Use

- "整理这些乱七八糟的笔记成 Obsidian vault"
- "Organize this messy notes folder into Inbox / Topics / Sources / MOC"
- User provides a path of mixed Chinese/English notes to clean up

Don't use for: single-note edits inside an existing vault (use `obsidian` skill instead).

## Target vault structure

```
<vault>/
  README.md
  Home.md
  00-Inbox/          # unclassified or needs review
  01-Topics/         # one note (or subfolder) per topic
  02-Sources/        # source excerpts, CSVs, quotes
  03-MOC/            # Maps of Content (index notes)
  _templates/        # note templates
```

## Rules

1. **Markdown + YAML frontmatter** on every note: `title`, `tags` (list), `created` (ISO date if known, else today's date or source mtime).
2. **Wiki-links:** use `[[Note Title]]` between related notes and from MOCs / Home.
3. **Dedupe:** if two files are near-duplicates (same title/topic, highly overlapping body), keep the richer one; move the other into `00-Inbox/` with a `status: duplicate-candidate` tag and a link to the kept note — or merge only when content clearly complements without inventing text.
4. **Classify by topic:** keyword/heading heuristics OK; put unclear items in `00-Inbox/`.
5. **Language:** write titles, MOC prose, and Home in **Chinese** when the source material is primarily Chinese; otherwise match the source language. Keep original body language.
6. **Never invent fake facts** — only organize, title, tag, and link what is present.
7. Prefer Hermes file tools: `search_files`, `read_file`, `write_file`, `patch`. Resolve vault path to an absolute path first (`OBSIDIAN_VAULT_PATH` or user-given output dir).

## Procedure

### 1. Inventory

List input files with `search_files` (`*.md`, `*.txt`, `*.csv`). Read each. Note language mix, obvious duplicates, and candidate topics. Done when every file is accounted for.

### 2. Plan folders

Ensure the structure above exists under the output vault path. Create `_templates/note.md` with frontmatter scaffold. Done when empty dirs + templates exist.

### 3. Normalize notes

For each input file: extract title (first heading or filename), body, tags; add frontmatter; write to `01-Topics/` or `02-Sources/` (CSV/excerpts → Sources). Unclear → `00-Inbox/`. Done when every input has a corresponding vault note.

### 4. Dedupe pass

Compare titles and opening paragraphs; mark or merge near-duplicates per Rules. Done when no two Topics notes are silent duplicates.

### 5. Build MOCs and Home

Create `03-MOC/` maps per major topic with `[[wikilinks]]`. Write root `Home.md` (导航) and `README.md` (vault purpose + folder legend). Done when Home links to all MOCs and key topics.

### 6. Verify

Re-list vault; spot-check frontmatter and links. Summarize counts for the user.

## Offline fallback

If no LLM/API is available, run the deterministic script shipped with this product demo:

```bash
python3 /workspace/hermes-obsidian/organize_vault.py \
  --input /workspace/hermes-obsidian/fixtures/messy-input \
  --output /workspace/hermes-obsidian/output-vault
```

Hermes should later replace/augment that script with this skill’s judgment while keeping the same folder contract.

## Pitfalls

- Do not overwrite an existing vault without confirming the output path.
- Do not translate or “improve” factual claims — organize only.
- CSV rows are sources, not topics; keep them under `02-Sources/`.

## Verification

- [ ] Folders `00-Inbox/` … `03-MOC/` + `_templates/` exist
- [ ] Every note has YAML `title` / `tags` / `created`
- [ ] `Home.md` and at least one MOC use `[[wikilinks]]`
- [ ] No fabricated facts beyond input content
