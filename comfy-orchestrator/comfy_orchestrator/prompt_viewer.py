"""Read-only prompt, character evidence and visual observation dialogs."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from . import core
from .character_refs import format_evidence
from .prompt_profiles import T2I_PROFILE_LABELS, I2I_PROFILE_LABELS, H3_PROFILE_LABELS


def show_prompt_details(parent, details: dict, *, from_history: bool, copy_text, show_character) -> None:
    """Shared read-only viewer for current and historic literal prompts."""
    kind = details.get("kind")
    version = details.get("profile")
    if kind == "t2i":
        version_text = T2I_PROFILE_LABELS.get(version, version or "記録なし")
    elif kind in ("i2i", "inpaint"):
        version_text = I2I_PROFILE_LABELS.get(version, version or "記録なし")
    elif details.get("workflow_id") == core.H3_I2V_ID:
        version_text = H3_PROFILE_LABELS.get(version, version or "記録なし")
    else:
        version_text = version or "対象外"
    positive = str(details.get("positive_prompt") or "")
    negative = details.get("negative_prompt")
    negative_saved = isinstance(negative, str)
    negative_text = negative if negative_saved else "（履歴に記録なし）"
    original_request = details.get("request_text")
    popup = tk.Toplevel(parent)
    popup.title(("履歴" if from_history else "今回") + "の生成タグ")
    popup.geometry("780x650")
    popup.minsize(480, 390)
    popup.transient(parent)
    ttk.Label(
        popup,
        text=f"ワークフロー: {details.get('workflow_id', '?')} / "
             f"方式: {version_text}",
        style="Muted.TLabel", wraplength=740,
    ).pack(anchor="w", padx=12, pady=(10, 3))
    values = [
        f"{label}: {details.get(key)}"
        for key, label in (
            ("seed", "Seed"), ("steps", "Steps"),
            ("cfg", "CFG"), ("denoise", "Denoise"),
        )
        if details.get(key) is not None
    ]
    if values:
        ttk.Label(
            popup, text="  /  ".join(values),
            style="Muted.TLabel", wraplength=740,
        ).pack(anchor="w", padx=12, pady=(0, 5))

    # Pack the action bar before expanding editors, so copy/close is
    # reachable even if the window is resized smaller than its content.
    buttons = ttk.Frame(popup, padding=(12, 0, 12, 12))
    buttons.pack(side="bottom", fill="x")

    def add_readonly(label: str, value: str, *, rows: int, grow: bool) -> None:
        frame = ttk.LabelFrame(popup, text=label, padding=7)
        frame.pack(fill="both" if grow else "x",
                   expand=grow, padx=12, pady=(0, 7))
        widget = scrolledtext.ScrolledText(
            frame, height=rows, wrap="word",
            font=("Meiryo UI", 10), padx=8, pady=6,
        )
        widget.insert("1.0", value)
        widget.configure(state="disabled")
        widget.pack(fill="both", expand=True)

    if original_request is not None:
        add_readonly("元の自然文", str(original_request), rows=3, grow=False)
    add_readonly("Positive", positive, rows=7, grow=True)
    add_readonly("Negative", negative_text, rows=4, grow=True)

    ttk.Button(
        buttons, text="Positiveをコピー",
        command=lambda: copy_text(positive),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        buttons, text="Negativeをコピー",
        command=lambda: copy_text(negative),
        state="normal" if negative_saved else "disabled",
    ).pack(side="left")
    if details.get("character_traits"):
        ttk.Button(
            buttons, text="キャラ特徴",
            command=lambda: show_character(details),
        ).pack(side="left", padx=(6, 0))
    ttk.Button(
        buttons, text="閉じる", command=popup.destroy,
    ).pack(side="right")

def show_saved_character_features(parent, details: dict, *, copy_text) -> None:
    """Review the exact approved sheet and observed reference evidence."""
    traits = details.get("character_traits")
    if not traits:
        return
    popup = tk.Toplevel(parent)
    popup.title("キャラ参照・確定特徴")
    popup.geometry("760x570")
    popup.minsize(450, 300)
    popup.transient(parent)
    bottom = ttk.Frame(popup, padding=(10, 3, 10, 10))
    bottom.pack(side="bottom", fill="x")
    ttk.Button(
        bottom, text="確定特徴をコピー",
        command=lambda: copy_text(traits),
    ).pack(side="left")
    ttk.Button(bottom, text="閉じる", command=popup.destroy).pack(side="right")
    num = len(details.get("character_references") or ())
    ttk.Label(
        popup, text=f"生成に採用した特徴 / 参照画像 {num}枚" if num else "生成に採用した特徴 / 文章のみ",
        style="Muted.TLabel",
    ).pack(anchor="w", padx=10, pady=(8, 4))
    content = ttk.Panedwindow(popup, orient="vertical")
    content.pack(fill="both", expand=True, padx=10, pady=(0, 8))
    approved_frame = ttk.LabelFrame(content, text="ユーザー確定値")
    content.add(approved_frame, weight=2)
    report_frame = ttk.LabelFrame(content, text="抽出根拠（LLM推定）")
    content.add(report_frame, weight=3)
    for frame, value in (
        (approved_frame, traits),
        (report_frame, (
            format_evidence(details["character_analysis"])
            if details.get("character_analysis") else "記録なし"
        )),
    ):
        view = scrolledtext.ScrolledText(
            frame, wrap="word", height=7, font=("Meiryo UI", 10),
        )
        view.insert("1.0", value)
        view.configure(state="disabled")
        view.pack(fill="both", expand=True, padx=6, pady=6)

def show_composition_report(parent, report: str) -> None:
    """Show exactly what the selected local VLM thought it saw."""
    if not report:
        messagebox.showinfo(
            "画像の構図認識",
            "まず参照画像を選び、「解釈のみテスト」を実行してください。"
            "画像対応モデルと構図解析ONが必要です。",
        )
        return
    window = tk.Toplevel(parent)
    window.title("画像の構図認識結果（VLM推定）")
    window.geometry("700x480")
    window.minsize(440, 300)
    window.transient(parent)
    ttk.Label(
        window,
        text="以下は画像対応LLMの観察結果です。誤認識があれば、生成指示を具体化するか"
             "ポーズControlNetの併用を検討してください。",
        style="Muted.TLabel", wraplength=650,
    ).pack(anchor="w", fill="x", padx=12, pady=(12, 7))
    view = scrolledtext.ScrolledText(
        window, wrap="word", font=("Meiryo UI", 11), padx=10,
        pady=8, height=14,
    )
    view.insert("1.0", report)
    view.configure(state="disabled")
    view.pack(fill="both", expand=True, padx=12, pady=(0, 8))
    footer = ttk.Frame(window, padding=(12, 0, 12, 12))
    footer.pack(fill="x")
    ttk.Button(
        footer, text="閉じる", command=window.destroy,
    ).pack(side="right")
