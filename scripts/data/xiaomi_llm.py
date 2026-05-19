#!/usr/bin/env python3
"""
xiaomi_llm.py — minimal OpenAI-compatible client for Xiaomi MiMo v2.5-pro.

Used by GH Action workflows (brief-fallback / weekly-review / news-digest)
that need to call an LLM directly without going through openclaw gateway.

Why direct API instead of openclaw:
- GH Action runners can't reach our local openclaw gateway
- Self-contained: just needs XIAOMI_API_KEY env var
- thinking=disabled to avoid multi-turn reasoning_content 400 (same as
  openclaw 2026.5.18's hard-guard for xiaomi)

Usage:
    from xiaomi_llm import chat
    reply = chat(
        system="You are Rick, kcn's stock analyst.",
        user="Write today's pre-open brief based on this context: ...",
        max_tokens=8000,
    )
"""
import json
import os
import sys
import time

import requests

DEFAULT_BASE = 'https://token-plan-cn.xiaomimimo.com/v1'
DEFAULT_MODEL = 'mimo-v2.5-pro'
TIMEOUT = 180  # 3 min per call
MAX_RETRIES = 3


def chat(system: str = '', user: str = '', messages: list = None,
         max_tokens: int = 8000, temperature: float = 0.7,
         model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE,
         api_key: str = None, thinking_disabled: bool = True,
         json_response: bool = False) -> str:
    """Call Xiaomi MiMo. Returns assistant content string (or raises)."""
    api_key = api_key or os.environ.get('XIAOMI_API_KEY')
    if not api_key:
        raise RuntimeError('XIAOMI_API_KEY env var not set')

    if messages is None:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        if user:
            messages.append({'role': 'user', 'content': user})

    body = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    if thinking_disabled:
        # Required for multi-turn — see /root/.claude/projects/-root/memory/openclaw-xiaomi-fallback.md
        body['thinking'] = {'type': 'disabled'}
    if json_response:
        body['response_format'] = {'type': 'json_object'}

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(f'{base_url}/chat/completions',
                              json=body, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                content = data['choices'][0]['message']['content']
                usage = data.get('usage', {})
                # Log to stderr for traceability
                print(f'  xiaomi: {usage.get("total_tokens","?")} tokens '
                      f'({usage.get("prompt_tokens","?")} in / {usage.get("completion_tokens","?")} out)',
                      file=sys.stderr)
                return content
            elif r.status_code == 429:
                # Rate limit — wait and retry
                wait = 5 * attempt
                print(f'  xiaomi: 429 rate limit, sleeping {wait}s', file=sys.stderr)
                time.sleep(wait)
                continue
            else:
                last_err = f'HTTP {r.status_code}: {r.text[:300]}'
                print(f'  xiaomi: {last_err}', file=sys.stderr)
        except requests.Timeout:
            last_err = 'timeout after 180s'
            print(f'  xiaomi: {last_err} (attempt {attempt})', file=sys.stderr)
        except Exception as e:
            last_err = f'{type(e).__name__}: {e}'
            print(f'  xiaomi: {last_err}', file=sys.stderr)
        time.sleep(2 * attempt)

    raise RuntimeError(f'Xiaomi call failed after {MAX_RETRIES} attempts: {last_err}')


if __name__ == '__main__':
    # Sanity test: cli example
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--system', default='You are a helpful stock analyst.')
    ap.add_argument('--user', required=True)
    ap.add_argument('--max-tokens', type=int, default=2000)
    args = ap.parse_args()
    print(chat(system=args.system, user=args.user, max_tokens=args.max_tokens))
