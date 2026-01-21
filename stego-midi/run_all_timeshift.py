import subprocess
import sys
import os
import re

SAMPLE_TEXT = "日本国民は、正当に選挙された国会における代表者を通じて行動し、われらとわれらの子孫のために、諸国民との協和による成果と、わが国全土にわたつて自由のもたらす恵沢を確保し、政府の行為によつて再び戦争の惨禍が起ることのないやうにすることを決意し、ここに主権が国民に存することを宣言し、この憲法を確定する。そもそも国政は、国民の厳粛な信託によるものであつて、その権威は国民に由来し、その権力は国民の代表者がこれを行使し、その福利は国民がこれを享受する。これは人類普遍の原理であり、この憲法は、かかる原理に基くものである。われらは、これに反する一切の憲法、法令及び詔勅を排除する。日本国民は、恒久の平和を念願し、人間相互の関係を支配する崇高な理想を深く自覚するのであつて、平和を愛する諸国民の公正と信義に信頼して、われらの安全と生存を保持しようと決意した。われらは、平和を維持し、専制と隷従、圧迫と偏狭を地上から永遠に除去しようと努めてゐる国際社会において、名誉ある地位を占めたいと思ふ。われらは、全世界の国民が、ひとしく恐怖と欠乏から免かれ、平和のうちに生存する権利を有することを確認する。われらは、いづれの国家も、自国のことのみに専念して他国を無視してはならないのであつて、政治道徳の法則は、普遍的なものであり、この法則に従ふことは、自国の主権を維持し、他国と対等関係に立たうとする各国の責務であると信ずる。日本国民は、国家の名誉にかけ、全力をあげてこの崇高な理想と目的を達成することを誓ふ。"
TITLE = "auto_sample_timeshift"

SCRIPT_DIR = os.path.dirname(__file__)

# エンコーダ候補を timeshift のみに絞る
ENCODERS = [
    ("timeshift", "makemidi_adaptive_timeshift.py", f"{TITLE}_timeshift", "decode_adaptive_timeshift_decode.py"),
]

def run_script(script_path, stdin_text):
    proc = subprocess.run([sys.executable, script_path],
                          input=stdin_text, text=True,
                          capture_output=True, cwd=SCRIPT_DIR)
    return proc

def main():
    for label, enc_name, out_basename, dec_name in ENCODERS:
        enc_path = os.path.join(SCRIPT_DIR, enc_name)
        if not os.path.isfile(enc_path):
            print(f"[SKIP] エンコーダが見つかりません: {enc_name}")
            continue
        print(f"\n>>> 実行: {enc_name} ({label}) -> 出力: mid/{out_basename}.mid")
        enc_proc = run_script(enc_path, f"{SAMPLE_TEXT}\n{out_basename}\n")
        print(f"[{enc_name}] returncode: {enc_proc.returncode}")
        # 出力をコンソール表示すると同時にファイルに保存
        encoder_out_path = os.path.join(SCRIPT_DIR, "output_encode")
        encoder_out_midpath = os.path.join(SCRIPT_DIR, "mid", f"{out_basename}_output_encode.txt")
        try:
            with open(encoder_out_path, "w", encoding="utf-8") as f:
                f.write(f"--- STDOUT ---\n{enc_proc.stdout}\n--- STDERR ---\n{enc_proc.stderr}\n")
        except Exception:
            pass
        try:
            with open(encoder_out_midpath, "w", encoding="utf-8") as f:
                f.write(f"--- STDOUT ---\n{enc_proc.stdout}\n--- STDERR ---\n{enc_proc.stderr}\n")
        except Exception:
            pass
        if enc_proc.stdout:
            print(f"---- {enc_name} stdout ----")
            print(enc_proc.stdout)
        if enc_proc.stderr:
            print(f"---- {enc_name} stderr ----")
            print(enc_proc.stderr)

        # 実際に保存された MIDI ファイル名を stdout から抽出
        saved_basename = None
        if enc_proc.stdout:
            m = re.search(r"MIDI saved:\s*(?:mid/)?([^\s]+\.mid)", enc_proc.stdout)
            if m:
                fname = m.group(1)
                saved_basename = os.path.splitext(fname)[0]

        if saved_basename is None:
            # フォールバック: ENCODERS に定義した out_basename を使う
            saved_basename = out_basename

        # デコーダ実行（抽出した basename を渡す）
        dec_path = os.path.join(SCRIPT_DIR, dec_name)
        if not os.path.isfile(dec_path):
            print(f"[SKIP] デコーダが見つかりません: {dec_name}")
            continue
        print(f">>> デコード実行: {dec_name} に mid/{saved_basename}.mid を渡します")
        dec_proc = run_script(dec_path, f"{saved_basename}\n")
        print(f"[{dec_name}] returncode: {dec_proc.returncode}")
        # デコーダ出力もファイルへ
        decoder_out_path = os.path.join(SCRIPT_DIR, "output_decode")
        decoder_out_midpath = os.path.join(SCRIPT_DIR, "mid", f"{saved_basename}_output_decode.txt")
        try:
            with open(decoder_out_path, "w", encoding="utf-8") as f:
                f.write(f"--- STDOUT ---\n{dec_proc.stdout}\n--- STDERR ---\n{dec_proc.stderr}\n")
        except Exception:
            pass
        try:
            with open(decoder_out_midpath, "w", encoding="utf-8") as f:
                f.write(f"--- STDOUT ---\n{dec_proc.stdout}\n--- STDERR ---\n{dec_proc.stderr}\n")
        except Exception:
            pass
        if dec_proc.stdout:
            print(f"---- {dec_name} stdout ----")
            print(dec_proc.stdout)
        if dec_proc.stderr:
            print(f"---- {dec_name} stderr ----")
            print(dec_proc.stderr)

        # 簡易検査スクリプト（保存して実行）
        from mido import MidiFile
        from pathlib import Path

        # ここを実際の basename に合わせる（.mid は不要）
        BASENAME = "auto_sample_timeshift_timeshift"  # run_all_timeshift の out_basename に合わせて変更
        path = Path("mid") / f"{BASENAME}.mid"
        if not path.exists():
            print("MIDI が見つかりません:", path)
            raise SystemExit(1)

        mid = MidiFile(path)
        all_msgs = []
        for tr in mid.tracks:
            all_msgs.extend(tr)

        DURATION_TABLE = {480:"00", 240:"01", 960:"10", 720:"11"}
        shift = 1

        print("index | type | note | vel | time | cum_time | info")
        cum = 0
        idx = 0
        for m in all_msgs:
            cum += getattr(m, "time", 0)
            if m.type == "note_on" and getattr(m, "velocity", 0) > 0:
                # find off index and duration
                accum = 0
                off_idx = None
                note_num = m.note
                for j in range(idx+1, len(all_msgs)):
                    accum += getattr(all_msgs[j], "time", 0)
                    mm = all_msgs[j]
                    if (getattr(mm, "type", None) == "note_off" and getattr(mm, "note", None) == note_num) or \
                       (getattr(mm, "type", None) == "note_on" and getattr(mm, "velocity", 0) == 0 and getattr(mm, "note", None) == note_num):
                        off_idx = j
                        break
                # detect if duration equals base + shift
                shifted = None
                for base in DURATION_TABLE:
                    if accum == base + shift:
                        shifted = f"{DURATION_TABLE[base]}(+{shift})"
                        break
                print(f"{idx:4d} | note_on | {note_num:3d} | {m.velocity:3d} | time={m.time:3d} | cum={cum:4d} | dur={accum} {shifted or ''}")
            elif m.type == "meta" and m.type == "text":
                print(f"{idx:4d} | meta text |      |     | time={m.time:3d} | cum={cum:4d} | text='{m.text}'")
            idx += 1

        # 追加チェック: SHIFTed note が見つかったらその直後に SYNC があるか表示
        print("\n-- SHIFTED notes and following messages --")
        for i, m in enumerate(all_msgs):
            if getattr(m, "type", None) == "note_on" and getattr(m, "velocity", 0) > 0:
                dur, off = None, None
                accum = 0
                note_num = m.note
                for j in range(i+1, len(all_msgs)):
                    accum += getattr(all_msgs[j], "time", 0)
                    mm = all_msgs[j]
                    if (getattr(mm, "type", None) == "note_off" and getattr(mm, "note", None) == note_num) or \
                       (getattr(mm, "type", None) == "note_on" and getattr(mm, "velocity", 0) == 0 and getattr(mm, "note", None) == note_num):
                        off = j
                        break
                for base in (480,240,960,720):
                    if accum == base + shift:
                        print(f"note_on idx={i} note={note_num} dur={accum} (base {base}+{shift}) -> off_idx={off}")
                        # print next few msgs
                        for k in range(off+1, min(off+6, len(all_msgs))):
                            mm = all_msgs[k]
                            print("   ->", k, mm)
                        break

if __name__ == "__main__":
    main()

