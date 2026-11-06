"""Judge every output in runs/<run>/<provider>/*.json with one or more judge models.

Usage: python scripts/judge_run.py --run bakeoff --judges openai anthropic
Writes runs/<run>/judge_<judge_provider>/<gen_provider>/<case>.json (resumable).
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from delorme.judge import judge  # noqa: E402
from delorme.llm import parse_spec  # noqa: E402
from delorme.schemas import CaseInput, ToolOutput  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--judges", nargs="+", default=["openai"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    run_dir = ROOT / "runs" / a.run
    outputs = sorted(p for p in run_dir.glob("*/C*.json") if not p.parent.name.startswith("judge_"))
    jobs = []
    for jm in a.judges:
        spec = parse_spec(jm)
        for p in outputs:
            dest = run_dir / f"judge_{spec.provider}" / p.parent.name / p.name
            if not dest.exists():
                jobs.append((spec, p, dest))
    print(f"{len(jobs)} judge jobs")

    def work(spec, p, dest):
        case = CaseInput.model_validate_json((ROOT / "data/cases" / p.name).read_text(encoding="utf-8"))
        out = ToolOutput.model_validate_json(p.read_text(encoding="utf-8"))
        res = judge(case, out, spec)
        res["_judge"] = spec.label
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(work, *j): j for j in jobs}
        for fut in as_completed(futs):
            spec, p, _ = futs[fut]
            try:
                fut.result()
                done += 1
                print(f"[{done}/{len(jobs)}] {spec.provider} judged {p.parent.name}/{p.stem}", flush=True)
            except Exception as e:
                print(f"FAIL {spec.provider} {p.parent.name}/{p.stem}: {e!r}"[:300], flush=True)


if __name__ == "__main__":
    main()
