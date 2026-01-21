from mido import MidiFile, tick2second
import sys
import os

NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"

def inspect(path):
    mid = MidiFile(path)
    # find first tempo (microseconds per beat); default 500000
    tempo = 500000
    for track in mid.tracks:
        for m in track:
            if m.type == 'set_tempo':
                tempo = m.tempo
                break
        if tempo != 500000:
            break

    print(f"file: {path}  ticks_per_beat={mid.ticks_per_beat} tempo={tempo} (usec/beat)")
    print("track idx | on_idx | note | name  | vel | dur_ticks | dur_sec")
    for ti, track in enumerate(mid.tracks):
        cum = 0
        # collect messages with their cumulative time
        msgs = []
        for m in track:
            cum += getattr(m, "time", 0)
            msgs.append((m, cum))
        # scan for note_on and matching off
        for i, (m, on_time) in enumerate(msgs):
            if getattr(m, "type", None) == "note_on" and getattr(m, "velocity", 0) > 0:
                note = getattr(m, "note", None)
                vel = getattr(m, "velocity", 0)
                # find matching note_off or note_on vel=0
                off_time = None
                for j in range(i+1, len(msgs)):
                    mm, t = msgs[j]
                    if (getattr(mm, "type", None) == "note_off" and getattr(mm, "note", None) == note) or \
                       (getattr(mm, "type", None) == "note_on" and getattr(mm, "velocity", 0) == 0 and getattr(mm, "note", None) == note):
                        off_time = t
                        break
                if off_time is None:
                    continue
                dur_ticks = off_time - on_time
                dur_sec = tick2second(dur_ticks, mid.ticks_per_beat, tempo)
                print(f"{ti:9d} | {i:6d} | {note:4d} | {note_name(note):4s} | {vel:3d} | {dur_ticks:9d} | {dur_sec:7.3f}")

def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        base = input("MIDIファイルパス（または basename を mid/ の下で指定）: ").strip()
        if not base:
            print("中止")
            return
        if not base.lower().endswith('.mid'):
            candidate = os.path.join("mid", f"{base}.mid")
            if os.path.exists(candidate):
                path = candidate
            else:
                path = base  # try as given
        else:
            path = base
    if not os.path.exists(path):
        print("ファイルが見つかりません:", path)
        return
    inspect(path)

if __name__ == "__main__":
    main()
