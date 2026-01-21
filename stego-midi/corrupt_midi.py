import mido
import random
import os

# 破壊したいファイル
filename = "auto_sample_timeshift.mid" # 生成済みのファイル名
input_path = os.path.join("mid", filename)
output_path = os.path.join("mid", "corrupted_" + filename)

mid = mido.MidiFile(input_path)

# ランダムに1つのノートの音程をズラす
target_track = mid.tracks[0] # トラック0と仮定
note_events = [msg for msg in target_track if msg.type == 'note_on' and msg.velocity > 0]

if note_events:
    target_msg = random.choice(note_events)
    original_note = target_msg.note
    # 音程を適当に変える (+1)
    target_msg.note = (original_note + 1) % 128
    print(f"破壊しました: Note {original_note} -> {target_msg.note}")

mid.save(output_path)
print(f"保存しました: {output_path}")