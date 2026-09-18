from __future__ import annotations

from resource_policy import (
    PROFILE_CUSTOM,
    PROFILE_DEFAULT_DUTY,
    RESOURCE_PROFILE_CHOICES,
)

COLOR_CORRECTION_CHOICES = {
    "Wavelet（高品質 / 標準）": "wavelet",
    "AdaIN（高速）": "adain",
    "なし（最速 / 色補正なし）": "none",
}


def enable_seedvr2_chunk_settings(app_ai) -> None:
    """Replace the AI settings dialog with resource + long-video controls."""
    original_refresh_ai_state = app_ai.App._refresh_ai_state

    def settings(self):
        w = app_ai.tk.Toplevel(self.root)
        w.title("AI設定")
        w.geometry("940x800")
        w.minsize(900, 760)
        w.grab_set()
        f = app_ai.ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        vals = {
            "rp": app_ai.tk.StringVar(value=self.config.rvrt_python),
            "rc": app_ai.tk.StringVar(value=str(self.config.rvrt_chunk_size)),
            "ro": app_ai.tk.StringVar(value=str(self.config.rvrt_chunk_overlap)),
            "rtile": app_ai.tk.StringVar(value=str(self.config.rvrt_spatial_tile)),
            "sr": app_ai.tk.StringVar(value=self.config.seedvr2_repo),
            "sp": app_ai.tk.StringVar(value=self.config.seedvr2_python),
            "sm": app_ai.tk.StringVar(value=self.config.seedvr2_model),
            "sb": app_ai.tk.StringVar(value=str(self.config.seedvr2_batch_size)),
            "ss": app_ai.tk.StringVar(value=str(self.config.seedvr2_blocks_to_swap)),
            "st": app_ai.tk.StringVar(value=str(self.config.seedvr2_temporal_overlap)),
            "sx": app_ai.tk.StringVar(value=str(self.config.seedvr2_resolution_override)),
            "vt": app_ai.tk.StringVar(value=str(self.config.seedvr2_vae_tile_size)),
            "vo": app_ai.tk.StringVar(value=str(self.config.seedvr2_vae_tile_overlap)),
            "sc": app_ai.tk.StringVar(value=str(self.config.seedvr2_chunk_size)),
            "so": app_ai.tk.StringVar(value=str(self.config.seedvr2_chunk_overlap)),
            "duty": app_ai.tk.StringVar(value=str(self.config.gpu_duty_cycle_percent)),
        }

        rev = {v: k for k, v in app_ai.RVRT_TASKS.items()}
        rt = app_ai.tk.StringVar(
            value=rev.get(self.config.rvrt_task, next(iter(app_ai.RVRT_TASKS)))
        )

        color_rev = {v: k for k, v in COLOR_CORRECTION_CHOICES.items()}
        color_label = app_ai.tk.StringVar(
            value=color_rev.get(
                self.config.seedvr2_color_correction,
                "Wavelet（高品質 / 標準）",
            )
        )

        profile_rev = {v: k for k, v in RESOURCE_PROFILE_CHOICES.items()}
        profile_label = app_ai.tk.StringVar(
            value=profile_rev.get(
                self.config.resource_profile,
                next(iter(RESOURCE_PROFILE_CHOICES)),
            )
        )

        def row(r, label, key, directory=False):
            app_ai.ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            app_ai.ttk.Entry(f, textvariable=vals[key]).grid(
                row=r, column=1, sticky="ew", padx=8, pady=3
            )

            def pick():
                p = (
                    app_ai.filedialog.askdirectory()
                    if directory
                    else app_ai.filedialog.askopenfilename()
                )
                if p:
                    vals[key].set(p)

            app_ai.ttk.Button(f, text="参照...", command=pick).grid(row=r, column=2)

        # Resource policy
        app_ai.ttk.Label(f, text="実行負荷", font=("", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        resource = app_ai.ttk.Frame(f)
        resource.grid(row=0, column=1, columnspan=2, sticky="w", padx=8)
        profile_box = app_ai.ttk.Combobox(
            resource,
            textvariable=profile_label,
            values=list(RESOURCE_PROFILE_CHOICES),
            state="readonly",
            width=18,
        )
        profile_box.pack(side="left")
        app_ai.ttk.Label(resource, text="GPUデューティ目標").pack(
            side="left", padx=(12, 3)
        )
        duty_entry = app_ai.ttk.Entry(resource, width=6, textvariable=vals["duty"])
        duty_entry.pack(side="left")
        app_ai.ttk.Label(resource, text="%").pack(side="left", padx=(3, 0))

        def sync_profile(_event=None):
            profile = RESOURCE_PROFILE_CHOICES[profile_label.get()]
            if profile == PROFILE_CUSTOM:
                duty_entry.configure(state="normal")
            else:
                vals["duty"].set(str(PROFILE_DEFAULT_DUTY[profile]))
                duty_entry.configure(state="disabled")

        profile_box.bind("<<ComboboxSelected>>", sync_profile)
        sync_profile()

        app_ai.ttk.Label(
            f,
            text=(
                "最大速度=100% / バランス=75% / 他作業優先=50%。"
                " デューティ値はハードなGPU使用率上限ではなく、AI処理単位の実測時間に応じて休止を挟む目安です。"
                " 他作業優先ではSeedVR2のBlockSwapも最低28まで自動的に強めます。"
            ),
            foreground="#555",
            wraplength=840,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 8))

        # RVRT
        app_ai.ttk.Label(f, text="RVRT (vsrvrt)", font=("", 10, "bold")).grid(
            row=2, column=0, sticky="w"
        )
        row(3, "RVRT Python", "rp")
        app_ai.ttk.Label(f, text="RVRTモデル").grid(row=4, column=0, sticky="w")
        app_ai.ttk.Combobox(
            f,
            textvariable=rt,
            values=list(app_ai.RVRT_TASKS),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=8)

        radv = app_ai.ttk.Frame(f)
        radv.grid(row=5, column=1, sticky="w", padx=8, pady=6)
        app_ai.ttk.Label(radv, text="Chunk（フレーム）").pack(side="left")
        app_ai.ttk.Entry(radv, width=7, textvariable=vals["rc"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(radv, text="Overlap（フレーム）").pack(side="left")
        app_ai.ttk.Entry(radv, width=7, textvariable=vals["ro"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(radv, text="空間Tile(0=自動)").pack(side="left")
        app_ai.ttk.Entry(radv, width=7, textvariable=vals["rtile"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(
            f,
            text=(
                "RVRTはFFmpeg rawvideo pipeで連続入力し、PNGを介さず処理します。"
                " 空間Tile=0ではVRAM予算内で256〜512からモデル呼び出し回数が少ない構成を自動選択します。"
                " 速度比較用の目安: 標準16/4・高速32/4・攻め64/4。"
            ),
            foreground="#555",
            wraplength=840,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 6))

        app_ai.ttk.Separator(f).grid(
            row=7, column=0, columnspan=3, sticky="ew", pady=8
        )

        # SeedVR2
        app_ai.ttk.Label(f, text="SeedVR2", font=("", 10, "bold")).grid(
            row=8, column=0, sticky="w"
        )
        row(9, "SeedVR2フォルダ", "sr", True)
        row(10, "SeedVR2 Python", "sp")
        app_ai.ttk.Label(f, text="Model").grid(row=11, column=0, sticky="w")
        app_ai.ttk.Entry(f, textvariable=vals["sm"]).grid(
            row=11, column=1, sticky="ew", padx=8
        )

        adv = app_ai.ttk.Frame(f)
        adv.grid(row=12, column=1, sticky="w", padx=8, pady=6)
        for label, key in [
            ("Batch", "sb"),
            ("BlockSwap", "ss"),
            ("処理短辺(0=ネイティブ)", "sx"),
        ]:
            app_ai.ttk.Label(adv, text=label).pack(side="left")
            app_ai.ttk.Entry(adv, width=7, textvariable=vals[key]).pack(
                side="left", padx=(3, 10)
            )

        tune = app_ai.ttk.Frame(f)
        tune.grid(row=13, column=1, sticky="w", padx=8, pady=6)
        for label, key in [
            ("Temporal overlap", "st"),
            ("VAE Tile", "vt"),
            ("VAE Overlap", "vo"),
        ]:
            app_ai.ttk.Label(tune, text=label).pack(side="left")
            app_ai.ttk.Entry(tune, width=7, textvariable=vals[key]).pack(
                side="left", padx=(3, 10)
            )

        app_ai.ttk.Label(f, text="色補正").grid(
            row=14, column=0, sticky="w", pady=3
        )
        app_ai.ttk.Combobox(
            f,
            textvariable=color_label,
            values=list(COLOR_CORRECTION_CHOICES),
            state="readonly",
        ).grid(row=14, column=1, sticky="ew", padx=8, pady=3)

        app_ai.ttk.Label(f, text="長尺動画 / RAM").grid(
            row=15, column=0, sticky="w", pady=3
        )
        cadv = app_ai.ttk.Frame(f)
        cadv.grid(row=15, column=1, sticky="w", padx=8, pady=6)
        app_ai.ttk.Label(cadv, text="Chunk（フレーム）").pack(side="left")
        app_ai.ttk.Entry(cadv, width=7, textvariable=vals["sc"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(cadv, text="Overlap（フレーム）").pack(side="left")
        app_ai.ttk.Entry(cadv, width=7, textvariable=vals["so"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(
            cadv,
            text="  目安: 25=低RAM / 45=標準 / 65=余裕あり",
            foreground="#555",
        ).pack(side="left")

        app_ai.ttk.Label(
            f,
            text=(
                "SeedVR2はモデルを1回だけロードし、動画を順次チャンク処理します。"
                " Batchは4n+1（5/9/13...）が必須で、24GB未満では5が安全側です。"
                " Temporal overlapを2→1/0に下げると速くなりますが境界の時間的一貫性が弱くなる可能性があります。"
                " AdaIN/色補正なしはWaveletより高速です。VAE Tileを大きくすると速くなる場合がありますがVRAMを多く使います。"
            ),
            foreground="#555",
            wraplength=840,
        ).grid(row=16, column=0, columnspan=3, sticky="w", pady=(4, 8))

        def save():
            try:
                rchunk = int(vals["rc"].get())
                rover = int(vals["ro"].get())
                rtile = int(vals["rtile"].get())
                batch = int(vals["sb"].get())
                swap = int(vals["ss"].get())
                temporal = int(vals["st"].get())
                res = int(vals["sx"].get())
                vae_tile = int(vals["vt"].get())
                vae_overlap = int(vals["vo"].get())
                schunk = int(vals["sc"].get())
                sover = int(vals["so"].get())
                duty = int(vals["duty"].get())
                profile = RESOURCE_PROFILE_CHOICES[profile_label.get()]
                if (
                    rchunk < 4
                    or rover < 0
                    or rover >= rchunk
                    or rtile < 0
                    or (rtile != 0 and (rtile < 128 or rtile % 8 != 0))
                    or batch < 1
                    or batch % 4 != 1
                    or swap < 0
                    or temporal < 0
                    or temporal >= batch
                    or res < 0
                    or vae_tile <= 0
                    or vae_overlap < 0
                    or vae_overlap >= vae_tile
                    or schunk < 5
                    or schunk < batch
                    or sover < 0
                    or sover >= schunk
                    or duty < 20
                    or duty > 100
                ):
                    raise ValueError
            except ValueError:
                app_ai.messagebox.showerror(
                    "AI設定",
                    (
                        "RVRT: Chunk>=4 / 0<=Overlap<Chunk\n"
                        "SeedVR2: Batchは4n+1 / 0<=Temporal<Batch / Chunk>=max(5, Batch) / 0<=Overlap<Chunk\n"
                        "VAE Tile>0 / 0<=VAE Overlap<Tile。BlockSwap・処理短辺は0以上、GPUデューティは20～100にしてください。"
                    ),
                    parent=w,
                )
                return

            self.config = app_ai.AIConfig(
                rvrt_repo="",
                rvrt_python=vals["rp"].get().strip(),
                rvrt_task=app_ai.RVRT_TASKS[rt.get()],
                rvrt_chunk_size=rchunk,
                rvrt_chunk_overlap=rover,
                rvrt_spatial_tile=rtile,
                seedvr2_repo=vals["sr"].get().strip(),
                seedvr2_python=vals["sp"].get().strip(),
                seedvr2_model=vals["sm"].get().strip(),
                seedvr2_batch_size=batch,
                seedvr2_blocks_to_swap=swap,
                seedvr2_temporal_overlap=temporal,
                seedvr2_resolution_override=res,
                seedvr2_vae_tiling=True,
                seedvr2_vae_tile_size=vae_tile,
                seedvr2_vae_tile_overlap=vae_overlap,
                seedvr2_color_correction=COLOR_CORRECTION_CHOICES[color_label.get()],
                seedvr2_chunk_size=schunk,
                seedvr2_chunk_overlap=sover,
                resource_profile=profile,
                gpu_duty_cycle_percent=duty,
            )
            self.config.save(self.config_path)
            self._refresh_ai_state()
            w.destroy()

        bar = app_ai.ttk.Frame(f)
        bar.grid(row=17, column=0, columnspan=3, sticky="e", pady=(10, 0))
        app_ai.ttk.Button(bar, text="キャンセル", command=w.destroy).pack(
            side="right"
        )
        app_ai.ttk.Button(bar, text="保存", command=save).pack(
            side="right", padx=8
        )

    def refresh_ai_state(self):
        original_refresh_ai_state(self)
        reverse = {value: label for label, value in RESOURCE_PROFILE_CHOICES.items()}
        label = reverse.get(self.config.resource_profile, self.config.resource_profile)
        self.ai_state.set(f"{self.ai_state.get()} / 実行負荷: {label}")

    app_ai.App._settings = settings
    app_ai.App._refresh_ai_state = refresh_ai_state
