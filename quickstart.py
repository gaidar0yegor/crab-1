#!/usr/bin/env python3
"""Profile one company with Crab-1: python quickstart.py "Doctolib" """
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval.run_eval import run_episode

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: python quickstart.py "<company name>" [model]')
    company = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else 'crab1-v7'
    ep = run_episode(model, company)
    print(json.dumps(ep['answer'], ensure_ascii=False, indent=2))
    print(f"\n({ep['turns']} turns)")
