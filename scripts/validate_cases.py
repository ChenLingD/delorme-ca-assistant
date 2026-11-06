"""Validate data/cases/*.json against the schema, the catalog and data/test_matrix.yaml.

Usage: python scripts/validate_cases.py [C01 C02 ...]
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from delorme.knowledge import event, product  # noqa: E402
from delorme.schemas import CaseInput  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
matrix = {c["id"]: c for c in yaml.safe_load((ROOT / "data/test_matrix.yaml").read_text(encoding="utf-8"))["cases"]}
ids = sys.argv[1:] or sorted(matrix)
bad = 0
for cid in ids:
    f = ROOT / "data/cases" / f"{cid}.json"
    errs = []
    if not f.exists():
        print(f"{cid}: MISSING")
        bad += 1
        continue
    try:
        case = CaseInput.model_validate(json.loads(f.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"{cid}: SCHEMA ERROR {e}")
        bad += 1
        continue
    m = matrix[cid]
    if case.case_id != cid:
        errs.append("case_id mismatch")
    if case.scenario != m["scenario"]:
        errs.append(f"scenario {case.scenario} != {m['scenario']}")
    if case.today != m["today"]:
        errs.append(f"today {case.today} != {m['today']}")
    for sku in case.product_skus:
        if not product(sku):
            errs.append(f"unknown sku {sku}")
    for sku in m.get("products", []):
        if sku not in case.product_skus:
            errs.append(f"missing matrix sku {sku}")
    if m.get("event") and case.event_id != m["event"]:
        errs.append(f"event_id should be {m['event']}")
    if case.event_id and not event(case.event_id):
        errs.append(f"unknown event {case.event_id}")
    for msg in case.conversation_history:
        if msg.time[:10] > case.today:
            errs.append(f"message after today: {msg.time}")
    if not case.test_meta or not {"persona", "type", "must", "must_not"} <= set(case.test_meta):
        errs.append("test_meta incomplete")
    print(f"{cid}: {'OK' if not errs else 'ERR ' + '; '.join(errs)}")
    bad += bool(errs)
print(f"\n{len(ids) - bad}/{len(ids)} valid")
sys.exit(1 if bad else 0)
