"""Run the tool over many cases × models, concurrently and resumably.

Usage:
  python scripts/run_batch.py --run bakeoff --version v1 --models openai anthropic gemini deepseek kimi --cases C01 C09 ...
  python scripts/run_batch.py --run main_v1 --version v1 --models openai --cases all
Outputs: runs/<run>/<provider>/<case_id>.json  (existing files are skipped, so re-running resumes)
"""
import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from delorme.llm import parse_spec  # noqa: E402
from delorme.pipeline import generate  # noqa: E402
from delorme.schemas import CaseInput  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--version", default="v4", choices=["v0", "v1", "v2", "v3", "v3.1", "v4", "v4.1"])
    ap.add_argument("--models", nargs="+", default=["openai"])
    ap.add_argument("--critic", default=None)
    ap.add_argument("--cases", nargs="+", default=["all"])
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    case_files = sorted((ROOT / "data/cases").glob("C*.json"))
    if a.cases != ["all"]:
        case_files = [f for f in case_files if f.stem in a.cases]
    jobs = []
    for m in a.models:
        spec = parse_spec(m)
        out_dir = ROOT / "runs" / a.run / spec.provider
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in case_files:
            out = out_dir / f"{f.stem}.json"
            if not out.exists():
                jobs.append((spec, f, out))
    print(f"{len(jobs)} jobs to run")

    def work(spec, f, out):
        case = CaseInput.model_validate_json(f.read_text(encoding="utf-8"))
        res = generate(case, spec, a.version, parse_spec(a.critic) if a.critic else None)
        out.write_text(res.model_dump_json(indent=1), encoding="utf-8")
        return f"{spec.label} {f.stem} {res.trace.get('seconds')}s"

    t0, done, failed = time.time(), 0, []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(work, *j): j for j in jobs}
        for fut in as_completed(futs):
            spec, f, _ = futs[fut]
            try:
                msg = fut.result()
                done += 1
                print(f"[{done}/{len(jobs)}] {msg}", flush=True)
            except Exception as e:
                failed.append(f"{spec.label} {f.stem}: {e!r}"[:300])
                print(f"FAIL {spec.label} {f.stem}: {e!r}"[:300], flush=True)
    print(f"\nfinished {done}, failed {len(failed)} in {time.time() - t0:.0f}s")
    (ROOT / "runs" / a.run / "failures.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
