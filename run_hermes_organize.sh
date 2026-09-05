#!/usr/bin/env bash
# Phase 2/4: best-effort non-interactive Hermes vault organize.
# Requires a real API key in ~/.hermes/.env (OPENROUTER_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY / …).
#
# Job-specific paths (Phase 4 server):
#   INPUT_DIR              — source notes (default: fixtures/messy-input)
#   OUTPUT_DIR             — alias for output vault
#   OBSIDIAN_VAULT_PATH    — output vault (wins over OUTPUT_DIR if both set)
set -euo pipefail

ROOT="/workspace/hermes-obsidian"
HERMES_DIR="${ROOT}/hermes-agent"
VENV_BIN="${HERMES_DIR}/.venv/bin"
INPUT="${INPUT_DIR:-${ROOT}/fixtures/messy-input}"
# Prefer OBSIDIAN_VAULT_PATH, then OUTPUT_DIR, then default hermes-output-vault
if [[ -n "${OBSIDIAN_VAULT_PATH:-}" ]]; then
  :
elif [[ -n "${OUTPUT_DIR:-}" ]]; then
  OBSIDIAN_VAULT_PATH="${OUTPUT_DIR}"
else
  OBSIDIAN_VAULT_PATH="${ROOT}/hermes-output-vault"
fi
export OBSIDIAN_VAULT_PATH

if [[ ! -x "${VENV_BIN}/hermes" ]]; then
  echo "ERROR: hermes CLI not found at ${VENV_BIN}/hermes" >&2
  echo "Install: cd ${HERMES_DIR} && uv venv .venv && uv pip install -e '.'" >&2
  exit 1
fi

# Prefer venv hermes
# shellcheck disable=SC1091
source "${VENV_BIN}/activate"
HERMES="${VENV_BIN}/hermes"

mkdir -p "${OBSIDIAN_VAULT_PATH}"

# Credential sniff (names only — do not print values)
has_key=0
if [[ -f "${HOME}/.hermes/.env" ]]; then
  if grep -E '^(OPENROUTER_API_KEY|DEEPSEEK_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|NOUS_API_KEY|GLM_API_KEY|KIMI_API_KEY|FIREWORKS_API_KEY)=' \
      "${HOME}/.hermes/.env" 2>/dev/null | grep -qvE '=\s*$|=.*PASTE|=\s*#'; then
    has_key=1
  fi
fi
# Also accept env already exported in the shell
for v in OPENROUTER_API_KEY DEEPSEEK_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY; do
  if [[ -n "${!v:-}" ]]; then has_key=1; fi
done

if [[ "${has_key}" -eq 0 ]]; then
  echo "No model API key detected in ~/.hermes/.env or environment."
  echo "Documented next step: edit ~/.hermes/.env and paste a key, e.g."
  echo "  OPENROUTER_API_KEY=sk-or-v1-..."
  echo "  # or DEEPSEEK_API_KEY=sk-..."
  echo ""
  echo "Fallback (no LLM):"
  echo "  python3 ${ROOT}/organize_vault.py --input ${INPUT} --output ${OBSIDIAN_VAULT_PATH}"
  exit 2
fi

PROMPT=$(cat <<PROMPT_EOF
请使用已预加载的技能 obsidian-vault-organize，把输入目录整理成 Obsidian vault。

输入目录（只读源）: ${INPUT}
输出 vault（必须写入这里）: ${OBSIDIAN_VAULT_PATH}
环境变量 OBSIDIAN_VAULT_PATH 已设为上述输出路径。

严格遵循技能规则：Inbox / Topics / Sources / MOC / templates；YAML frontmatter；wikilinks；不编造事实。
完成后简要汇总各类笔记数量与主要路径。
PROMPT_EOF
)

echo "INPUT_DIR=${INPUT}"
echo "OBSIDIAN_VAULT_PATH=${OBSIDIAN_VAULT_PATH}"
echo "Running: hermes chat -Q --oneshot --yolo -s obsidian-vault-organize ..."
echo "(Batch mode: chat -q/--query-file + --oneshot + -Q; see hermes chat --help)"

# Optional provider/model overrides via env:
#   HERMES_PROVIDER=deepseek HERMES_MODEL=deepseek-chat ./run_hermes_organize.sh
EXTRA=()
if [[ -n "${HERMES_PROVIDER:-}" ]]; then EXTRA+=(--provider "${HERMES_PROVIDER}"); fi
if [[ -n "${HERMES_MODEL:-}" ]]; then EXTRA+=(-m "${HERMES_MODEL}"); fi

# Soft time budget for long agent runs (server also wraps with its own timeout)
export HERMES_RUN_BUDGET="${HERMES_RUN_BUDGET:-240}"

exec "${HERMES}" chat -Q --oneshot --yolo \
  -s obsidian-vault-organize \
  --run-budget "${HERMES_RUN_BUDGET}" \
  "${EXTRA[@]}" \
  -q "${PROMPT}"
