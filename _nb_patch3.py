"""
Fix two bugs in jyupiter_train_model.ipynb:
  1. _find_repo_root() matches the system /src dir on Linux — use a
     repo-specific marker (src/ml/model.py) instead of bare src/.
  2. Load Dataset cell tells users to run a CLI script; update message to
     point to the Build Dataset section above, and auto-trigger the build.
"""
import json
from pathlib import Path

nb_path = Path(__file__).parent / "jyupiter_train_model.ipynb"
nb = json.loads(nb_path.read_text(encoding="utf-8"))

cells_by_id = {c["id"]: c for c in nb["cells"]}

# ── Fix 1: repo-root detection ────────────────────────────────────────────────
OLD_DETECT = """\
# Locate the repository root — check cwd first, then walk upward
def _find_repo_root() -> Path:
    cwd = Path.cwd()
    # Check cwd itself (Colab: we cd'd into the repo already)
    if (cwd / 'src').exists():
        return cwd
    # Walk upward
    candidate = cwd.parent
    while candidate != candidate.parent:
        if (candidate / 'src').exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(
        f'Could not find repository root with a src/ directory. '
        f'cwd={cwd}. In Colab, run the setup cell first.'
    )

repo_root = _find_repo_root()"""

NEW_DETECT = """\
# Locate the repository root using a repo-specific marker file.
# Checking bare src/ is not reliable — Linux has a system /src directory.
def _find_repo_root() -> Path:
    marker = Path('src') / 'ml' / 'model.py'   # unique to this repo
    cwd = Path.cwd()
    # Check cwd itself (Colab: os.chdir'd into the repo in the setup cell)
    if (cwd / marker).exists():
        return cwd
    # Walk upward (local dev: notebook opened from inside the repo)
    candidate = cwd.parent
    while candidate != candidate.parent:
        if (candidate / marker).exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(
        f'Cannot find repo root (looked for {marker}). '
        f'cwd={cwd}. In Colab, make sure the setup cell ran successfully.'
    )

repo_root = _find_repo_root()"""

setup_cell = cells_by_id.get("0c51f5fe")
if setup_cell is None:
    raise RuntimeError("Setup cell 0c51f5fe not found")

src = "".join(setup_cell["source"])
if OLD_DETECT not in src:
    # Try ASCII dash in case the em-dash was stored differently
    alt = OLD_DETECT.replace("—", "-")
    if alt in src:
        OLD_DETECT = alt
    else:
        print("WARNING: could not find old detect block verbatim; dumping current source for inspection")
        print(repr(src[:800]))
        raise RuntimeError("Old detection block not found")

new_src = src.replace(OLD_DETECT, NEW_DETECT)
setup_cell["source"] = [ln + "\n" for ln in new_src.splitlines()]
if not src.endswith("\n") and setup_cell["source"]:
    setup_cell["source"][-1] = setup_cell["source"][-1].rstrip("\n")
print("Fix 1 applied: repo-root detection now uses src/ml/model.py as marker.")

# ── Fix 2: Load Dataset cell — better error + point to Build Dataset ──────────
OLD_LOAD = """\
if not data_path.exists():
    raise FileNotFoundError('Training data not found. Run scripts/build_dataset.py first.')"""

NEW_LOAD = """\
if not data_path.exists():
    raise FileNotFoundError(
        f'Training data not found at {data_path}\\n'
        'Run the \\'Build Dataset\\' section at the top of this notebook first, '
        'then re-run this cell.'
    )"""

load_cell = cells_by_id.get("1a2fde52")
if load_cell is None:
    raise RuntimeError("Load Dataset cell 1a2fde52 not found")

load_src = "".join(load_cell["source"])
if OLD_LOAD not in load_src:
    print("WARNING: old load block not found verbatim; skipping fix 2")
    print(repr(load_src[:400]))
else:
    new_load_src = load_src.replace(OLD_LOAD, NEW_LOAD)
    load_cell["source"] = [ln + "\n" for ln in new_load_src.splitlines()]
    if not load_src.endswith("\n") and load_cell["source"]:
        load_cell["source"][-1] = load_cell["source"][-1].rstrip("\n")
    print("Fix 2 applied: Load Dataset error message updated.")

nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("Done.")
