"""Usage: python -m delorme.cli data/samples/x.json [--model openai] [--version v1] [--critic gemini]"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .llm import parse_spec
from .pipeline import generate
from .schemas import CaseInput


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--model", default="openai")
    ap.add_argument("--critic", default=None)
    ap.add_argument("--version", default="v4", choices=["v0", "v1", "v2", "v3", "v3.1", "v4", "v4.1"])
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()

    case = CaseInput.model_validate_json(Path(a.case).read_text(encoding="utf-8"))
    out = generate(case, parse_spec(a.model), a.version, parse_spec(a.critic) if a.critic else None)

    print(f"== {out.case_id} | {out.version} | {out.model} | {out.trace.get('seconds')}s")
    print(f"风险：{out.risk.level} {out.risk.flags} {out.risk.advice}")
    for i, (c, chk) in enumerate(zip(out.candidates, out.checks), 1):
        mark = "OK" if chk["pass"] else "FAIL " + "；".join(chk["hard"])
        print(f"\n[{i}] {c.strategy}（{chk['length']}字，{mark}）\n{c.text}\n  ↳ CA备注：{c.note_for_ca}")
    print(f"\n候选间最大相似度：{out.trace.get('diversity_max_sim'):.2f}")
    if a.trace:
        print(json.dumps(out.trace, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
