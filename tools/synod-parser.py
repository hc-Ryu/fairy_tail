#!/usr/bin/env python3
"""
Synod Response Parser - Extract SID signals from model responses.

Usage:
  echo "response" | synod-parser
  synod-parser "response"
  synod-parser --validate "response"  # Check format only
  synod-parser --trust C R I S        # Calculate Trust Score
"""
import sys
import re
import json
import argparse
from typing import Optional, Dict, Any, List

def validate_format(text: str) -> Dict[str, bool]:
    """Check if response has required XML format."""
    return {
        'has_confidence': bool(re.search(r'<confidence[^>]*>.*?</confidence>', text, re.DOTALL)),
        'has_score': bool(re.search(r'<confidence\s+score="\d+"', text)),
        'has_semantic_focus': bool(re.search(r'<semantic_focus>.*?</semantic_focus>', text, re.DOTALL)),
        'is_valid': all([
            re.search(r'<confidence[^>]*>.*?</confidence>', text, re.DOTALL),
            re.search(r'<semantic_focus>.*?</semantic_focus>', text, re.DOTALL)
        ])
    }

def extract_confidence(text: str) -> Optional[Dict[str, Any]]:
    """Extract confidence block from response."""
    pattern = r'<confidence\s+score="(\d+)">(.*?)</confidence>'
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return None

    score = int(match.group(1))
    inner = match.group(2)

    # Extract sub-elements
    evidence = re.search(r'<evidence>(.*?)</evidence>', inner, re.DOTALL)
    logic = re.search(r'<logic>(.*?)</logic>', inner, re.DOTALL)
    expertise = re.search(r'<expertise>(.*?)</expertise>', inner, re.DOTALL)
    can_exit = re.search(r'<can_exit>(.*?)</can_exit>', inner, re.DOTALL)

    return {
        'score': score,
        'evidence': evidence.group(1).strip() if evidence else None,
        'logic': logic.group(1).strip() if logic else None,
        'expertise': expertise.group(1).strip() if expertise else None,
        'can_exit': can_exit.group(1).strip().lower() == 'true' if can_exit else False
    }

def extract_semantic_focus(text: str) -> List[str]:
    """Extract semantic focus points."""
    pattern = r'<semantic_focus>(.*?)</semantic_focus>'
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return []

    content = match.group(1).strip()
    # Split by newlines or numbered items
    items = re.split(r'\n\s*\d+\.\s*|\n', content)
    return [item.strip() for item in items if item.strip()]

def extract_key_sentences(text: str, limit: int = 3) -> List[str]:
    """Extract key sentences when semantic_focus is missing."""
    # Remove XML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Split into sentences
    sentences = re.split(r'[.!?]\s+', clean)
    # Return first N non-empty sentences
    return [s.strip() for s in sentences if len(s.strip()) > 20][:limit]

def calculate_trust_score(c: float, r: float, i: float, s: float) -> Dict[str, Any]:
    """
    Calculate CortexDebate Trust Score.
    T = (C x R x I) / S

    Args:
        c: Credibility (0-1)
        r: Reliability (0-1)
        i: Intimacy (0-1)
        s: Self-Orientation (0.1-1)
    """
    if s < 0.1:
        s = 0.1  # Minimum to avoid extreme values

    trust = min((c * r * i) / s, 2.0)  # Capped at 2.0 per CortexDebate spec

    return {
        'credibility': c,
        'reliability': r,
        'intimacy': i,
        'self_orientation': s,
        'trust_score': round(trust, 3),
        'include': trust >= 0.5,
        'rating': 'high' if trust >= 1.5 else 'good' if trust >= 1.0 else 'acceptable' if trust >= 0.5 else 'low'
    }

def apply_defaults(text: str) -> Dict[str, Any]:
    """Apply default values for malformed responses."""
    return {
        'confidence': {
            'score': 50,
            'evidence': None,
            'logic': None,
            'expertise': None,
            'can_exit': False
        },
        'semantic_focus': extract_key_sentences(text, 3),
        'format_warning': 'Model did not comply with SID format - defaults applied'
    }

def parse_response(text: str) -> Dict[str, Any]:
    """Parse full response and extract all SID signals."""
    validation = validate_format(text)

    if not validation['is_valid']:
        result = apply_defaults(text)
        result['validation'] = validation
        return result

    result = {
        'confidence': extract_confidence(text),
        'semantic_focus': extract_semantic_focus(text),
        'validation': validation,
        'raw_length': len(text),
        'has_code': bool(re.search(r'```[\w]*\n', text))
    }

    # Calculate derived metrics
    if result['confidence']:
        result['can_exit_early'] = result['confidence'].get('can_exit', False)
        result['high_confidence'] = result['confidence']['score'] >= 85

    return result

def main():
    parser = argparse.ArgumentParser(description='Parse Synod SID signals')
    parser.add_argument('text', nargs='?', help='Response text to parse')
    parser.add_argument('--validate', action='store_true', help='Only validate format')
    parser.add_argument('--trust', nargs=4, type=float, metavar=('C', 'R', 'I', 'S'),
                        help='Calculate Trust Score from C R I S values')

    args = parser.parse_args()

    # Trust score calculation mode
    if args.trust:
        result = calculate_trust_score(*args.trust)
        print(json.dumps(result, indent=2))
        return

    # Get input text
    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Usage: synod-parser 'response' or echo 'response' | synod-parser", file=sys.stderr)
        sys.exit(1)

    # Validation only mode
    if args.validate:
        result = validate_format(text)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['is_valid'] else 1)

    # Full parse
    result = parse_response(text)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
