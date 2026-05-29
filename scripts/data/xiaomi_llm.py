#!/usr/bin/env python3
"""
xiaomi_llm.py — minimal OpenAI-compatible LLM client for GH Action workflows.

Primary: Xiaomi MiMo v2.5-pro. Fallback: MiniMax M2.7 (when Xiaomi errors out or
its key is missing). Both are OpenAI chat/completions compatible. Used by
brief-fallback / weekly-review / news-digest / influencer-scan — none of which
can reach the local openclaw gateway, so they call the vendor API directly.

Why a fallback (2026-05-30, kcn 要求): Xiaomi has had empty-turn / sensitive-content
/ rate-limit hiccups that can blank a scheduled job's output. If Xiaomi fails all
retries, we transparently retry on MiniMax so the cron still produces something.

Env:
- XIAOMI_API_KEY   — primary
- MINIMAX_API_KEY  — fallback (optional; if unset, fallback is skipped)

Notes:
- thinking=enabled by default for single-turn calls (multi-turn reasoning_content
  bug only fires with chat history containing prior assistant tool_calls — GH
  Action calls are pure single-turn so safe). The `thinking` param is Xiaomi-
  specific and is NOT sent to MiniMax (MiniMax reasoning is on by default).
- response_format=json_object is sent only to Xiaomi; for MiniMax we rely on the
  prompt's "只返回 JSON" instruction + a markdown-fence stripper, to avoid a 400
  if MiniMax rejects the param.

Usage:
    from xiaomi_llm import chat
    reply = chat(system="...", user="...", max_tokens=32000)
"""
import json
import os
import re
import sys
import time

import requests

DEFAULT_BASE = 'https://token-plan-cn.xiaomimimo.com/v1'
DEFAULT_MODEL = 'mimo-v2.5-pro'
MINIMAX_BASE = 'https://api.minimaxi.com/v1'
MINIMAX_MODEL = 'MiniMax-M2.7'
MINIMAX_MAX_TOKENS = 65536  # M2.7 maxOutput cap
TIMEOUT = 180  # 3 min per call
MAX_RETRIES = 3


def _clean(s: str) -> str:
    """Normalize provider output: strip MiniMax inline <think>…</think> reasoning
    blocks and an outer ```/```json code fence, so prose and json.loads both work."""
    t = (s or '')
    # MiniMax M2.7 emits reasoning inline as <think>…</think> before the answer.
    if '</think>' in t:
        t = t[t.rindex('</think>') + len('</think>'):]
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.S).strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-zA-Z]*\n?', '', t)
        t = re.sub(r'\n?```$', '', t.strip())
    return t.strip()


def _call_provider(label, base_url, api_key, model, messages, max_tokens,
                   temperature, json_response, thinking):
    """One provider, with retries. Returns content str or raises RuntimeError."""
    body = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    if thinking is not None:
        body['thinking'] = thinking
    if json_response:
        body['response_format'] = {'type': 'json_object'}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(f'{base_url}/chat/completions',
                              json=body, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                msg = r.json()['choices'][0]['message']
                content = msg.get('content') or msg.get('reasoning_content') or ''
                usage = r.json().get('usage', {})
                print(f'  {label}: {usage.get("total_tokens","?")} tokens '
                      f'({usage.get("prompt_tokens","?")} in / '
                      f'{usage.get("completion_tokens","?")} out)', file=sys.stderr)
                return _clean(content)
            elif r.status_code == 429:
                wait = 5 * attempt
                print(f'  {label}: 429 rate limit, sleeping {wait}s', file=sys.stderr)
                time.sleep(wait)
                continue
            else:
                last_err = f'HTTP {r.status_code}: {r.text[:300]}'
                print(f'  {label}: {last_err}', file=sys.stderr)
        except requests.Timeout:
            last_err = 'timeout after 180s'
            print(f'  {label}: {last_err} (attempt {attempt})', file=sys.stderr)
        except Exception as e:
            last_err = f'{type(e).__name__}: {e}'
            print(f'  {label}: {last_err}', file=sys.stderr)
        time.sleep(2 * attempt)
    raise RuntimeError(f'{label} failed after {MAX_RETRIES} attempts: {last_err}')


def chat(system: str = '', user: str = '', messages: list = None,
         max_tokens: int = 32000, temperature: float = 0.7,
         model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE,
         api_key: str = None, thinking_disabled: bool = False,
         json_response: bool = False, fallback: bool = True) -> str:
    """Call Xiaomi MiMo; on total failure fall back to MiniMax M2.7.

    Returns assistant content string, or raises if BOTH providers fail.
    Set fallback=False to use Xiaomi only.
    """
    if messages is None:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        if user:
            messages.append({'role': 'user', 'content': user})

    thinking = {'type': 'disabled'} if thinking_disabled else {'type': 'enabled'}
    errors = []

    # ── Primary: Xiaomi MiMo (thinking + response_format supported) ──
    xiaomi_key = api_key or os.environ.get('XIAOMI_API_KEY')
    if xiaomi_key:
        try:
            return _call_provider('xiaomi', base_url, xiaomi_key, model, messages,
                                  max_tokens, temperature, json_response, thinking)
        except Exception as e:
            errors.append(f'xiaomi[{e}]')
            print(f'  ⚠️ xiaomi exhausted — falling back to MiniMax', file=sys.stderr)
    else:
        errors.append('xiaomi[no XIAOMI_API_KEY]')

    # ── Fallback: MiniMax M2.7 (omit Xiaomi-specific thinking + response_format) ──
    mm_key = os.environ.get('MINIMAX_API_KEY')
    if fallback and mm_key:
        try:
            return _call_provider('minimax', MINIMAX_BASE, mm_key, MINIMAX_MODEL,
                                  messages, min(max_tokens, MINIMAX_MAX_TOKENS),
                                  temperature, json_response=False, thinking=None)
        except Exception as e:
            errors.append(f'minimax[{e}]')
    elif fallback and not mm_key:
        errors.append('minimax[no MINIMAX_API_KEY]')

    raise RuntimeError('all LLM providers failed: ' + ' | '.join(errors))


if __name__ == '__main__':
    # Sanity test: cli example
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--system', default='You are a helpful stock analyst.')
    ap.add_argument('--user', required=True)
    ap.add_argument('--max-tokens', type=int, default=2000)
    args = ap.parse_args()
    print(chat(system=args.system, user=args.user, max_tokens=args.max_tokens))
