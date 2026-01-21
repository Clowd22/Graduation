# makemidi_adaptive のコピーを基に、キーフレーム音の duration を微小にずらす（+1 tick）実装
from mido import Message, MidiFile, MidiTrack, MetaMessage
import os

# ---------------------------
# 音階・基準設定 (エンコーダと一致)
# ---------------------------
NOTE_NAMES = ["G3", "A3", "B3", "C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
NOTE_TO_MIDI = {
    "G3": 55, "A3": 57, "B3": 59,
    "C4": 60, "D4": 62, "E4": 64, "F4": 65,
    "G4": 67, "A4": 69, "B4": 71, "C5": 72
}

RELATIVE_WEIGHTS = [1, 2, 3, 3, 3, 2, 1, 1]

DURATION_TABLE = {
    "00": 480,
    "01": 240,
    "10": 960,
    "11": 720
}

# キーフレーム設定
KEYFRAME_INTERVAL = 20
BASE_VELOCITY = 80
KEYFRAME_PHRASE = [
    ("D4", 240), ("E4", 240), ("A4", 240), ("A3", 240)
]
KEYFRAME_VELOCITY = BASE_VELOCITY
# 微小時間ずらし (ticks) を導入
KEYFRAME_DURATION_SHIFT = 1  # キーフレーム音は duration を +1 tick する

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

def print_mapping_verbose(prob_table, mapping, step, prev_note, chunk, pitch_bits_for_map, slot_index):
    print("\n--- ENCODE STEP (詳細) ---")
    print(f"Step {step} | prev_note={prev_note} | input_chunk={chunk} (pitch={chunk[:4]} dur={chunk[4:]})")
    print("確率分布:")
    for n, p in prob_table.items():
        print(f"  {n:<3}: {p:.4f} {'#'*int(p*40)}")
    print("4bit -> 音 のマッピング (index順):")
    for bits in sorted(mapping.keys(), key=lambda x: int(x,2)):
        mark = "<-- selected" if bits == pitch_bits_for_map else ""
        print(f"  {bits} -> {mapping[bits]:4s} {mark}")
    print(f"pitch_bits_for_map={pitch_bits_for_map} slot_index={slot_index}")

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

def main():
    import sys
    # stdin がパイプ/リダイレクトの場合は全入力を読み取り、
    # 「末尾の空でない行」を title、それ以前を text（改行を保持）とする。
    if not sys.stdin.isatty():
        raw = sys.stdin.read().splitlines()
        if len(raw) == 0:
            text = input("Enter text to encode in MIDI: ")
            title = input("Enter title for MIDI data: ")
        elif len(raw) == 1:
            text = raw[0]
            title = input("Enter title for MIDI data: ")
        else:
            idx = len(raw) - 1
            while idx >= 0 and raw[idx].strip() == "":
                idx -= 1
            title = raw[idx].strip()
            text = "\n".join(raw[:idx])
    else:
        # 対話モードで改行を含むテキストを入力できるようにする。
        print("Enter text to encode in MIDI. 終了は単独の '.' を入力して確定、Ctrl-D でも終了できます。")
        lines = []
        try:
            while True:
                line = input()
                if line == ".":
                    break
                lines.append(line)
        except EOFError:
            # Ctrl-D で終了
            pass
        text = "\n".join(lines).rstrip("\n")
        if text == "":
            # 空なら1行入力にフォールバック
            text = input("Empty input — Enter single-line text to encode: ")
        title = input("Enter title for MIDI data: ")

    # UTF-8 バイト列でエンコード（日本語・絵文字を正しく扱う）
    payload_bytes = text.encode('utf-8')
    # 先頭に元のバイト長を 4 バイト（big-endian）で付与しておく
    length_header = len(payload_bytes).to_bytes(4, 'big')
    bytes_data = length_header + payload_bytes
    binary_data = ''.join(f'{b:08b}' for b in bytes_data)
    chunks = [binary_data[i:i+6].ljust(6, '0') for i in range(0, len(binary_data), 6)]

    # DEBUG: エンコード情報出力（ビット・チャンク数・末尾チャンク）
    print(f"[ENCODE INFO] payload_bytes_len={len(payload_bytes)} total_bytes_len={len(bytes_data)} "
          f"binary_bits_len={len(binary_data)} chunks={len(chunks)} last_chunk={chunks[-1]!r}")

    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)

    prev_note = "C4"
    block_bits = ""
    notes_since_keyframe = 0
    print("\n=== Adaptive MIDI Encoding (timeshift keyframe) ===")

    for step, chunk in enumerate(chunks, 1):
        pitch_bits = chunk[:4]
        dur_bits = chunk[4:]
        pitch_bits_for_map = pitch_bits

        prob_table = make_probability_table(prev_note)
        mapping = make_mapping_from_prob_table(prob_table)

        candidates = [b for b, n in mapping.items() if n == mapping[pitch_bits_for_map]]
        candidates.sort(key=lambda x: int(x,2))
        try:
            slot_index = candidates.index(pitch_bits_for_map)
        except ValueError:
            slot_index = 0

        print_mapping_verbose(prob_table, mapping, step, prev_note, chunk, pitch_bits_for_map, slot_index)

        note_name = mapping[pitch_bits_for_map]
        duration = DURATION_TABLE[dur_bits]
        new_velocity = BASE_VELOCITY + slot_index
        if new_velocity > 127:
            new_velocity = 127

        note_num = NOTE_TO_MIDI[note_name]

        # decide whether THIS data note is the KEYFRAME (i.e. the N=KEYFRAME_INTERVAL-th note)
        is_keyframe_note = (notes_since_keyframe + 1) >= KEYFRAME_INTERVAL

        # append data note; if it's keyframe note, add duration shift to its note_off
        track.append(Message('note_on', note=note_num, velocity=new_velocity, time=0))
        off_time = duration + (KEYFRAME_DURATION_SHIFT if is_keyframe_note else 0)
        track.append(Message('note_off', note=note_num, velocity=0, time=off_time))

        # accumulate bits (include this 20th note's bits)
        block_bits += pitch_bits + dur_bits

        # update notes counter / handle keyframe action AFTER adding the 20th note
        notes_since_keyframe += 1
        if is_keyframe_note:
            crc = crc8_bits(block_bits)
            # emit SYNC text immediately after the shifted note_off
            last_note = note_name
            sync_text = f"SYNC:{step}:{last_note}:{crc:02X}"
            track.append(MetaMessage('text', text=sync_text, time=0))
            print(f"[SYNC(timeshift) WRITE] step={step} block_bits_len={len(block_bits)} crc={crc:02X} keyframe_note={last_note} text='{sync_text}'")
            block_bits = ""
            notes_since_keyframe = 0

        prev_note = note_name

    output_dir = "mid"
    os.makedirs(output_dir, exist_ok=True)
    # タイトルにすでに "_timeshift" が含まれている場合は重複させない
    if title.endswith("_timeshift"):
        out_basename = f"{title}.mid"
    else:
        out_basename = f"{title}_timeshift.mid"
    output_filename = os.path.join(output_dir, out_basename)
    mid.save(output_filename)
    print(f"\nMIDI saved: {output_filename}")

if __name__ == "__main__":
    main()
