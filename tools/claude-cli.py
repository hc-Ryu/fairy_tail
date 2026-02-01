#!/usr/bin/env python3
"""
Anthropic Claude CLI with Extended Thinking, streaming, and retry logic.

Usage:
  echo "prompt" | claude-cli [options]
  claude-cli "prompt" [options]
  claude-cli --model opus --thinking high "prompt"

Models: sonnet (default), opus, haiku
Thinking: none (default), low, medium, high
"""

import argparse
import os
import sys
import time

# Suppress warnings
import warnings
from typing import Optional

warnings.filterwarnings("ignore")

try:
    import anthropic
except ImportError:
    print("Error: anthropic not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

# Model mapping
MODEL_MAP = {
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
    "haiku": "claude-haiku-4-5-20251001",
}

# Extended Thinking budget mapping (tokens)
THINKING_MAP = {
    "none": None,  # Extended thinking disabled
    "low": 1024,
    "medium": 2048,
    "high": 4096,
}

# Timeout settings (seconds)
BASE_TIMEOUT = {
    "haiku": 60,
    "sonnet": 90,
    "opus": 120,
}

THINKING_TIMEOUT_BONUS = {
    "haiku": 60,
    "sonnet": 60,
    "opus": 90,
}


def get_timeout(model: str, thinking_level: str) -> float:
    """Calculate timeout based on model and thinking level."""
    base = BASE_TIMEOUT.get(model, 90)
    if thinking_level != "none":
        base += THINKING_TIMEOUT_BONUS.get(model, 60)
    return float(base)


def create_client(api_key: str, timeout: float) -> anthropic.Anthropic:
    """Create Anthropic client with timeout."""
    return anthropic.Anthropic(api_key=api_key, timeout=timeout)


def generate_with_retry(
    client: anthropic.Anthropic,
    model: str,
    prompt: str,
    thinking_budget: Optional[int],
    use_streaming: bool,
    max_tokens: int = 4096,
    max_retries: int = 3,
    temperature: float = 1.0,
) -> str:
    """Generate content with retry on rate limit."""

    for attempt in range(max_retries):
        try:
            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Build request kwargs
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
            }

            # Add Extended Thinking if enabled
            if thinking_budget is not None:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

            if use_streaming:
                # Streaming mode
                full_response = ""
                with client.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        print(text, end="", flush=True)
                        full_response += text
                print()  # Final newline
                return full_response
            else:
                # Non-streaming mode
                response = client.messages.create(**kwargs)
                # Extract text from content blocks
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                return "\n".join(text_parts)

        except anthropic.RateLimitError:
            wait_time = 2 ** (attempt + 2)
            print(
                f"[Retry {attempt + 1}/{max_retries}] Rate limited - waiting {wait_time}s",
                file=sys.stderr,
            )
            time.sleep(wait_time)
            continue

        except anthropic.APITimeoutError as e:
            print(f"[Retry {attempt + 1}/{max_retries}] Timeout: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            else:
                print("Error: Max retries exceeded due to timeout", file=sys.stderr)
                sys.exit(1)

        except anthropic.APIError as e:
            error_str = str(e).lower()
            is_retryable = any(x in error_str for x in ["503", "overloaded", "unavailable"])

            if is_retryable and attempt < max_retries - 1:
                wait_time = 2**attempt
                print(
                    f"[Retry {attempt + 1}/{max_retries}] API error - waiting {wait_time}s: {e}",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
                continue
            else:
                print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
                sys.exit(1)

        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Error: Max retries ({max_retries}) exceeded", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Anthropic Claude CLI with Extended Thinking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  echo "Hello" | claude-cli
  claude-cli "Explain quantum computing"
  claude-cli --model opus --thinking high "Complex analysis"
  claude-cli --no-stream "Quick response"
        """,
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt text")
    parser.add_argument(
        "-m",
        "--model",
        choices=["sonnet", "opus", "haiku"],
        default="sonnet",
        help="Model to use (default: sonnet)",
    )
    parser.add_argument(
        "-t",
        "--thinking",
        choices=["none", "low", "medium", "high"],
        default="none",
        help="Extended Thinking level (default: none)",
    )
    parser.add_argument(
        "--timeout", type=float, default=None, help="Timeout in seconds (default: auto-calculated)"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=4096, help="Max tokens in response (default: 4096)"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (not recommended for long responses)",
    )
    parser.add_argument("--retries", type=int, default=3, help="Max retries (default: 3)")
    parser.add_argument(
        "--temperature", type=float, default=1.0, help="Temperature for generation (default: 1.0)"
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

    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Calculate timeout
    if args.timeout is None:
        timeout = get_timeout(args.model, args.thinking)
    else:
        timeout = args.timeout

    # Create client
    client = create_client(api_key, timeout)

    # Get model name and thinking budget
    model_name = MODEL_MAP[args.model]
    thinking_budget = THINKING_MAP[args.thinking]

    if args.verbose:
        print(f"Model: {model_name}", file=sys.stderr)
        print(
            f"Thinking: {args.thinking} ({thinking_budget} tokens)"
            if thinking_budget
            else "Thinking: disabled",
            file=sys.stderr,
        )
        print(f"Streaming: {not args.no_stream}", file=sys.stderr)
        print(f"Timeout: {timeout}s", file=sys.stderr)
        print(f"Max tokens: {args.max_tokens}", file=sys.stderr)

    # Generate response
    response = generate_with_retry(
        client=client,
        model=model_name,
        prompt=prompt,
        thinking_budget=thinking_budget,
        use_streaming=not args.no_stream,
        max_tokens=args.max_tokens,
        max_retries=args.retries,
        temperature=args.temperature,
    )

    if not args.no_stream:
        # Response already printed during streaming
        pass
    else:
        print(response)


if __name__ == "__main__":
    main()
