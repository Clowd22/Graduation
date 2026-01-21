from mido import MidiFile
import os
import sys

# --- 設定（エンコードと一致させること） ---
NOTE_NAMES = ["G3", "A3", "B3", "C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
NOTE_TO_MIDI = {
    "G3": 55, "A3": 57, "B3": 59,
    "C4": 60, "D4": 62, "E4": 64, "F4": 65,
    "G4": 67, "A4": 69, "B4": 71, "C5": 72
}
MIDI_TO_NOTE = {v: k for k, v in NOTE_TO_MIDI.items()}

RELATIVE_WEIGHTS = [1, 2, 3, 3, 3, 2, 1, 1]  # -3..+4

DURATION_TABLE = {
    "00": 480,   # 4分音符
    "01": 240,   # 8分音符
    "10": 960,   # 2分音符
    "11": 720    # 付点4分音符
}

# キーフレーム関連（エンコーダと一致）
KEYFRAME_INTERVAL = 20
BASE_VELOCITY = 80
# timeshift エンコーダで使ったフレーズと shift
KEYFRAME_PHRASE = [
    ("D4", 240),
    ("E4", 240),
    ("A4", 240),
    ("A3", 240)
]
# エンコーダでの微小ずらし量（ticks）
KEYFRAME_DURATION_SHIFT = 1

# --- ヘルパ ---
def make_probability_table(prev_note):
    if prev_note not in NOTE_NAMES:
        prev_note = "C4"
    center_index = NOTE_NAMES.index(prev_note)
    prob_table = {}
    for offset, weight in enumerate(RELATIVE_WEIGHTS):
        rel_idx = offset - 3
        target_index = center_index + rel_idx
        if 0 <= target_index < len(NOTE_NAMES):
            note = NOTE_NAMES[target_index]
            prob_table[note] = prob_table.get(note, 0) + weight
    total = sum(prob_table.values()) or 1
    for k in list(prob_table.keys()):
        prob_table[k] = prob_table[k] / total
    return prob_table

def make_mapping_from_prob_table(prob_table):
    notes = []
    for note in NOTE_NAMES:
        prob = prob_table.get(note, 0)
        if prob <= 0:
            continue
        count = max(1, round(prob * 16))
        notes.extend([note] * count)
    while len(notes) < 16:
        notes.append(list(prob_table.keys())[len(prob_table)//2])
    notes = notes[:16]
    return {format(i, '04b'): notes[i] for i in range(16)}

def select_slot_from_velocity(note_name, mapping, velocity):
    candidates = [bits for bits, n in mapping.items() if n == note_name]
    candidates.sort(key=lambda x: int(x, 2))
    if not candidates:
        return None
    vel_index = velocity - BASE_VELOCITY
    if vel_index < 0:
        vel_index = 0
    idx = vel_index % len(candidates)
    return candidates[idx]

def crc8_bits(bitstr):
    if len(bitstr) % 8 != 0:
        bitstr = bitstr + '0' * (8 - (len(bitstr) % 8))
    data = [int(bitstr[i:i+8], 2) for i in range(0, len(bitstr), 8)]
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) & 0xFF) ^ 0x07
            else:
                crc = (crc << 1) & 0xFF
    return crc

# find paired note_off index and compute duration_ticks
def find_note_duration_and_off_index(all_msgs, start_idx):
    msg_len = len(all_msgs)
    accum = 0
    note_num = getattr(all_msgs[start_idx], "note", None)
    for j in range(start_idx + 1, msg_len):
        m = all_msgs[j]
        accum += getattr(m, "time", 0)
        if (getattr(m, "type", None) == "note_off" and getattr(m, "note", None) == note_num) or \
           (getattr(m, "type", None) == "note_on" and getattr(m, "velocity", 0) == 0 and getattr(m, "note", None) == note_num):
            return accum, j
    return None, None

# キーフレーズ（timeshift考慮）検出
def find_keyframe_block(all_msgs, start_idx):
    """
    start_idx に note_on があり、そこから KEYFRAME_PHRASE と同じノート列が連続して存在し、
    各ノートの duration が expected または expected+KEYFRAME_DURATION_SHIFT のいずれかに一致し、
    その直後に SYNC テキストがあれば (set_of_indices_to_skip, sync_index, reported_sync_text) を返す。
    """
    if not KEYFRAME_PHRASE:
        return None
    msg_len = len(all_msgs)
    needed = [NOTE_TO_MIDI[n] for n, _ in KEYFRAME_PHRASE]
    found_note_on_idxs = []
    i = start_idx
    # collect next note_on events (allow intervening non-text messages like delta-time/note_off, but require ordering)
    while i < msg_len and len(found_note_on_idxs) < len(needed):
        m = all_msgs[i]
        if getattr(m, "type", None) == "note_on" and getattr(m, "velocity", 0) > 0:
            found_note_on_idxs.append(i)
        elif getattr(m, "type", None) == "text":
            # stray text before finishing -> abort
            return None
        i += 1
    if len(found_note_on_idxs) != len(needed):
        return None
    # check note numbers match expected order
    for idx, expect in zip(found_note_on_idxs, needed):
        if getattr(all_msgs[idx], "note", None) != expect:
            return None
    # for each found note, verify duration equals expected or expected+shift (allow tolerance 0)
    off_indices = []
    durations_ok = True
    for on_idx, (phrase_note, phrase_dur) in zip(found_note_on_idxs, KEYFRAME_PHRASE):
        dur_ticks, off_idx = find_note_duration_and_off_index(all_msgs, on_idx)
        if off_idx is None:
            durations_ok = False
            break
        # allow exact match to phrase_dur or phrase_dur + KEYFRAME_DURATION_SHIFT
        if not (dur_ticks == phrase_dur or dur_ticks == phrase_dur + KEYFRAME_DURATION_SHIFT):
            durations_ok = False
            break
        off_indices.append(off_idx)
    if not durations_ok:
        return None
    last_off = off_indices[-1] if off_indices else found_note_on_idxs[-1]
    # find SYNC text soon after last_off
    for j in range(last_off + 1, min(last_off + 1 + 64, msg_len)):
        m = all_msgs[j]
        if getattr(m, "type", None) == "text" and isinstance(getattr(m, "text", None), str) and m.text.startswith("SYNC:"):
            # return set of indices to skip (all involved note_on and their offs) and sync index and sync text
            skip_set = set(found_note_on_idxs) | set(off_indices)
            return skip_set, j, m.text
    return None

# デバッグ出力（簡潔）
VERBOSE = True
def print_decode_verbose(*args, **kwargs):
    # timeshift 用デコーダでは詳細表示は不要なので無害なダミーにする
    return

# --- メイン ---
def main():
    name = input("解析するMIDIファイル名を入力してください（拡張子 .mid は不要）: ")
    path = os.path.join("mid", f"{name}.mid")
    if not os.path.exists(path):
        print(f"ファイルが見つかりません: {path}")
        return

    mid = MidiFile(path)
    prev_note = "C4"
    step = 1
    bit_string = ""

    # flatten all messages (preserve relative times)
    all_msgs = []
    for tr in mid.tracks:
        all_msgs.extend(tr)
    msg_len = len(all_msgs)

    block_bits_accum = ""
    skip_indices = set()
    idx = 0
    while idx < msg_len:
        msg = all_msgs[idx]
        if idx in skip_indices:
            idx += 1
            continue

        # only process note_on with velocity>0
        if getattr(msg, "type", None) != "note_on" or getattr(msg, "velocity", 0) == 0:
            idx += 1
            continue

        # compute duration (find corresponding note_off)
        dur_ticks, off_idx = find_note_duration_and_off_index(all_msgs, idx)
        if dur_ticks is None:
            dur_ticks = 0

        note_num = getattr(msg, "note", None)
        velocity = getattr(msg, "velocity", 0)
        note_name = MIDI_TO_NOTE.get(note_num)
        if note_name is None:
            idx += 1
            continue

        # reconstruct mapping and select slot
        prob_table = make_probability_table(prev_note)
        mapping = make_mapping_from_prob_table(prob_table)
        selected_bits = select_slot_from_velocity(note_name, mapping, velocity)
        if selected_bits is None:
            print(f"[Step {step}] slot 選択失敗: note_name={note_name}")
            idx += 1
            continue
        data4 = selected_bits
        # round duration to nearest 2bit code
        closest = min(DURATION_TABLE.items(), key=lambda kv: abs(kv[1] - dur_ticks))
        dur_bits = closest[0]

        full_bits = data4 + dur_bits
        bit_string += full_bits
        # append to block accumulator for SYNC CRC
        block_bits_accum += full_bits

        # check whether this note is a timeshift keyframe marker:
        # if dur_ticks equals some canonical duration + KEYFRAME_DURATION_SHIFT, and a SYNC meta follows the note_off,
        # then treat SYNC as block boundary. The note itself remains part of data (we already added its bits).
        is_keyframe_marker = False
        for code, base_dur in DURATION_TABLE.items():
            if dur_ticks == base_dur + KEYFRAME_DURATION_SHIFT:
                # check for SYNC text shortly after off_idx
                if off_idx is not None:
                    for j in range(off_idx + 1, min(off_idx + 1 + 64, msg_len)):
                        m = all_msgs[j]
                        if getattr(m, "type", None) == "text" and isinstance(getattr(m, "text", None), str) and m.text.startswith("SYNC:"):
                            # validate CRC on block_bits_accum (which currently includes this note)
                            parts = m.text.split(":", 3)
                            if len(parts) >= 4:
                                _, s_step, s_note, s_crc = parts
                                print(f"[Keyframe+SYNC READ] step={s_step} prev_note を {s_note} に同期、reported_crc={s_crc}")
                                actual_crc = crc8_bits(block_bits_accum)
                                try:
                                    reported_crc = int(s_crc, 16)
                                except:
                                    reported_crc = None
                                print(f"  block_bits_len={len(block_bits_accum)} actual_crc={actual_crc:02X}")
                                if reported_crc is not None and actual_crc != reported_crc:
                                    print(f"  CRC MISMATCH! reported={reported_crc:02X} actual={actual_crc:02X}")
                                elif reported_crc is not None:
                                    print("  CRC OK")
                            # consume the SYNC meta (skip its index)
                            skip_indices.add(j)
                            # synchronize prev_note to reported note (or leave as current)
                            try:
                                prev_note = s_note
                            except:
                                prev_note = note_name
                            # reset block accumulator after handling
                            block_bits_accum = ""
                            is_keyframe_marker = True
                            break
                break

        print(f"[Step {step}] decoded note={note_name} dur={dur_ticks} vel={velocity} -> bits={full_bits}")
        prev_note = note_name
        step += 1
        idx += 1

    # パディング方針：末尾の不完全バイトはゼロでパディングして復元する
    rem = len(bit_string) % 8
    print(f"[DECODE INFO] bit_string_len={len(bit_string)} rem={rem} (last32={bit_string[-32:]!r})")
    if rem != 0:
        pad = 8 - rem
        print(f"[INFO] 末尾の不完全なビットを{rem}個検出、{pad}個の'0'でパディングして復号します")
        bit_string = bit_string + '0' * pad
    bytes_list = [int(bit_string[i:i+8], 2) for i in range(0, len(bit_string), 8)]
    try:
        reconstructed_bytes = bytes(bytes_list)
    except Exception:
        reconstructed_bytes = b"".join(bytes([b]) for b in bytes_list)

    print(f"[DECODE INFO] reconstructed_bytes_len={len(reconstructed_bytes)} "
          f"first4={reconstructed_bytes[:4].hex()} last4={reconstructed_bytes[-4:].hex()}")
    # ヘッダ付き出力を想定: 先頭4バイトが元データ長 (big-endian)
    if len(reconstructed_bytes) >= 4:
        expected_len = int.from_bytes(reconstructed_bytes[:4], 'big')
        print(f"[DECODE INFO] expected_payload_len={expected_len} available={len(reconstructed_bytes)-4}")
        # 期待長が手元のバイト数内に収まればその分だけ取り出す。足りなければ残りをデコード。
        if expected_len <= len(reconstructed_bytes) - 4:
            payload = reconstructed_bytes[4:4 + expected_len]
        else:
            payload = reconstructed_bytes[4:]
        decoded_text = payload.decode('utf-8', errors='replace')
    else:
        decoded_text = reconstructed_bytes.decode('utf-8', errors='replace')
    # 修正箇所: エラーが出ても無理やり表示させる
    import sys
    try:
        # コンソールで表示できない文字は '?' などに置き換えて表示
        safe_text = decoded_text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(f"復号テキスト: {safe_text}")
    except Exception as e:
        print(f"テキスト表示エラー: {e}")
        print(f"生データ(Hex): {decoded_text.encode('utf-8', errors='replace').hex()}")

if __name__ == "__main__":
    main()
