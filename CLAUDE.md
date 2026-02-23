# Synod Project Instructions

## Quick Commands
- `/synod [mode] <prompt>` - Multi-agent deliberation
- Modes: review, design, debug, idea, general

## When Editing This Project
- Skills are in `skills/` directory
- Tools are in `tools/` directory  
- For detailed architecture, read `AGENTS.md`

## Key Patterns
- Use SID format for confidence scoring
- Trust Score formula: T = min((C×R×I)/S, 2.0)
