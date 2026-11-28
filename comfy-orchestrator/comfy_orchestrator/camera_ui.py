"""Camera intent editor with a lightweight real perspective wireframe preview."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import camera_spec as camera
from .camera_preview import segments


class CameraWindow(tk.Toplevel):
    def __init__(self, parent, value, width, height, *, apply_label="適用"):
        super().__init__(parent)
        self.title("カメラ設定")
        self.geometry("790x535")
        self.minsize(620,410)
        self.transient(parent)
        self.result = None
        try:
            w,h = int(width),int(height)
            self.aspect = w/h if w>0 and h>0 else 1.0
        except (ValueError,TypeError,ZeroDivisionError):
            self.aspect = 1.0
        self.aspect = min(8.0,max(.125,self.aspect))
        value = camera.normalize(value)
        self.fields = {}
        body = ttk.Frame(self,padding=10)
        body.pack(fill="both",expand=True)
        footer = ttk.Frame(body)
        footer.pack(side="bottom",fill="x",pady=(8,0))
        ttk.Button(footer,text="すべて未指定",command=self._reset).pack(side="left")
        ttk.Button(footer,text="キャンセル",command=self.destroy).pack(side="right")
        ttk.Button(footer,text=apply_label,command=self._apply).pack(side="right",padx=6)
        controls = ttk.Frame(body,padding=(12,0,0,0))
        controls.pack(side="right",fill="y")
        view = ttk.Frame(body)
        view.pack(side="left",fill="both",expand=True)
        self.canvas = tk.Canvas(view,background="#202631",highlightthickness=0,
                                width=410,height=385)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",self._redraw)
        ttk.Label(view,text="未指定項目はプレビュー上のみ既定値で表示",wraplength=380).pack(anchor="w",pady=(4,0))
        for field,choices in camera.OPTIONS.items():
            ttk.Label(controls,text=camera.LABELS[field]).pack(anchor="w",pady=(5,2))
            variable = tk.StringVar(master=self,value=choices[value[field]][0] if field in value else "未指定")
            self.fields[field] = variable
            box = ttk.Combobox(controls,textvariable=variable,state="readonly",
                               values=("未指定",*(item[0] for item in choices.values())),width=17)
            box.pack(fill="x")
            box.bind("<<ComboboxSelected>>",self._redraw)
        ttk.Label(controls,text="左右は被写体基準。\nプレビューは参考用で、生成結果の\n角度を保証するものではありません。",
                  justify="left",wraplength=205).pack(anchor="w",pady=(12,0))
        self.protocol("WM_DELETE_WINDOW",self.destroy)
        self._redraw()

    def value(self):
        return {field: code for field,var in self.fields.items()
                for code,item in camera.OPTIONS[field].items() if item[0]==var.get()}

    def _redraw(self,_event=None):
        if len(self.fields)!=len(camera.OPTIONS):
            return
        self.canvas.delete("all")
        cw,ch=max(2,self.canvas.winfo_width()),max(2,self.canvas.winfo_height())
        w=max(2,min(cw-16,(ch-16)*self.aspect))
        h=max(2,w/self.aspect)
        x,y=(cw-w)/2,(ch-h)/2
        self.canvas.create_rectangle(x,y,x+w,y+h,fill="#303b4b",outline="#9aa8bb")
        for kind,a,b,c,d in segments(self.value(),w,h):
            color={"grid":"#48586b","body":"#b4c8da","front":"#e5b86c"}[kind]
            self.canvas.create_line(x+a,y+b,x+c,y+d,fill=color,width=1 if kind=="grid" else 2)
        self.canvas.create_rectangle(x,y,x+w,y+h,outline="#9aa8bb")
        self.canvas.create_text(x+8,y+8,text="CAMERA PREVIEW",fill="#c7d4e2",anchor="nw",font=("TkDefaultFont",9))

    def _reset(self):
        for variable in self.fields.values():
            variable.set("未指定")
        self._redraw()

    def _apply(self):
        self.result = camera.normalize(self.value())
        self.destroy()


def choose_camera(parent, value, width, height, *, apply_label="適用"):
    previous = parent.grab_current()
    popup = CameraWindow(parent,value,width,height,apply_label=apply_label)
    try:
        popup.wait_visibility()
        popup.grab_set()
        parent.wait_window(popup)
        return popup.result
    finally:
        if previous is not None and previous.winfo_exists():
            previous.grab_set()
