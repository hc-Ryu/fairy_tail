# Synod v2 - Quick Reference

**Project:** Multi-agent deliberation system for Claude Code (Claude + Gemini + OpenAI)

## Commands
- `/synod [mode] <prompt>` - 다중 에이전트 숙의 (`.claude/commands/synod.md`, 배포용 사본 `skills/synod.md`)
- `/cancel-synod` - 세션 취소

## Modes (defaults in `tools/synod-run.py` → `MODES`)
| Mode | Gemini | OpenAI | Max rounds |
|------|--------|--------|------------|
| review | flash (3.8) / high | sol / medium | 3 |
| design | flash / high | sol / high | 3 |
| debug | flash / high | sol / high | 3 |
| idea | flash / high | luna / medium | 3 |
| general | flash / medium | luna / low | 2 |

Rounds are adaptive: early exit after solver, defense round only when the critics raise a substantive objection.

## Key Files
- `tools/synod-run.py` - round runner (parallel calls, SID parsing, fallback, session state)
- `tools/gemini-3.py`, `tools/openai-cli.py` - provider CLIs (`bin/*.bat` wrappers)
- `tools/synod-parser.py` - SID signal parser / Trust Score
- Optional providers: `tools/{deepseek,groq,grok,mistral,claude}-cli.py` (not used by default)
- Sessions: `.omc/synod/<session-id>/`
- Tests: `py -m pytest -o addopts="" tests`

## Editing rules
- Keep `.claude/commands/*.md` and `skills/*.md` identical (copy after editing).
- Model IDs: verify with the provider's model list before changing `MODEL_MAP`.
