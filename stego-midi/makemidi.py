from mido import Message, MidiFile, MidiTrack
import math

NOTE_NAMES = ["G3", "A3", "B3", "C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
NOTE_TO_MIDI = {
    "G3": 55 + 12, "A3": 57 + 12, "B3": 59 + 12,
    "C4": 60 + 12, "D4": 62 + 12, "E4": 64 + 12, "F4": 65 + 12,
    "G4": 67 + 12, "A4": 69 + 12, "B4": 71 + 12, "C5": 72 + 12
}
RELATIVE_WEIGHTS = [1, 2, 3, 3, 3, 2, 1, 1]
DURATION_TABLE = {
    "00": 480,
    "01": 240,
    "10": 960,
    "11": 720
}

# pitch_table は 3bit→MIDIノートの対応が必要なので NOTE_NAMES の先頭8音を使用
pitch_table = {format(i, "03b"): NOTE_TO_MIDI[n] for i, n in enumerate(NOTE_NAMES[:8])}

# 入力文字列とバイナリ変換
text = input("Enter text to encode in MIDI: ")
title = input("Enter title for the MIDI file: ")
binary_data = ''.join(f'{ord(c):08b}' for c in text)
chunks = [binary_data[i:i+5].ljust(5, '0') for i in range(0, len(binary_data), 5)]

# MIDIファイル作成
mid = MidiFile()
track = MidiTrack()
mid.tracks.append(track)

base_velocity = 80  # 1010000

time = 0
for chunk in chunks:
    pitch_bits = chunk[:3]
    velocity_bits = chunk[3:]

    note = pitch_table[pitch_bits]

    # ベロシティの下位2bitを差し替え
    velocity_bin = format(base_velocity, '07b')
    new_velocity_bin = velocity_bin[:5] + velocity_bits
    new_velocity = int(new_velocity_bin, 2)

    # ノートオン・オフ
    track.append(Message('note_on', note=note, velocity=new_velocity, time=time))
    track.append(Message('note_off', note=note, velocity=0, time=240))  # 240 ticks later

# 保存
mid.save(f"{title}.mid")
