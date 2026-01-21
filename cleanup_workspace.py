# 軽い整理スクリプト：__pycache__ や .pyc、ログの一括移動
from pathlib import Path
ROOT = Path(__file__).parent
ARCH = ROOT / "archive"
ARCH.mkdir(exist_ok=True)

def archive_unused():
    moved = 0
    patterns = ["__pycache__", "*.pyc", "output_encode", "output_decode"]
    for p in ROOT.iterdir():
        if p.is_dir() and p.name == "__pycache__":
            dest = ARCH / p.name
            p.rename(dest)
            moved += 1
        if p.is_file() and (p.suffix == ".pyc" or p.name in patterns):
            try:
                p.rename(ARCH / p.name)
                moved += 1
            except Exception:
                pass
    return moved

if __name__ == "__main__":
    print("moved:", archive_unused())
