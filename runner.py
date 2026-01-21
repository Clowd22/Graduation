# 実行ラッパー（エンコーダ/デコーダ呼び出し・ログ保存・テスト実行）

import subprocess
import sys
import os
from pathlib import Path
from midi_shared import ROOT, MID_DIR, ARTIFACTS_DIR, ENCODER_SCRIPT, DECODER_SCRIPT

def run_script(script_name, stdin_text, cwd=ROOT):
    proc = subprocess.run([sys.executable, str(Path(cwd) / script_name)],
                          input=stdin_text, text=True,
                          capture_output=True, cwd=str(cwd))
    return proc

def save_log(kind, basename, stdout, stderr):
    p = ARTIFACTS_DIR / f"{basename}_{kind}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"--- STDOUT ---\n{stdout}\n\n--- STDERR ---\n{stderr}\n")
    return str(p)

def encode_text(text, out_basename):
    # normalize basename: avoid duplicate "_timeshift" suffix
    suffix = "_timeshift"
    if out_basename.endswith(suffix):
        base = out_basename[:-len(suffix)]
    else:
        base = out_basename
    enc = run_script(ENCODER_SCRIPT, f"{text}\n{base}\n")
    # save logs under the final expected basename (base + suffix)
    save_log("encode", base + suffix, enc.stdout, enc.stderr)
    return enc

def decode_mid(mid_basename):
    dec = run_script(DECODER_SCRIPT, f"{mid_basename}\n")
    save_log("decode", mid_basename, dec.stdout, dec.stderr)
    return dec

def run_test_samples(samples):
    results = []
    for i, text in enumerate(samples, start=1):
        basename = f"testcase_{i:02d}_timeshift"
        enc = encode_text(text, basename)
        if enc.returncode != 0:
            results.append((text, False, "encoder_failed"))
            continue
        # extract saved mid name (same extraction logic as earlier)
        import re
        m = re.search(r"MIDI saved:\s*(?:mid/)?([^\s]+\.mid)", enc.stdout)
        saved_mid = m.group(1) if m else f"{basename}.mid"
        dec = decode_mid(Path(saved_mid).stem)
        if dec.returncode != 0:
            results.append((text, False, "decoder_failed"))
            continue
        # extract decoded text
        m2 = re.search(r"復号テキスト:\s*(.*)", dec.stdout)
        decoded = (m2.group(1).strip() if m2 else dec.stdout.strip().splitlines()[-1])
        ok = decoded == text
        results.append((text, ok, decoded))
    return results
