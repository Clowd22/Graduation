import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from pathlib import Path
import re

from midi_shared import MID_DIR, ARTIFACTS_DIR, ENCODER_SCRIPT, DECODER_SCRIPT
from runner import encode_text, decode_mid

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MIDI My Sample — GUI")
        self.geometry("1000x700")
        self._build()

    def _build(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        btn_frame = tk.Frame(top)
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text="Open mid folder", command=self.open_mid_folder).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Open artifacts", command=self.open_artifacts).pack(side="left", padx=4)

        body = tk.PanedWindow(self, sashrelief="raised", sashwidth=6, orient="horizontal")
        body.pack(expand=True, fill="both", padx=8, pady=8)

        # --- Encode panel ---
        enc_frame = tk.LabelFrame(body, text="Encode: text → MIDI", padx=6, pady=6)
        body.add(enc_frame, stretch="always")

        tk.Label(enc_frame, text="Title (basename):").grid(row=0, column=0, sticky="w")
        self.enc_title = tk.Entry(enc_frame, width=40)
        self.enc_title.grid(row=0, column=1, sticky="we", padx=4, pady=2)
        self.enc_title.insert(0, "auto_sample_timeshift")

        tk.Label(enc_frame, text="Text to encode:").grid(row=1, column=0, sticky="nw")
        self.enc_text = scrolledtext.ScrolledText(enc_frame, width=60, height=12, wrap="word")
        self.enc_text.grid(row=1, column=1, sticky="nsew", padx=4)
        enc_frame.columnconfigure(1, weight=1)

        enc_btn = tk.Button(enc_frame, text="Encode → MIDI", command=self.on_encode)
        enc_btn.grid(row=2, column=1, sticky="e", pady=6)

        self.enc_out = scrolledtext.ScrolledText(enc_frame, height=60, wrap="word", state="disabled")
        self.enc_out.grid(row=3, column=0, columnspan=2, sticky="we", pady=(4,0))

        # --- Decode panel ---
        dec_frame = tk.LabelFrame(body, text="Decode: MIDI → text", padx=6, pady=6)
        body.add(dec_frame, stretch="always")

        tk.Label(dec_frame, text="MIDI file (.mid):").grid(row=0, column=0, sticky="w")
        self.dec_mid_path = tk.Entry(dec_frame, width=50)
        self.dec_mid_path.grid(row=0, column=1, sticky="we", padx=4)
        tk.Button(dec_frame, text="Browse", command=self.browse_mid).grid(row=0, column=2, padx=4)

        dec_btn = tk.Button(dec_frame, text="Decode → Text", command=self.on_decode)
        dec_btn.grid(row=1, column=2, sticky="e", pady=6)

        tk.Label(dec_frame, text="Decoded text:").grid(row=1, column=0, sticky="nw")
        self.dec_text = scrolledtext.ScrolledText(dec_frame, width=60, height=12, wrap="word")
        self.dec_text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=4)
        dec_frame.columnconfigure(1, weight=1)

        self.dec_out = scrolledtext.ScrolledText(dec_frame, height=60, wrap="word", state="disabled")
        self.dec_out.grid(row=3, column=0, columnspan=3, sticky="we", pady=(4,0))

    def log_to_widget(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def open_mid_folder(self):
        import webbrowser
        webbrowser.open(str(MID_DIR.resolve()))

    def open_artifacts(self):
        import webbrowser
        webbrowser.open(str(ARTIFACTS_DIR.resolve()))

    def browse_mid(self):
        p = filedialog.askopenfilename(initialdir=str(MID_DIR.resolve()),
                                       filetypes=[("MIDI files","*.mid"),("All files","*.*")])
        if p:
            self.dec_mid_path.delete(0, "end")
            self.dec_mid_path.insert(0, p)

    def _extract_saved_mid(self, stdout, fallback):
        m = re.search(r"MIDI saved:\s*(?:mid/)?([^\s]+\.mid)", stdout)
        if m:
            return m.group(1)
        return f"{fallback}.mid"

    def on_encode(self):
        title = self.enc_title.get().strip()
        text = self.enc_text.get("1.0", "end").rstrip("\n")
        if not text:
            messagebox.showwarning("Encode", "テキストを入力してください。")
            return
        self.enc_out.configure(state="normal")
        self.enc_out.delete("1.0", "end")
        self.log_to_widget(self.enc_out, "Running encoder...")
        enc = encode_text(text, title)
        self.log_to_widget(self.enc_out, f"[returncode={enc.returncode}]")
        self.log_to_widget(self.enc_out, enc.stdout[:2000])
        self.log_to_widget(self.enc_out, "--- STDERR ---")
        self.log_to_widget(self.enc_out, enc.stderr[:2000])

        saved = self._extract_saved_mid(enc.stdout, title)
        mid_path = MID_DIR / saved
        if mid_path.exists():
            messagebox.showinfo("Encode", f"MIDI saved: {mid_path}")
        else:
            messagebox.showwarning("Encode", "MIDI が見つかりません。ログを確認してください。")

    def on_decode(self):
        p = self.dec_mid_path.get().strip()
        if not p:
            messagebox.showwarning("Decode", "MIDIファイルを選択してください。")
            return
        # allow full path or basename
        mid_path = Path(p)
        basename = mid_path.stem
        self.dec_out.configure(state="normal")
        self.dec_out.delete("1.0", "end")
        self.log_to_widget(self.dec_out, f"Decoding {p} ...")
        dec = decode_mid(basename)
        self.log_to_widget(self.dec_out, f"[returncode={dec.returncode}]")
        self.log_to_widget(self.dec_out, dec.stdout[:4000])
        self.log_to_widget(self.dec_out, "--- STDERR ---")
        self.log_to_widget(self.dec_out, dec.stderr[:2000])

        # try to extract decoded text
        # マーカー "復号テキスト:" の後ろ全てを復元テキストとする（改行を含む）
        text = ""
        m = re.search(r"復号テキスト:\s*", dec.stdout)
        if m:
            # マーカー直後から末尾までを取得
            text_tail = dec.stdout[m.end():]
            # 先頭の空行を除去
            text_tail = text_tail.lstrip("\r\n")
            # 後続のログ等が続く場合に備え、よくあるセパレータで切り取る
            sep = re.search(r"\n(?:===|---|\[|MIDI saved:)", text_tail)
            if sep:
                text = text_tail[:sep.start()].rstrip()
            else:
                text = text_tail.rstrip()
        else:
            lines = [l.rstrip() for l in dec.stdout.splitlines() if l.strip()]
            text = lines[-1] if lines else ""
        self.dec_text.delete("1.0", "end")
        self.dec_text.insert("1.0", text)
        messagebox.showinfo("Decode", "復号処理が完了しました。")

if __name__ == "__main__":
    App().mainloop()
