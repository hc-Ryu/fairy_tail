# Synod v1.0 - Quick Reference

**Project:** Multi-agent deliberation system for Claude Code

## Commands
- `/synod [mode] <prompt>` - 다중 에이전트 숙의
- `/cancel-synod` - 세션 취소

## Modes
| Mode | Gemini | OpenAI | Rounds |
|------|--------|--------|--------|
| review | flash | o3 | 3 |
| design | pro | o3 | 4 |
| debug | flash | o3 | 3 |
| idea | pro | gpt4o | 4 |
| general | flash | gpt4o | 3 |

## Key Files
- Skills: `skills/synod.md`, `skills/cancel-synod.md`
- Tools: `tools/gemini-3.py`, `tools/openai-cli.py`
- Sessions: `~/.synod/sessions/`

## Detailed Documentation
- Architecture: `docs/ARCHITECTURE.md`
- Algorithms: `docs/ALGORITHMS.md`
- API Reference: `docs/API.md`

---
*Full documentation: See `docs/` directory*
