# 共通定義・パス
from pathlib import Path
import os

ROOT = Path(__file__).parent
MID_DIR = ROOT / "mid"
ARTIFACTS_DIR = ROOT / "artifacts"
ENCODERS_DIR = ROOT

MID_DIR.mkdir(exist_ok=True)
ARTIFACTS_DIR.mkdir(exist_ok=True)

ENCODER_SCRIPT = "makemidi_adaptive_timeshift.py"
DECODER_SCRIPT = "decode_adaptive_timeshift_decode.py"

SAMPLE_TEXTS = [
    "Hello",
    "The quick brown fox jumps over the lazy dog",
    "Some sample text for testing,but its length is not too long.",
    "これは日本語のテストです。",
    "短い",
    # 長いサンプルは必要に応じてここに入れる
    "日本国民は、正当に選挙された国会における代表者を通じて行動し、われらとわれらの子孫のために、諸国民との協和による成果と、わが国全土にわたつて自由のもたらす恵沢を確保し、政府の行為によつて再び戦争の惨禍が起ることのないやうにすることを決意し、ここに主権が国民に存することを宣言し、この憲法を確定する。",
    "Emoji test 👍🚀🎵",
]

def script_path(name: str):
    return str((ROOT / name).resolve())
