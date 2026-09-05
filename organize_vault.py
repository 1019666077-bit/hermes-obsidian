#!/usr/bin/env python3
"""Deterministic Phase-1 Obsidian vault organizer (no LLM / no API).

Reads messy notes from fixtures (or --input) and writes a clean vault under
--output following the Phase-1 folder contract.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

TODAY = date.today().isoformat()

TOPIC_RULES: list[tuple[str, list[str], str]] = [
    # (topic_slug, keywords_lower, display_title)
    (
        "product-vision",
        ["产品", "product", "phase1", "phase 1", "目标用户", "founder", "vault"],
        "产品愿景 Product Vision",
    ),
    (
        "hermes-agent",
        ["hermes", "nous", "skill.md", "openrouter", "hermes model"],
        "Hermes Agent",
    ),
    (
        "obsidian-workflow",
        ["obsidian", "wikilink", "frontmatter", "00-inbox", "moc"],
        "Obsidian 工作流",
    ),
    (
        "meetings",
        ["周会", "meeting", "参会", "todo:"],
        "会议纪要 Meetings",
    ),
    (
        "wechat-mp",
        ["微信", "小程序", "wechat", "mp"],
        "微信小程序（后续）",
    ),
]

INBOX_HINTS = ["untitled", "随机", "咖啡", "不确定"]


@dataclass
class Note:
    source_path: Path
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    dest_rel: str = ""
    lang: str = "mixed"
    content_hash: str = ""
    is_duplicate: bool = False
    duplicate_of: str = ""


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:80] or "note"


def detect_lang(text: str) -> str:
    zh = len(re.findall(r"[\u4e00-\u9fff]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    if zh > en * 1.2:
        return "zh"
    if en > zh * 1.2:
        return "en"
    return "mixed"


def extract_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    stem = path.stem
    if stem.lower() in {"untitled", "note", "notes"} or "untitled" in stem.lower():
        return f"未命名备忘 ({stem})"
    return stem.replace("-", " ").replace("_", " ")


def normalize_for_hash(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[#*_>`\[\]()!,.!！？?，。；;：:\"']+", "", t)
    return t.strip()


def similarity(a: str, b: str) -> float:
    """Token Jaccard similarity — deterministic, no deps."""
    ta = set(re.findall(r"[\w\u4e00-\u9fff]+", a.lower()))
    tb = set(re.findall(r"[\w\u4e00-\u9fff]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# Cross-language concept markers: if both notes hit the same concept bucket, treat as related.
CONCEPT_GROUPS: list[set[str]] = [
    {"messy", "notes", "obsidian", "vault", "零散", "笔记", "整理", "干净"},
    {"chinese", "founder", "中文", "创始人", "知识工作者", "knowledge", "workers"},
    {"invent", "facts", "organize", "编造", "事实", "整理"},
    {"mixed", "english", "chinese", "英文", "中文"},
]


def concept_fingerprint(text: str) -> frozenset[int]:
    lower = text.lower()
    hits = set()
    for i, group in enumerate(CONCEPT_GROUPS):
        if any(tok in lower for tok in group):
            hits.add(i)
    return frozenset(hits)


def near_duplicate(a: Note, b: Note) -> bool:
    sim = similarity(a.body, b.body)
    title_sim = similarity(a.title, b.title)
    if sim >= 0.55 or (title_sim >= 0.5 and sim >= 0.35):
        return True
    # Same topic folder + overlapping bilingual concepts
    fa, fb = concept_fingerprint(a.body + a.title), concept_fingerprint(b.body + b.title)
    same_topic = False
    if a.dest_rel.startswith("01-Topics/") and b.dest_rel.startswith("01-Topics/"):
        same_topic = Path(a.dest_rel).parts[1] == Path(b.dest_rel).parts[1]
    if same_topic and len(fa & fb) >= 2:
        return True
    return False


def classify(path: Path, text: str) -> tuple[str, list[str]]:
    """Return (bucket, tags) where bucket is topics|sources|inbox and tags include topic slug."""
    lower = text.lower()
    name_lower = path.name.lower()

    if path.suffix.lower() == ".csv":
        return "sources", ["source", "csv"]

    for hint in INBOX_HINTS:
        if hint in lower or hint in name_lower:
            return "inbox", ["inbox", "needs-review"]

    best_slug = None
    best_hits = 0
    for slug, kws, _title in TOPIC_RULES:
        hits = sum(1 for k in kws if k.lower() in lower or k.lower() in name_lower)
        if hits > best_hits:
            best_hits = hits
            best_slug = slug

    if best_slug and best_hits > 0:
        return "topics", ["topic", best_slug]

    return "inbox", ["inbox", "unclassified"]


def topic_display(slug: str) -> str:
    for s, _k, title in TOPIC_RULES:
        if s == slug:
            return title
    return slug


def frontmatter(title: str, tags: list[str], created: str) -> str:
    tag_line = "[" + ", ".join(tags) + "]"
    return (
        "---\n"
        f"title: \"{title}\"\n"
        f"tags: {tag_line}\n"
        f"created: {created}\n"
        "---\n\n"
    )


def strip_existing_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def csv_to_markdown(path: Path) -> tuple[str, str]:
    """Convert CSV excerpt to a Sources markdown note; preserve rows as table."""
    text = read_text_file(path)
    rows = list(csv.reader(text.splitlines()))
    title = f"来源摘录 {path.stem}"
    lines = [f"# {title}", "", f"Source file: `{path.name}`", ""]
    if not rows:
        lines.append("_(empty CSV)_")
        return title, "\n".join(lines) + "\n"
    header, *body = rows
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for r in body:
        # pad/truncate to header width
        cells = list(r) + [""] * max(0, len(header) - len(r))
        lines.append("| " + " | ".join(cells[: len(header)]) + " |")
    lines.append("")
    lines.append("原始内容未改写，仅表格化以便 Obsidian 阅读。")
    return title, "\n".join(lines) + "\n"


def load_notes(input_dir: Path) -> list[Note]:
    notes: list[Note] = []
    patterns = ("*.md", "*.txt", "*.csv")
    files: list[Path] = []
    for pat in patterns:
        files.extend(sorted(input_dir.glob(pat)))
    files = sorted(set(files), key=lambda p: p.name)

    for path in files:
        if path.suffix.lower() == ".csv":
            title, body = csv_to_markdown(path)
            tags = ["source", "csv"]
            bucket = "sources"
        else:
            raw = read_text_file(path)
            body = strip_existing_frontmatter(raw).strip() + "\n"
            title = extract_title(path, raw)
            bucket, tags = classify(path, raw)
            # keep a leading heading if missing
            if not re.match(r"^#\s", body):
                body = f"# {title}\n\n{body}"

        lang = detect_lang(title + "\n" + body)
        h = hashlib.sha256(normalize_for_hash(body).encode()).hexdigest()[:16]
        note = Note(
            source_path=path,
            title=title,
            body=body,
            tags=tags,
            lang=lang,
            content_hash=h,
        )
        safe = slugify(title)
        if bucket == "topics":
            topic = next((t for t in tags if t not in {"topic", "inbox", "source", "csv", "needs-review", "unclassified"}), "general")
            note.dest_rel = f"01-Topics/{topic}/{safe}.md"
            if "topic" not in note.tags:
                note.tags.insert(0, "topic")
        elif bucket == "sources":
            note.dest_rel = f"02-Sources/{safe}.md"
        else:
            note.dest_rel = f"00-Inbox/{safe}.md"
        notes.append(note)
    return notes


def dedupe(notes: list[Note]) -> list[Note]:
    """Mark near-duplicates: keep richer body, send other to Inbox as duplicate-candidate."""
    kept: list[Note] = []
    for note in notes:
        if note.dest_rel.startswith("02-Sources/"):
            kept.append(note)
            continue
        dup_of = None
        for prev in kept:
            if prev.is_duplicate:
                continue
            if near_duplicate(note, prev):
                # keep the longer body
                if len(note.body) > len(prev.body):
                    # demote prev
                    prev.is_duplicate = True
                    prev.duplicate_of = note.title
                    prev.tags = list(dict.fromkeys(prev.tags + ["duplicate-candidate"]))
                    prev.dest_rel = f"00-Inbox/{slugify(prev.title)}-dup.md"
                    prev.body = (
                        f"# {prev.title}\n\n"
                        f"> 近重复候选；保留版见 [[{note.title}]]。\n\n"
                        + strip_existing_frontmatter(prev.body)
                    )
                    dup_of = None
                    break
                else:
                    dup_of = prev
                    break
        if dup_of is not None:
            note.is_duplicate = True
            note.duplicate_of = dup_of.title
            note.tags = list(dict.fromkeys(note.tags + ["duplicate-candidate"]))
            note.dest_rel = f"00-Inbox/{slugify(note.title)}-dup.md"
            note.body = (
                f"# {note.title}\n\n"
                f"> 近重复候选；保留版见 [[{dup_of.title}]]。\n\n"
                + strip_existing_frontmatter(note.body)
            )
        kept.append(note)
    return kept


def write_note(vault: Path, note: Note) -> Path:
    path = vault / note.dest_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = strip_existing_frontmatter(note.body).lstrip()
    content = frontmatter(note.title, note.tags, TODAY) + body
    if not content.endswith("\n"):
        content += "\n"
    # provenance footer
    content += f"\n---\n\n_Source: `{note.source_path.name}`_\n"
    path.write_text(content, encoding="utf-8")
    return path


def build_mocs(vault: Path, notes: list[Note]) -> list[str]:
    """Create one MOC per topic folder; return list of MOC titles."""
    moc_dir = vault / "03-MOC"
    moc_dir.mkdir(parents=True, exist_ok=True)
    by_topic: dict[str, list[Note]] = {}
    for n in notes:
        if n.is_duplicate:
            continue
        if n.dest_rel.startswith("01-Topics/"):
            parts = Path(n.dest_rel).parts
            topic = parts[1] if len(parts) > 2 else "general"
            by_topic.setdefault(topic, []).append(n)

    moc_titles: list[str] = []
    for topic, tnotes in sorted(by_topic.items()):
        display = topic_display(topic)
        moc_title = f"MOC · {display}"
        moc_titles.append(moc_title)
        links = "\n".join(f"- [[{n.title}]]" for n in tnotes)
        body = (
            f"# {moc_title}\n\n"
            f"本图汇总主题 **{display}** 下的笔记（仅来自输入整理，无新增事实）。\n\n"
            f"## 笔记\n\n{links}\n"
        )
        path = moc_dir / f"MOC-{slugify(topic)}.md"
        path.write_text(frontmatter(moc_title, ["moc", topic], TODAY) + body, encoding="utf-8")

    # Sources MOC
    sources = [n for n in notes if n.dest_rel.startswith("02-Sources/")]
    if sources:
        moc_title = "MOC · Sources 来源"
        moc_titles.append(moc_title)
        links = "\n".join(f"- [[{n.title}]]" for n in sources)
        body = f"# {moc_title}\n\n## 来源笔记\n\n{links}\n"
        (moc_dir / "MOC-sources.md").write_text(
            frontmatter(moc_title, ["moc", "sources"], TODAY) + body, encoding="utf-8"
        )
    return moc_titles


def write_home_and_readme(vault: Path, notes: list[Note], moc_titles: list[str]) -> None:
    inbox = [n for n in notes if n.dest_rel.startswith("00-Inbox/")]
    topics = [n for n in notes if n.dest_rel.startswith("01-Topics/") and not n.is_duplicate]
    sources = [n for n in notes if n.dest_rel.startswith("02-Sources/")]

    moc_links = "\n".join(f"- [[{t}]]" for t in moc_titles) or "- _(none)_"
    topic_links = "\n".join(f"- [[{n.title}]]" for n in topics) or "- _(none)_"
    inbox_links = "\n".join(f"- [[{n.title}]]" for n in inbox) or "- _(empty)_"
    source_links = "\n".join(f"- [[{n.title}]]" for n in sources) or "- _(none)_"

    home = (
        frontmatter("Home", ["home", "nav"], TODAY)
        + "# Home\n\n"
        + "本库由 Phase-1 离线整理脚本生成。导航如下：\n\n"
        + "## Maps of Content\n\n"
        + moc_links
        + "\n\n## Topics\n\n"
        + topic_links
        + "\n\n## Sources\n\n"
        + source_links
        + "\n\n## Inbox（待审）\n\n"
        + inbox_links
        + "\n"
    )
    (vault / "Home.md").write_text(home, encoding="utf-8")

    readme = (
        frontmatter("README", ["meta"], TODAY)
        + "# Vault README\n\n"
        + "结构化 Obsidian vault（Phase-1 demo）。\n\n"
        + "## 目录说明\n\n"
        + "- `00-Inbox/` — 未分类 / 近重复候选 / 需人工审阅\n"
        + "- `01-Topics/` — 按主题分类的笔记\n"
        + "- `02-Sources/` — 来源摘录（含 CSV）\n"
        + "- `03-MOC/` — Maps of Content\n"
        + "- `_templates/` — 模板\n"
        + "- [[Home]] — 导航首页\n\n"
        + "规则：Markdown + YAML frontmatter；wiki-links `[[...]]`；"
        + "不编造输入之外的事实；中文源材料保持中文导航。\n"
    )
    (vault / "README.md").write_text(readme, encoding="utf-8")


def write_template(vault: Path) -> None:
    tdir = vault / "_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    tpl = (
        "---\n"
        'title: "{{title}}"\n'
        "tags: []\n"
        f"created: {TODAY}\n"
        "---\n\n"
        "# {{title}}\n\n"
    )
    (tdir / "note.md").write_text(tpl, encoding="utf-8")


def organize(input_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    notes = load_notes(input_dir)
    notes = dedupe(notes)

    written: list[Path] = []
    for n in notes:
        written.append(write_note(output_dir, n))

    moc_titles = build_mocs(output_dir, notes)
    write_home_and_readme(output_dir, notes, moc_titles)
    write_template(output_dir)

    summary = {
        "input_files": len(notes),
        "written_notes": len(written),
        "inbox": sum(1 for n in notes if n.dest_rel.startswith("00-Inbox/")),
        "topics": sum(1 for n in notes if n.dest_rel.startswith("01-Topics/") and not n.is_duplicate),
        "sources": sum(1 for n in notes if n.dest_rel.startswith("02-Sources/")),
        "duplicates_flagged": sum(1 for n in notes if n.is_duplicate),
        "mocs": len(moc_titles),
        "output": str(output_dir),
    }
    return summary


def main() -> None:
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Phase-1 deterministic Obsidian vault organizer")
    ap.add_argument("--input", type=Path, default=root / "fixtures" / "messy-input")
    ap.add_argument("--output", type=Path, default=root / "output-vault")
    args = ap.parse_args()

    if not args.input.is_dir():
        raise SystemExit(f"Input dir not found: {args.input}")

    summary = organize(args.input, args.output)
    print("=== organize_vault.py summary ===")
    print(f"Input files processed : {summary['input_files']}")
    print(f"Notes written         : {summary['written_notes']}")
    print(f"  00-Inbox/           : {summary['inbox']}")
    print(f"  01-Topics/          : {summary['topics']}")
    print(f"  02-Sources/         : {summary['sources']}")
    print(f"Duplicates flagged    : {summary['duplicates_flagged']}")
    print(f"MOCs created          : {summary['mocs']}")
    print(f"Output vault          : {summary['output']}")
    print("Also wrote: README.md, Home.md, _templates/note.md")


if __name__ == "__main__":
    main()
