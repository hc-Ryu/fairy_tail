#!/usr/bin/env python3
"""
Synod round runner - executes external model rounds so the orchestrator
(Claude) only needs one Bash call per round.

Usage:
  synod-run start   --mode MODE --problem-file P --claude-file C
  synod-run critic  --context-file CTX [--session ID]
  synod-run defense --context-file CTX [--session ID]
  synod-run finish  --synthesis-file S --confidence N [--session ID]
  synod-run status  [--session ID]
  synod-run cancel  [--session ID]

Sessions live in ./.omc/synod/<session-id>/ (relative to the current directory).
"""

import argparse
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TOOLS_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = Path(".omc") / "synod"

# Mode -> model configuration. Gemini 3.8 Flash outscores 3.1 Pro Preview, so flash is used everywhere.
MODES = {
    "review": {"gemini": ("flash", "high"), "openai": ("sol", "medium"), "max_rounds": 3},
    "design": {"gemini": ("flash", "high"), "openai": ("sol", "high"), "max_rounds": 3},
    "debug": {"gemini": ("flash", "high"), "openai": ("sol", "high"), "max_rounds": 3},
    "idea": {"gemini": ("flash", "high"), "openai": ("luna", "medium"), "max_rounds": 3},
    "general": {"gemini": ("flash", "medium"), "openai": ("luna", "low"), "max_rounds": 2},
}

FOCUS = {
    "review": ("architecture, code organization, maintainability",
               "edge cases, error handling, security"),
    "design": ("scalability, patterns, trade-offs", "failure modes, alternatives, constraints"),
    "debug": ("system-level causes, pattern recognition", "counter-hypotheses, edge cases"),
    "idea": ("creative exploration, novel approaches", "risks, feasibility, practical fit"),
    "general": ("broad coverage, connections", "alternative perspectives, nuances"),
}

# Per-call wall-clock budget (seconds) by reasoning level; CLIs downgrade internally on timeout.
TIMEOUTS = {"low": 120, "medium": 240, "high": 420}

# One fallback per provider when the primary call fails.
FALLBACK = {"gemini": ("flash", "low"), "openai": ("luna", "medium")}

SID_BLOCKS = """End your answer with exactly these two XML blocks:

<confidence score="[0-100]">
  <evidence>[facts/code/docs supporting you]</evidence>
  <logic>[soundness of reasoning, assumptions]</logic>
  <expertise>[what you know well vs. are unsure about]</expertise>
  <can_exit>[true ONLY if score >= 90, answer complete, no ambiguity]</can_exit>
</confidence>

<semantic_focus>
1. [primary claim]
2. [secondary claim]
3. [tertiary claim]
</semantic_focus>"""

STYLE = (
    "Be concise and concrete: at most ~500 words outside code blocks, no restating the problem. "
    "Write in the same language as the problem."
)

ROLE_PROMPTS = {
    "solver": {
        "gemini": "You are the ARCHITECT in Synod, a multi-model deliberation council. "
        "Focus on structure, patterns, design trade-offs. Give an evidence-based solution.",
        "openai": "You are the EXPLORER in Synod, a multi-model deliberation council. "
        "Challenge assumptions, find edge cases and counter-examples others might miss, then give your solution.",
    },
    "critic": {
        "gemini": "You are a CRITIC in Synod. Validate the solver-round claims below: which are well "
        "supported, which are disputed (and why), and what was missed.",
        "openai": "You are a LOGIC CHECKER in Synod. Attack the solver-round claims below: concrete "
        "counter-examples, logical flaws, false premises, alternative interpretations.",
    },
    "defense": {
        "gemini": "You are the DEFENSE in Synod Court. Defend the leading solution below against the "
        "criticisms: rebut with evidence, fix what is fixable, explain why alternatives are worse. "
        "Do NOT concede just to reach consensus; concede only what is genuinely indefensible.",
        "openai": "You are the PROSECUTOR in Synod Court. Attack the leading solution below: fatal flaws, "
        "concrete failure scenarios, and a superior alternative if one exists. "
        "Do NOT agree just to reach consensus; concede only if the solution is genuinely sound.",
    },
}

ROUND_DIRS = {"solver": "round-1-solver", "critic": "round-2-critic", "defense": "round-3-defense"}


def _load_parser():
    spec = importlib.util.spec_from_file_location("synod_parser", TOOLS_DIR / "synod-parser.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser_mod = _load_parser()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_session(session_id: str | None) -> Path:
    if session_id:
        path = SESSIONS_DIR / session_id
    else:
        current = SESSIONS_DIR / ".current"
        if not current.exists():
            sys.exit("Error: no active Synod session (run 'synod-run start' first)")
        path = SESSIONS_DIR / current.read_text(encoding="utf-8").strip()
    if not (path / "meta.json").exists():
        sys.exit(f"Error: session not found: {path}")
    return path


def update_status(session: Path, **changes) -> dict:
    status = read_json(session / "status.json")
    status.update(changes)
    status["last_updated"] = now()
    write_json(session / "status.json", status)
    return status


def call_model(provider: str, model: str, level: str, prompt: str) -> dict:
    """Run one CLI call. Returns {ok, text, model, level, elapsed, error}."""
    if provider == "gemini":
        cmd = [sys.executable, str(TOOLS_DIR / "gemini-3.py"), "--model", model,
               "--thinking", level, "--timeout", str(TIMEOUTS[level]), "--retries", "2"]
    else:
        cmd = [sys.executable, str(TOOLS_DIR / "openai-cli.py"), "--model", model,
               "--reasoning", level, "--timeout", str(TIMEOUTS[level]), "--retries", "2"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    start = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              env=env, timeout=TIMEOUTS[level] * 2)
        ok = proc.returncode == 0 and proc.stdout.strip() != ""
        error = None if ok else (proc.stderr.strip()[-500:] or f"exit {proc.returncode}")
        text = proc.stdout.strip()
    except subprocess.TimeoutExpired:
        ok, text, error = False, "", f"timeout after {TIMEOUTS[level] * 2}s"
    return {"ok": ok, "text": text, "model": model, "level": level,
            "elapsed": round(time.time() - start, 1), "error": error}


def call_with_fallback(provider: str, model: str, level: str, prompt: str) -> dict:
    result = call_model(provider, model, level, prompt)
    if result["ok"]:
        return result
    fb_model, fb_level = FALLBACK[provider]
    if (fb_model, fb_level) == (model, level):
        return result
    print(f"[synod-run] {provider} failed ({result['error']}); falling back to {fb_model}/{fb_level}",
          file=sys.stderr)
    fallback = call_model(provider, fb_model, fb_level, prompt)
    fallback["fallback_from"] = f"{model}/{level}: {result['error']}"
    return fallback


def build_prompt(round_name: str, provider: str, meta: dict, problem: str, context: str) -> str:
    gemini_focus, openai_focus = FOCUS[meta["mode"]]
    focus = gemini_focus if provider == "gemini" else openai_focus
    parts = [ROLE_PROMPTS[round_name][provider],
             f"Mode: {meta['mode']}. Emphasize: {focus}.", STYLE]
    if context:
        title = "Prior round summary" if round_name == "critic" else "Case file (leading solution + criticisms)"
        parts.append(f"## {title}\n{context}")
    parts.append(f"## Problem\n{problem}")
    parts.append(SID_BLOCKS)
    return "\n\n".join(parts)


def strip_sid(text: str) -> str:
    text = re.sub(r"<confidence[^>]*>.*?</confidence>", "", text, flags=re.DOTALL)
    text = re.sub(r"<semantic_focus>.*?</semantic_focus>", "", text, flags=re.DOTALL)
    return text.strip()


def run_round(session: Path, round_name: str, context: str, max_chars: int) -> None:
    meta = read_json(session / "meta.json")
    problem = (session / "problem.md").read_text(encoding="utf-8")
    round_dir = session / ROUND_DIRS[round_name]
    round_dir.mkdir(exist_ok=True)
    if context:
        (round_dir / "context.md").write_text(context, encoding="utf-8")
    update_status(session, resume_point=f"{round_name}-running")

    jobs = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for provider in ("gemini", "openai"):
            model, level = meta["model_config"][provider]
            prompt = build_prompt(round_name, provider, meta, problem, context)
            jobs[provider] = pool.submit(call_with_fallback, provider, model, level, prompt)
    results = {p: f.result() for p, f in jobs.items()}

    summary = {}
    for provider, res in results.items():
        parsed = parser_mod.parse_response(res["text"]) if res["ok"] else None
        (round_dir / f"{provider}.md").write_text(res["text"] or f"[FAILED] {res['error']}",
                                                  encoding="utf-8")
        summary[provider] = {k: v for k, v in res.items() if k != "text"}
        summary[provider]["parsed"] = parsed
    write_json(round_dir / "signals.json", summary)

    status = read_json(session / "status.json")
    status["completed_rounds"] = sorted(set(status.get("completed_rounds", [])) | {round_name})
    update_status(session, completed_rounds=status["completed_rounds"],
                  resume_point=f"{round_name}-done")
    print_round(round_name, results, summary, max_chars)


def print_round(round_name: str, results: dict, summary: dict, max_chars: int) -> None:
    print(f"=== Synod {round_name} round ===")
    all_exit = True
    for provider, res in results.items():
        info = summary[provider]
        if not res["ok"]:
            all_exit = False
            print(f"\n## {provider}: FAILED ({info['error']}) - note this in the synthesis")
            continue
        conf = (info["parsed"] or {}).get("confidence") or {}
        focus = (info["parsed"] or {}).get("semantic_focus") or []
        warn = " [format defaults applied]" if (info["parsed"] or {}).get("format_warning") else ""
        fb = f" [fallback from {info['fallback_from']}]" if info.get("fallback_from") else ""
        all_exit = all_exit and bool(conf.get("can_exit")) and conf.get("score", 0) >= 90
        print(f"\n## {provider} ({info['model']}/{info['level']}, {info['elapsed']}s){fb}{warn}")
        print(f"confidence={conf.get('score', 50)} can_exit={conf.get('can_exit', False)}")
        if focus:
            print("focus: " + " | ".join(focus[:3]))
        body = strip_sid(res["text"])
        if len(body) > max_chars:
            body = body[:max_chars] + f"\n...[truncated {len(body) - max_chars} chars; full text in session dir]"
        print(body)
    print(f"\n=== external_can_exit={all_exit} ===")


def cmd_start(args) -> None:
    problem = Path(args.problem_file).read_text(encoding="utf-8").strip()
    if not problem:
        sys.exit("Error: problem is empty")
    claude = Path(args.claude_file).read_text(encoding="utf-8").strip()
    if not claude:
        sys.exit("Error: Claude's independent solver answer is required (--claude-file)")

    cfg = MODES[args.mode]
    gemini = (args.gemini_model or cfg["gemini"][0], args.gemini_thinking or cfg["gemini"][1])
    openai = (args.openai_model or cfg["openai"][0], args.openai_reasoning or cfg["openai"][1])
    session_id = f"synod-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    session = SESSIONS_DIR / session_id
    (session / ROUND_DIRS["solver"]).mkdir(parents=True)
    (session / "problem.md").write_text(problem, encoding="utf-8")
    (session / ROUND_DIRS["solver"] / "claude.md").write_text(claude, encoding="utf-8")
    write_json(session / "meta.json", {
        "session_id": session_id, "created_at": now(), "mode": args.mode,
        "model_config": {"gemini": gemini, "openai": openai}, "max_rounds": cfg["max_rounds"],
    })
    write_json(session / "status.json", {"status": "running", "completed_rounds": [],
                                         "resume_point": "solver", "last_updated": now()})
    (SESSIONS_DIR / ".current").write_text(session_id, encoding="utf-8")
    print(f"[Synod] session={session_id} mode={args.mode} "
          f"gemini={gemini[0]}/{gemini[1]} openai={openai[0]}/{openai[1]} max_rounds={cfg['max_rounds']}")
    run_round(session, "solver", "", args.max_chars)


def cmd_round(args, round_name: str) -> None:
    session = resolve_session(args.session)
    context = Path(args.context_file).read_text(encoding="utf-8").strip()
    if not context:
        sys.exit("Error: context is empty")
    run_round(session, round_name, context, args.max_chars)


def cmd_finish(args) -> None:
    session = resolve_session(args.session)
    synthesis = Path(args.synthesis_file).read_text(encoding="utf-8")
    (session / "synthesis.md").write_text(synthesis, encoding="utf-8")
    update_status(session, status="complete", final_confidence=args.confidence,
                  resume_point="done", completed_at=now())
    print(f"[Synod] {session.name} complete (confidence {args.confidence}%)")


def cmd_status(args) -> None:
    session = resolve_session(args.session)
    print(json.dumps({"session": session.name, "meta": read_json(session / "meta.json"),
                      "status": read_json(session / "status.json"),
                      "files": sorted(str(p.relative_to(session)) for p in session.rglob("*") if p.is_file())},
                     ensure_ascii=False, indent=2))


def cmd_cancel(args) -> None:
    session = resolve_session(args.session)
    update_status(session, status="cancelled")
    print(f"[Synod] {session.name} cancelled; partial results kept in {session}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Synod round runner")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="create session and run the solver round")
    p.add_argument("--mode", choices=list(MODES), default="general")
    p.add_argument("--problem-file", required=True)
    p.add_argument("--claude-file", required=True, help="Claude's independent solver answer")
    p.add_argument("--gemini-model")
    p.add_argument("--gemini-thinking", choices=["low", "medium", "high"])
    p.add_argument("--openai-model")
    p.add_argument("--openai-reasoning", choices=["low", "medium", "high"])

    for name in ("critic", "defense"):
        p = sub.add_parser(name, help=f"run the {name} round")
        p.add_argument("--context-file", required=True)
        p.add_argument("--session")

    p = sub.add_parser("finish", help="save synthesis and close the session")
    p.add_argument("--synthesis-file", required=True)
    p.add_argument("--confidence", type=int, required=True)
    p.add_argument("--session")

    for name in ("status", "cancel"):
        sub.add_parser(name).add_argument("--session")

    for p in sub.choices.values():
        p.add_argument("--max-chars", type=int, default=6000,
                       help="max printed chars per model response (full text is saved)")

    args = ap.parse_args()
    if args.command == "start":
        cmd_start(args)
    elif args.command in ("critic", "defense"):
        cmd_round(args, args.command)
    elif args.command == "finish":
        cmd_finish(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        cmd_cancel(args)


if __name__ == "__main__":
    main()
