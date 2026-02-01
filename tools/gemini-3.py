#!/usr/bin/env python3
"""
Gemini 3 CLI with robust timeout handling, streaming, and adaptive retry.

Usage:
  echo "prompt" | gemini-3 [options]
  gemini-3 "prompt" [options]
  gemini-3 --model flash --thinking high "prompt"

Models: flash (default), pro
Thinking: minimal, low, medium (default), high
"""

import argparse
import os
import sys
import time

# Suppress warnings
import warnings

warnings.filterwarnings("ignore")

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai not installed. Run: pip install google-genai", file=sys.stderr)
    sys.exit(1)

# Model mapping
MODEL_MAP = {
    "flash": "gemini-3-flash-preview",
    "pro": "gemini-3-pro-preview",
    "2.5-flash": "gemini-2.5-flash",
    "2.5-pro": "gemini-2.5-pro",
}

# Thinking budget mapping (tokens)
THINKING_MAP = {
    "minimal": 50,
    "low": 200,
    "medium": 500,
    "high": 2000,
    "max": 10000,
}

# Retry levels (progressive downgrade)
RETRY_LEVELS = ["high", "medium", "low", "minimal"]


def create_client(timeout_ms: int = 300_000) -> genai.Client:
    """Create Gemini client with timeout."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))


def generate_with_retry(
    client: genai.Client,
    model: str,
    prompt: str,
    thinking_level: str,
    use_streaming: bool,
    max_retries: int = 3,
    adaptive: bool = True,
    temperature: float = 0.7,
) -> str:
    """Generate content with adaptive retry on timeout."""

    current_level = thinking_level
    current_level_idx = RETRY_LEVELS.index(current_level) if current_level in RETRY_LEVELS else 1

    for attempt in range(max_retries):
        try:
            thinking_budget = THINKING_MAP.get(current_level, 500)
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                temperature=temperature,
            )

            if use_streaming:
                # Streaming mode - prevents timeout for long responses
                stream = client.models.generate_content_stream(
                    model=model, contents=prompt, config=config
                )
                full_response = ""
                for chunk in stream:
                    if chunk.text:
                        full_response += chunk.text
                return full_response
            else:
                # Non-streaming mode
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                return response.text

        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__

            # Check for retryable errors
            is_timeout = any(x in error_str for x in ["timeout", "504", "gateway", "deadline"])
            is_rate_limit = any(
                x in error_str for x in ["429", "rate", "quota", "resource_exhausted"]
            )
            is_overloaded = any(x in error_str for x in ["503", "overloaded", "unavailable"])

            if is_timeout or is_overloaded:
                if adaptive and current_level_idx < len(RETRY_LEVELS) - 1:
                    # Downgrade thinking level
                    current_level_idx += 1
                    current_level = RETRY_LEVELS[current_level_idx]
                    print(
                        f"[Retry {attempt + 1}/{max_retries}] Timeout - downgrading thinking to '{current_level}'",
                        file=sys.stderr,
                    )
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                else:
                    print(f"[Retry {attempt + 1}/{max_retries}] {error_type}: {e}", file=sys.stderr)
                    time.sleep(2**attempt)
                    continue

            elif is_rate_limit:
                wait_time = 2 ** (attempt + 2)  # Longer backoff for rate limits
                print(
                    f"[Retry {attempt + 1}/{max_retries}] Rate limited - waiting {wait_time}s",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
                continue
            else:
                # Non-retryable error
                print(f"Error: {error_type}: {e}", file=sys.stderr)
                sys.exit(1)

    print(f"Error: Max retries ({max_retries}) exceeded", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Gemini 3 CLI with robust error handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  echo "Hello" | gemini-3
  gemini-3 "Explain quantum computing"
  gemini-3 --model pro --thinking high "Complex analysis"
  gemini-3 --no-stream "Quick response"
        """,
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt text")
    parser.add_argument(
        "-m",
        "--model",
        choices=["flash", "pro", "2.5-flash", "2.5-pro"],
        default="flash",
        help="Model to use (default: flash)",
    )
    parser.add_argument(
        "-t",
        "--thinking",
        choices=["minimal", "low", "medium", "high", "max"],
        default="medium",
        help="Thinking level (default: medium)",
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="Timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (not recommended for long prompts)",
    )
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="Disable adaptive retry (thinking level downgrade)",
    )
    parser.add_argument("--retries", type=int, default=3, help="Max retries (default: 3)")
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="Temperature for generation (default: 0.7)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args, remaining = parser.parse_known_args()

    # Get prompt from args, remaining args, or stdin
    if args.prompt:
        prompt = args.prompt
    elif remaining:
        prompt = " ".join(remaining)
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        parser.print_help()
        sys.exit(1)

    if not prompt:
        print("Error: No prompt provided", file=sys.stderr)
        sys.exit(1)

    # Create client with timeout
    timeout_ms = args.timeout * 1000
    client = create_client(timeout_ms)

    # Get model name
    model_name = MODEL_MAP.get(args.model, MODEL_MAP["flash"])

    if args.verbose:
        print(f"Model: {model_name}", file=sys.stderr)
        print(f"Thinking: {args.thinking}", file=sys.stderr)
        print(f"Streaming: {not args.no_stream}", file=sys.stderr)
        print(f"Timeout: {args.timeout}s", file=sys.stderr)

    # Generate response
    response = generate_with_retry(
        client=client,
        model=model_name,
        prompt=prompt,
        thinking_level=args.thinking,
        use_streaming=not args.no_stream,
        max_retries=args.retries,
        adaptive=not args.no_adaptive,
        temperature=args.temperature,
    )

    print(response)


if __name__ == "__main__":
    main()
