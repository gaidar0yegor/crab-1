#!/usr/bin/env python3
"""Native tool-calling eval for Crab-1 — the exact harness behind the published
numbers. Works for the fine-tuned model AND untrained baselines, so any
comparison is apples-to-apples.

The model (served by Ollama, or any OpenAI-compatible endpoint) gets the
canonical system prompt + tool schemas, emits native tool_calls, this script
executes the real tools, and on submit_answer grades the profile against the
ground truth (department-level location, TLD-aware website score, dynamic
denominator).

Usage:
  python eval/run_eval.py --model crab1-v7 --out results/crab1_v7.json
  python eval/run_eval.py --model qwen3:1.7b --out results/baseline.json
Env:
  OLLAMA_BASE_URL (default http://localhost:11434)

NOTE: the tools hit the live web — scores drift over time. Compare models
measured the SAME DAY only. See README → "This benchmark is perishable".
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import crab_harness as ch
from harness.reward import compute_reward
from harness.tools import OSINTTools
from harness.agent_config import SYSTEM_PROMPT, TOOLS

OLLAMA = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
EVAL_PATH = ROOT / 'data' / 'eval_ground_truth_v3_enriched.json'
TOOLS_TOOLS = OSINTTools()


def execute_tool(name, args):
    """Observations use the SAME compact shape the model saw at training time."""
    try:
        if name == 'registry_lookup':
            reg = TOOLS_TOOLS.registry_lookup(args.get('company_name', ''))
            top = reg.get('top') if isinstance(reg, dict) else None
            return {'success': bool(top), 'top': top or {}}
        if name == 'web_search':
            res = TOOLS_TOOLS.web_search(args.get('query', ''), args.get('limit', 5)).get('results', [])
            return [{'title': r.get('title', ''), 'url': r.get('url', ''),
                     'description': (r.get('description', '') or '')[:200]} for r in res[:6]]
        if name == 'web_extract':
            res = TOOLS_TOOLS.web_extract(args.get('urls', []), 1500).get('results', [])
            return [{'url': r.get('url', ''), 'content': (r.get('content', '') or '')[:800]} for r in res]
        if name == 'submit_answer':
            return {'status': 'submitted'}
    except Exception as e:
        return {'error': str(e)}
    return {'error': f'unknown tool {name}'}


def run_episode(model, name, max_turns=8):
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': f"Build a company profile for: {name}"},
    ]
    answer, turns, valid_calls, total_calls = None, 0, 0, 0
    for turn in range(1, max_turns + 1):
        turns = turn
        try:
            resp = ch.call_llm(model, messages, tools=TOOLS, temperature=0.0, base_url=OLLAMA)
            msg = resp['choices'][0]['message']
        except Exception as e:
            messages.append({'role': 'user', 'content': f"(error: {e})"})
            break
        tcs = msg.get('tool_calls') or []
        if tcs:
            tc = tcs[0]
            total_calls += 1
            fn = tc['function']['name']
            try:
                args = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']
                valid_calls += 1
            except Exception:
                args = {}
            result = execute_tool(fn, args)
            messages.append({'role': 'assistant', 'content': msg.get('content') or '', 'tool_calls': [tc]})
            messages.append({'role': 'tool', 'tool_call_id': tc.get('id', f'call_{turn}'),
                             'name': fn, 'content': json.dumps(result, ensure_ascii=False)[:8000]})
            if fn == 'submit_answer':
                answer = args
                break
        else:
            messages.append({'role': 'assistant', 'content': msg.get('content') or ''})
            messages.append({'role': 'user', 'content': "Call a tool, or submit_answer if you have enough facts."})
    return {'answer': answer or {}, 'turns': turns,
            'valid_call_rate': (valid_calls / total_calls) if total_calls else 0.0,
            'made_tool_call': total_calls > 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--eval-file', default=None,
                    help='custom ground-truth JSON (defaults to the 30-company benchmark)')
    args = ap.parse_args()

    eval_path = Path(args.eval_file) if args.eval_file else EVAL_PATH
    records = json.loads(eval_path.read_text())
    if args.limit:
        records = records[:args.limit]

    results = []
    t0 = time.time()
    for i, r in enumerate(records, 1):
        ep = run_episode(args.model, r['name'])
        rew = compute_reward(ep['answer'], r['expected'])
        results.append({'company': r['name'], 'answer': ep['answer'], 'expected': r['expected'],
                        'reward': rew, 'turns': ep['turns'], 'valid_call_rate': ep['valid_call_rate'],
                        'made_tool_call': ep['made_tool_call'], 'submitted': bool(ep['answer'])})
        print(f"[{i}/{len(records)}] {r['name']:18s} reward={rew['total']} "
              f"comp={rew['components']} turns={ep['turns']} sub={bool(ep['answer'])}", flush=True)

    n = len(results)
    def frac(key_fn):
        vals = [key_fn(x) for x in results if key_fn(x) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None
    summary = {
        'model': args.model, 'n': n, 'date': time.strftime('%Y-%m-%d'),
        'avg_reward': round(sum(x['reward']['total'] for x in results) / n, 3),
        'pass_rate': round(sum(1 for x in results if x['reward']['passes_threshold']) / n, 3),
        'submit_rate': round(sum(1 for x in results if x['submitted']) / n, 3),
        'tool_call_rate': round(sum(1 for x in results if x['made_tool_call']) / n, 3),
        'valid_call_rate': round(sum(x['valid_call_rate'] for x in results) / n, 3),
        'avg_turns': round(sum(x['turns'] for x in results) / n, 2),
        'acc_website': frac(lambda x: x['reward']['components'].get('website')),
        'acc_sector': frac(lambda x: x['reward']['components'].get('sector')),
        'acc_city': frac(lambda x: x['reward']['components'].get('city')),
        'wall_seconds': round(time.time() - t0, 1),
        'results': results,
    }
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== SUMMARY ===")
    print(json.dumps({k: v for k, v in summary.items() if k != 'results'}, ensure_ascii=False, indent=2))
    print(f"Saved {outp}")


if __name__ == '__main__':
    main()
