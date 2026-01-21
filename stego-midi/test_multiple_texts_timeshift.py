import subprocess
import sys
import os
import re
import tempfile
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ENCODER = "makemidi_adaptive_timeshift.py"
DECODER = "decode_adaptive_timeshift_decode.py"
MID_DIR = SCRIPT_DIR / "mid"
MID_DIR.mkdir(exist_ok=True)

SAMPLES = [
    "Hello",
    "The quick brown fox jumps over the lazy dog",
    "Some sample text for testing,but its length is not too long.",
    "これは日本語のテストです。",
    "短い",
    "日本国民は、正当に選挙された国会における代表者を通じて行動し、われらとわれらの子孫のために、諸国民との協和による成果と、わが国全土にわたつて自由のもたらす恵沢を確保し、政府の行為によつて再び戦争の惨禍が起ることのないやうにすることを決意し、ここに主権が国民に存することを宣言し、この憲法を確定する。そもそも国政は、国民の厳粛な信託によるものであつて、その権威は国民に由来し、その権力は国民の代表者がこれを行使し、その福利は国民がこれを享受する。これは人類普遍の原理であり、この憲法は、かかる原理に基くものである。われらは、これに反する一切の憲法、法令及び詔勅を排除する。日本国民は、恒久の平和を念願し、人間相互の関係を支配する崇高な理想を深く自覚するのであつて、平和を愛する諸国民の公正と信義に信頼して、われらの安全と生存を保持しようと決意した。われらは、平和を維持し、専制と隷従、圧迫と偏狭を地上から永遠に除去しようと努めてゐる国際社会において、名誉ある地位を占めたいと思ふ。われらは、全世界の国民が、ひとしく恐怖と欠乏から免かれ、平和のうちに生存する権利を有することを確認する。われらは、いづれの国家も、自国のことのみに専念して他国を無視してはならないのであつて、政治道徳の法則は、普遍的なものであり、この法則に従ふことは、自国の主権を維持し、他国と対等関係に立たうとする各国の責務であると信ずる。日本国民は、国家の名誉にかけ、全力をあげてこの崇高な理想と目的を達成することを誓ふ。" ,
    "Emoji test 👍🚀🎵",
]

def run_script(script, stdin_text, cwd=SCRIPT_DIR):
    proc = subprocess.run([sys.executable, script], input=stdin_text, text=True,
                          capture_output=True, cwd=str(cwd))
    return proc

def extract_saved_mid(stdout, fallback_basename):
    m = re.search(r"MIDI saved:\s*(?:mid/)?([^\s]+\.mid)", stdout)
    if m:
        return m.group(1)
    return f"{fallback_basename}.mid"

def extract_decoded_text(dec_stdout):
    m = re.search(r"復号テキスト:\s*(.*)", dec_stdout)
    if m:
        return m.group(1).strip()
    # fallback: try last non-empty line
    lines = [l.strip() for l in dec_stdout.splitlines() if l.strip()]
    return lines[-1] if lines else ""

def main():
    results = []
    for i, text in enumerate(SAMPLES, start=1):
        basename = f"testcase_{i:02d}_timeshift"
        print(f"\n--- CASE {i} ---")
        print(f"原文: {repr(text)[:120]}")
        # run encoder
        enc_proc = run_script(ENCODER, f"{text}\n{basename}\n")
        if enc_proc.returncode != 0:
            print(f"[ENCODER ERROR] returncode={enc_proc.returncode}")
            print(enc_proc.stderr)
            results.append((text, False, "encoder_failed"))
            continue
        saved_mid = extract_saved_mid(enc_proc.stdout, basename)
        mid_path = MID_DIR / saved_mid
        if not mid_path.exists():
            # fallback path
            mid_path = MID_DIR / f"{basename}.mid"
        print(f"生成されたMIDI: {mid_path}")
        if not mid_path.exists():
            print("[ERROR] MIDIが見つかりません")
            results.append((text, False, "mid_missing"))
            continue

        # run decoder
        dec_proc = run_script(DECODER, f"{Path(saved_mid).stem}\n")
        if dec_proc.returncode != 0:
            print(f"[DECODER ERROR] returncode={dec_proc.returncode}")
            print(dec_proc.stderr)
            results.append((text, False, "decoder_failed"))
            continue
        decoded = extract_decoded_text(dec_proc.stdout)
        ok = decoded == text
        # 復号結果表示（簡潔）
        print(f"復号結果: {repr(decoded)[:120]}")
        if not ok:
            # 詳細デバッグ: 長さ・バイト列・差分位置を表示
            orig_bytes = text.encode('utf-8')
            dec_bytes = decoded.encode('utf-8', errors='replace')
            print("=== DIAGNOSTICS ===")
            print(f"orig_len={len(text)} dec_len={len(decoded)}")
            print(f"orig_bytes_len={len(orig_bytes)} dec_bytes_len={len(dec_bytes)}")
            # 最初の差分位置を探す
            min_len = min(len(orig_bytes), len(dec_bytes))
            diff_idx = None
            for j in range(min_len):
                if orig_bytes[j] != dec_bytes[j]:
                    diff_idx = j
                    break
            if diff_idx is None and len(orig_bytes) != len(dec_bytes):
                diff_idx = min_len
            if diff_idx is not None:
                context_start = max(0, diff_idx-8)
                context_end = min(len(orig_bytes), diff_idx+8)
                print(f"first diff at byte index: {diff_idx}")
                print("orig bytes context:", orig_bytes[context_start:context_end].hex())
                print("dec  bytes context:", dec_bytes[context_start:context_end].hex())
            else:
                print("No byte-level difference detected.")
            print("====================")
        print("MATCH" if ok else "MISMATCH")
        results.append((text, ok, decoded))

    # summary
    ok_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n=== SUMMARY ===")
    print(f"合格 {ok_count}/{total}")
    for i, (orig, ok, info) in enumerate(results, start=1):
        status = "OK" if ok else f"NG ({info})"
        print(f"{i:02d}: {status} orig_len={len(orig)}")

if __name__ == "__main__":
    main()
