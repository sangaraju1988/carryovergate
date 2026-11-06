"""Pick the pilot subset: 10 cases per environment, seeded, from sorted case ids.
Run once before the pilot; the output file is committed with the preregistration."""
import argparse
import json
import random
from pathlib import Path

SEED = 20261106
PER_ENV = 10
ENVS = ("devops", "marketplace", "productivity")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="benchmark data/test_cases dir")
    ap.add_argument("--out", default="eval/pilot_cases.json")
    a = ap.parse_args()
    rng = random.Random(SEED)
    sel = {}
    for env in ENVS:
        ids = sorted(p.stem for p in (Path(a.data) / env).glob("*.json"))
        sel[env] = sorted(rng.sample(ids, PER_ENV))
    Path(a.out).write_text(json.dumps({"seed": SEED, "per_env": PER_ENV, "cases": sel}, indent=1) + "\n")
    print(json.dumps(sel))


if __name__ == "__main__":
    main()
