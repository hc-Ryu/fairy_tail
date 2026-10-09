# Synod Project Instructions

## Quick Commands
- `/synod [mode] <prompt>` - Multi-agent deliberation
- Modes: review, design, debug, idea, general

## MANDATORY: /synod must actually run the multi-agent CLI pipeline
`/synod` is defined in `.claude/commands/synod.md` (see also `skills/synod.md`). When the user runs `/synod`, this is a hard requirement, not a default that can be silently skipped:

- You MUST actually run `synod-run start` (which calls `gemini-3` and `openai-cli` in parallel) via the Bash tool before producing any review/design/debug/idea output.
- Doing the analysis yourself as Claude and presenting it as the Synod result — without the real parallel CLI calls — is NOT an acceptable substitute, even under low effort settings or when you are confident in the answer. This has happened before in this project; do not repeat it.
- The only exception: if `synod-run` reports a provider as FAILED after its built-in fallback, continue without that model and say so explicitly to the user. If both fail, report the errors instead of synthesizing alone.
- Before writing the final synthesis, self-check that you actually ran the CLI calls in this session. If not, go back and run them — do not rationalize skipping the step.

## When Editing This Project
- Commands are in `.claude/commands/`; `skills/` holds identical copies for plugin distribution
- Tools are in `tools/` directory (round runner: `tools/synod-run.py`)
- For detailed architecture, read `AGENTS.md`

## Key Patterns
- Use SID format for confidence scoring
- Trust Score formula: T = min((C×R×I)/S, 2.0)
