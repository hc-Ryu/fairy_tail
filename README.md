# Synod v3.0

Multi-agent deliberation system for Claude Code - structured debate between Claude, Gemini, and OpenAI for better decision-making.

## Features

- **3-round structured debate**: Solver → Critic → Defense/Prosecution
- **SID (Self-Signals Driven) confidence scoring**: 0-100 scale with semantic focus
- **CortexDebate Trust Score calculation**: Confidence × Reasoning × Informativeness / Complexity
- **Anti-conformity instructions**: Prevent premature consensus through Free-MAD methodology
- **Session resume capability**: Continue previous debates seamlessly
- **5 specialized modes**: review, design, debug, idea, general

## Installation

### Prerequisites

- Claude Code CLI (v1.0.0 or later)
- Python 3.9 or higher
- API Keys: GEMINI_API_KEY, OPENAI_API_KEY
- System tools: jq, openssl

### Via Plugin (Recommended)

```bash
/plugin install quantsquirrel/synod
```

### Manual Installation

```bash
git clone https://github.com/quantsquirrel/synod.git
cd synod
pip install -r requirements.txt
cp skills/*.md ~/.claude/commands/
chmod +x tools/*.py
export PATH="$PATH:$(pwd)/tools"
```

## Configuration

### Required Environment Variables

```bash
export GEMINI_API_KEY="your-gemini-key"
export OPENAI_API_KEY="your-openai-key"
```

### Optional

```bash
export SYNOD_SESSION_DIR="~/.synod/sessions"  # Default session storage directory
```

## Usage

### Basic Syntax

```
/synod [mode] <prompt>
```

### Modes

| Mode | Use Case | Models | Rounds |
|------|----------|--------|--------|
| review | Code review and analysis | Gemini Flash + GPT-4o | 3 |
| design | Architecture and system design | Gemini Pro + GPT-4o | 4 |
| debug | Debugging and troubleshooting | Gemini Flash + GPT-4o | 3 |
| idea | Brainstorming and ideation | Gemini Pro + GPT-4o | 4 |
| general | General questions | Gemini Flash + GPT-4o | 3 |

### Examples

```bash
/synod review Analyze the performance of this function

/synod design Design a JWT authentication system

/synod debug Why is this test failing?

/synod idea How can we improve user onboarding?

/synod resume  # Continue previous session

/synod resume <session-id>  # Resume specific session
```

## Theoretical Foundation

Synod is built on state-of-the-art multi-agent debate research:

### Core Methodologies

- **SID (Self-Signals Driven)**: Agents report confidence with semantic focus (primary, secondary, tertiary claims)
- **CortexDebate**: Trust Score formula = min((C×R×I)/S, 2.0) where:
  - C = Confidence (0-100)
  - R = Reasoning quality (0-1)
  - I = Informativeness (0-1)
  - S = System complexity (0-1)

- **Free-MAD (Majority Aversion Debate)**: Anti-conformity instructions force independent analysis
- **ReConcile**: 3-round convergence pattern (Solver → Critic → Defense)
- **ConfMAD**: Soft defer mechanism for low-confidence arguments

## Output Format

Each agent outputs structured XML with confidence scores and semantic focus:

```xml
<confidence score="85">
  <evidence>Specific evidence supporting this position</evidence>
  <logic>Reasoning chain</logic>
  <expertise>Domain expertise applied</expertise>
  <can_exit>true</can_exit>
</confidence>

<semantic_focus>
1. Primary claim
2. Secondary claim
3. Tertiary claim
</semantic_focus>
```

### Interpretation

- **Score 80+**: High confidence, likely consensus-ready
- **Score 60-79**: Moderate confidence, needs refinement
- **Score <60**: Low confidence, requires more analysis
- **can_exit**: Whether agent can recommend discussion closure

## Session Management

Synod stores deliberation sessions in `~/.synod/sessions/` (configurable via SYNOD_SESSION_DIR).

### Session Structure

```
synod-YYYYMMDD-HHMMSS-xxx/
├── meta.json              # Session metadata
├── status.json            # Current session status
├── round-1-solver/        # Solver outputs
│   ├── gemini_response.json
│   └── openai_response.json
├── round-2-critic/        # Critic outputs
│   ├── gemini_response.json
│   └── openai_response.json
└── round-3-defense/       # Defense/Prosecution outputs
    ├── gemini_response.json
    └── openai_response.json
```

### Resuming Sessions

Resume the most recent session:

```bash
/synod resume
```

Resume a specific session by ID:

```bash
/synod resume synod-20260124-143022-a1b
```

## Tools

Synod includes three specialized tools:

| Tool | Purpose |
|------|---------|
| `synod-parser.py` | Parses agent outputs and calculates confidence scores |
| `gemini-3.py` | Google Gemini integration with adaptive thinking |
| `openai-cli.py` | OpenAI integration with reasoning support |

All tools include automatic retry logic and graceful fallback modes.

## Troubleshooting

### API Timeouts

Gemini and OpenAI have 110-second internal timeouts with automatic retry:

- First timeout: Retry with exponential backoff
- Second timeout: Downgrade to adaptive thinking (Gemini) or remove reasoning (OpenAI)
- Third timeout: Use cached response or return error

### Missing Tools

If `synod-parser` is not found:

- Inline fallback parser activates automatically
- Full functionality preserved
- Check: `which synod-parser.py` and `$PATH`

### Configuration Issues

- **Missing API Key**: Verify `echo $GEMINI_API_KEY` and `echo $OPENAI_API_KEY`
- **Session directory permission error**: Ensure `~/.synod/sessions/` is writable
- **Python version mismatch**: Verify `python --version` returns 3.9+

### Common Errors

| Error | Solution |
|-------|----------|
| `API key not found` | Export required API keys (see Configuration section) |
| `No such file or directory: ~/.synod/sessions` | Create directory: `mkdir -p ~/.synod/sessions` |
| `Command not found: /synod` | Install plugin via `/plugin install quantsquirrel/synod` |
| `Timeout after 3 retries` | Check network connection and API service status |

## Advanced Configuration

### Custom Model Selection

Override default models in `.claude/synod-config.json`:

```json
{
  "modes": {
    "review": {
      "solver": "gemini-2.0-flash",
      "critic": "gpt-4o"
    },
    "design": {
      "solver": "gemini-2.0-pro",
      "critic": "gpt-4-turbo"
    }
  }
}
```

### Session Retention

Control how long sessions are retained:

```bash
export SYNOD_RETENTION_DAYS=30  # Delete sessions older than 30 days
```

## Performance Considerations

- **Debate duration**: Typically 2-5 minutes per session
- **Token usage**: ~5,000-15,000 tokens per 3-round debate (varies by prompt length)
- **Parallel execution**: Both agents run simultaneously within rounds
- **Caching**: Recent sessions cached for faster resume

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2026 quantsquirrel

## Contributing

Issues, bug reports, and pull requests welcome!

- **Issues**: https://github.com/quantsquirrel/synod/issues
- **Discussions**: https://github.com/quantsquirrel/synod/discussions
- **Repository**: https://github.com/quantsquirrel/synod

### Development Setup

```bash
git clone https://github.com/quantsquirrel/synod.git
cd synod
pip install -r requirements-dev.txt
pytest tests/
```

## Citation

If you use Synod in research or production, please cite:

```bibtex
@software{synod2026,
  title = {Synod: Multi-Agent Deliberation System for Claude Code},
  author = {quantsquirrel},
  year = {2026},
  url = {https://github.com/quantsquirrel/synod}
}
```

## Acknowledgments

Synod builds on research from:
- CortexDebate (Multi-agent debate with trust scores)
- Free-MAD (Majority aversion in debate)
- SID (Self-signals driven confidence)
- ReConcile (Convergence patterns)

## Support

For questions and support:

- GitHub Discussions: https://github.com/quantsquirrel/synod/discussions
- Report bugs: https://github.com/quantsquirrel/synod/issues
- Email: Open an issue for contact information
