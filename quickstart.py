#!/usr/bin/env python3
"""Profile one company with Crab-1: python quickstart.py "Doctolib" """
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval.run_eval import run_episode


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: python quickstart.py "<company name>" [model] [seed]')
    company = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else 'crab1-v7'
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    ep = run_episode(model, company, seed=seed)
    print(json.dumps(ep['answer'], ensure_ascii=False, indent=2))
    print(f"\n({ep['turns']} turns, seed={seed})")


if __name__ == '__main__':
    main()
