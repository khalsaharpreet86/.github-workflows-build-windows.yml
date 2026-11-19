#!/usr/bin/env python3
"""Happy Audios WTG Converter: Jieli AC696x WTG <-> MP3."""
from __future__ import annotations
import ctypes, shutil, subprocess, sys, tempfile, threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Happy Audios WTG Converter"
PARAM_WIDTHS = (8, 10, 8, 1, 13, 4, 7, 5, 13, 4, 7)

def resource_path(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name

def unpack_jieli_frame(frame):
    if len(frame) != 10: raise ValueError("WTG frame must be 10 bytes")
    w = [int.from_bytes(frame[i:i+2], "little") for i in range(0, 10, 2)]
    return [w[0]&255, (w[0]>>8)|((w[1]<<8)&0x300), (w[1]>>2)&255,
            (w[1]>>10)&1, (w[1]>>11)|((w[2]<<5)&0x1fe0), (w[2]>>8)&15,
            (w[2]>>12)|((w[3]<<4)&0x70), (w[3]>>3)&31,
            (w[3]>>8)|((w[4]<<8)&0x1f00), (w[4]>>5)&15, w[4]>>9]

def repack_standard_g729(params):
    bits = 0
    for value, width in zip(params, PARAM_WIDTHS):
        bits = (bits << width) | (value & ((1 << width)-1))
    return bits.to_bytes(10, "big")

def standard_g729_to_params(frame):
    bits = int.from_bytes(frame, "big")
    out, remaining = [], 80
    for width in PARAM_WIDTHS:
        remaining -= width
        out.append((bits >> remaining) & ((1 << width)-1))
    return out

def pack_jieli_frame(params):
    p0,p1,p2,p3,p4,p5,p6,p7,p8,p9,p10 = params
    words = [p0|((p1&255)<<8),
      ((p1>>8)&3)|(p2<<2)|(p3<<10)|((p4&31)<<11),
      (p4>>5)|(p5<<8)|((p6&15)<<12),
      (p6>>4)|(p7<<3)|((p8&255)<<8),
      (p8>>8)|(p9<<5)|(p10<<9)]
    return b"".join((x&65535).to_bytes(2,"little") for x in words)

def wtg_to_g729(data):
    if not data or len(data)%10: raise ValueError(f"WTG length {len(data)} is not a whole number of 10-byte frames")
    return b"".join(repack_standard_g729(unpack_jieli_frame(data[i:i+10])) for i in range(0,len(data),10))

def g729_to_wtg(data):
    if not data or len(data)%10: raise ValueError("G.729 stream has incomplete frames")
    return b"".join(pack_jieli_frame(standard_g729_to_params(data[i:i+10])) for i in range(0,len(data),10))

class G729Codec:
    def __init__(self, dll_path):
        self.lib = ctypes.CDLL(str(dll_path))
        L = self.lib
        L.initBcg729DecoderChannel.restype = ctypes.c_void_p
        L.closeBcg729DecoderChannel.argtypes = [ctypes.c_void_p]
        L.bcg729Decoder.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8,
            ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.POINTER(ctypes.c_int16)]
        L.initBcg729EncoderChannel.argtypes = [ctypes.c_uint8]
        L.initBcg729EncoderChannel.restype = ctypes.c_void_p
        L.closeBcg729EncoderChannel.argtypes = [ctypes.c_void_p]
        L.bcg729Encoder.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16),
            ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8)]
    def decode(self, data):
        ctx = self.lib.initBcg729DecoderChannel()
        if not ctx: raise RuntimeError("G.729 decoder initialization failed")
        out = bytearray()
        try:
            for i in range(0,len(data),10):
                frame=(ctypes.c_uint8*10).from_buffer_copy(data[i:i+10]); pcm=(ctypes.c_int16*80)()
                self.lib.bcg729Decoder(ctx,frame,10,0,0,0,pcm); out.extend(bytes(pcm))
        finally: self.lib.closeBcg729DecoderChannel(ctx)
        return bytes(out)
    def encode(self, pcm_bytes):
        if len(pcm_bytes)%160: pcm_bytes += b"\x00"*(160-len(pcm_bytes)%160)
        ctx=self.lib.initBcg729EncoderChannel(0)
        if not ctx: raise RuntimeError("G.729 encoder initialization failed")
        out=bytearray()
        try:
            for i in range(0,len(pcm_bytes),160):
                pcm=(ctypes.c_int16*80).from_buffer_copy(pcm_bytes[i:i+160])
                bits=(ctypes.c_uint8*10)(); length=ctypes.c_uint8(0)
                self.lib.bcg729Encoder(ctx,pcm,bits,ctypes.byref(length))
                if length.value != 10: raise RuntimeError(f"Unexpected G.729 frame length: {length.value}")
                out.extend(bytes(bits[:length.value]))
        finally: self.lib.closeBcg729EncoderChannel(ctx)
        return bytes(out)

def ffmpeg(args):
    exe=resource_path("ffmpeg.exe")
    if not exe.exists(): exe=Path(shutil.which("ffmpeg") or "")
    if not exe or not exe.exists(): raise FileNotFoundError("ffmpeg.exe is missing from this package")
    p=subprocess.run([str(exe),"-hide_banner","-loglevel","error","-y",*args],capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr.strip() or "FFmpeg failed")

def convert_wtg(src,dst,codec):
    standard=wtg_to_g729(src.read_bytes()); pcm=codec.decode(standard)
    with tempfile.TemporaryDirectory() as td:
        raw=Path(td)/"decoded.s16le"; raw.write_bytes(pcm)
        ffmpeg(["-f","s16le","-ar","8000","-ac","1","-i",str(raw),"-codec:a","libmp3lame","-b:a","64k",str(dst)])

def convert_mp3(src,dst,codec):
    with tempfile.TemporaryDirectory() as td:
        raw=Path(td)/"input.s16le"
        ffmpeg(["-i",str(src),"-f","s16le","-acodec","pcm_s16le","-ar","8000","-ac","1",str(raw)])
        standard=codec.encode(raw.read_bytes())
    dst.write_bytes(g729_to_wtg(standard))

class App:
    def __init__(self,root):
        self.root=root; self.files=[]; self.outdir=None; self.busy=False
        root.title(APP_NAME+"  |  Jieli AC696x"); root.geometry("720x510"); root.minsize(620,440)
        box=ttk.Frame(root,padding=18); box.pack(fill="both",expand=True)
        ttk.Label(box,text="HAPPY AUDIOS",font=("Segoe UI",18,"bold")).pack(anchor="w")
        ttk.Label(box,text="WTG  ⇄  MP3 Converter  |  Jieli AC696x",font=("Segoe UI",11)).pack(anchor="w",pady=(0,12))
        self.drop=tk.Label(box,text="Drop .WTG or .MP3 files here",relief="groove",bd=2,bg="#f3f6fa",height=4,font=("Segoe UI",12))
        self.drop.pack(fill="x",pady=5)
        row=ttk.Frame(box); row.pack(fill="x",pady=5)
        ttk.Button(row,text="Add WTG files",command=self.add_wtg).pack(side="left",padx=(0,7))
        ttk.Button(row,text="Add MP3 files",command=self.add_mp3).pack(side="left",padx=(0,7))
        ttk.Button(row,text="Remove selected",command=self.remove).pack(side="left")
        self.list=tk.Listbox(box,height=9,selectmode=tk.EXTENDED); self.list.pack(fill="both",expand=True,pady=8)
        out=ttk.Frame(box); out.pack(fill="x")
        ttk.Button(out,text="Choose output folder",command=self.choose_out).pack(side="left")
        self.outlabel=ttk.Label(out,text="Output: beside each input file"); self.outlabel.pack(side="left",padx=10)
        self.progress=ttk.Progressbar(box,mode="determinate"); self.progress.pack(fill="x",pady=(12,4))
        self.status=tk.StringVar(value="Ready"); ttk.Label(box,textvariable=self.status).pack(anchor="w")
        actions=ttk.Frame(box); actions.pack(fill="x",pady=(10,0))
        ttk.Button(actions,text="Clear list",command=self.clear).pack(side="right",padx=6)
        self.go=ttk.Button(actions,text="Convert queued files",command=self.start); self.go.pack(side="right")
        ttk.Label(box,text="WTG uses 10-byte Jieli G.729 frames. Audio is converted as 8 kHz mono.",font=("Segoe UI",8)).pack(anchor="w",pady=(10,0))
        self.enable_drop()
    def enable_drop(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.drop.drop_target_register(DND_FILES); self.drop.dnd_bind("<<Drop>>",self.on_drop)
        except Exception: self.drop.configure(text="Drag-and-drop not enabled; use Add WTG / Add MP3 files")
    def on_drop(self,event):
        for f in self.root.tk.splitlist(event.data): self.add_paths([Path(f)])
    def add_paths(self,paths):
        have={str(p) for p in self.files}
        for p in paths:
            if p.is_file() and p.suffix.lower() in (".wtg",".mp3") and str(p) not in have:
                self.files.append(p); self.list.insert("end",f"[{p.suffix[1:].upper()}]  {p}"); have.add(str(p))
        self.status.set(f"{len(self.files)} file(s) queued")
    def add_wtg(self):
        self.add_paths([Path(x) for x in filedialog.askopenfilenames(filetypes=[("WTG audio","*.wtg")])])
    def add_mp3(self):
        self.add_paths([Path(x) for x in filedialog.askopenfilenames(filetypes=[("MP3 audio","*.mp3")])])
    def remove(self):
        for i in reversed(self.list.curselection()): self.list.delete(i); del self.files[i]
    def clear(self):
        if not self.busy: self.files.clear(); self.list.delete(0,"end"); self.progress["value"]=0; self.status.set("Ready")
    def choose_out(self):
        p=filedialog.askdirectory()
        if p: self.outdir=Path(p); self.outlabel.configure(text="Output: "+p)
    def start(self):
        if self.busy: return
        if not self.files: messagebox.showinfo(APP_NAME,"Add WTG or MP3 files first."); return
        self.busy=True; self.go.configure(state="disabled"); self.progress["maximum"]=len(self.files); self.progress["value"]=0
        threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        ok=[]; errors=[]
        try:
            dll=resource_path("libbcg729.dll")
            if not dll.exists(): raise FileNotFoundError("libbcg729.dll is missing from the app package")
            codec=G729Codec(dll)
            for n,src in enumerate(self.files,1):
                try:
                    ext="_converted.mp3" if src.suffix.lower()==".wtg" else "_converted.wtg"
                    folder=self.outdir or src.parent; dst=folder/(src.stem+ext)
                    if dst.exists():
                        k=2
                        while (folder/(src.stem+ext.replace(".",f"_{k}.",1))).exists(): k+=1
                        dst=folder/(src.stem+ext.replace(".",f"_{k}.",1))
                    if src.suffix.lower()==".wtg": convert_wtg(src,dst,codec)
                    else: convert_mp3(src,dst,codec)
                    ok.append(dst); self.root.after(0,self.status.set,f"Converted {n}/{len(self.files)}: {src.name}")
                except Exception as e: errors.append(f"{src.name}: {e}")
                self.root.after(0,self.progress.configure,{"value":n})
        except Exception as e: errors.append(str(e))
        self.root.after(0,self.finish,ok,errors)
    def finish(self,ok,errors):
        self.busy=False; self.go.configure(state="normal")
        msg=f"Finished. Converted: {len(ok)}   Errors: {len(errors)}"; self.status.set(msg)
        if errors: messagebox.showwarning(APP_NAME,msg+"\n\n"+"\n".join(errors[:10]))
        else: messagebox.showinfo(APP_NAME,msg+"\n\n" + "\n".join(str(p) for p in ok[:10]))

def main():
    try:
        from tkinterdnd2 import TkinterDnD
        root=TkinterDnD.Tk()
    except Exception: root=tk.Tk()
    App(root); root.mainloop()

if __name__=="__main__": main()
