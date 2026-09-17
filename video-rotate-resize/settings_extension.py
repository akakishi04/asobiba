from __future__ import annotations


def enable_seedvr2_chunk_settings(app_ai) -> None:
    """Replace the AI settings dialog with one that exposes SeedVR2 RAM chunking."""

    def settings(self):
        w = app_ai.tk.Toplevel(self.root)
        w.title("AI設定")
        w.geometry("840x620")
        w.minsize(800, 580)
        w.grab_set()
        f = app_ai.ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        vals = {
            "rp": app_ai.tk.StringVar(value=self.config.rvrt_python),
            "rc": app_ai.tk.StringVar(value=str(self.config.rvrt_chunk_size)),
            "ro": app_ai.tk.StringVar(value=str(self.config.rvrt_chunk_overlap)),
            "sr": app_ai.tk.StringVar(value=self.config.seedvr2_repo),
            "sp": app_ai.tk.StringVar(value=self.config.seedvr2_python),
            "sm": app_ai.tk.StringVar(value=self.config.seedvr2_model),
            "sb": app_ai.tk.StringVar(value=str(self.config.seedvr2_batch_size)),
            "ss": app_ai.tk.StringVar(value=str(self.config.seedvr2_blocks_to_swap)),
            "sx": app_ai.tk.StringVar(value=str(self.config.seedvr2_resolution_override)),
            "sc": app_ai.tk.StringVar(value=str(self.config.seedvr2_chunk_size)),
            "so": app_ai.tk.StringVar(value=str(self.config.seedvr2_chunk_overlap)),
        }
        rev = {v: k for k, v in app_ai.RVRT_TASKS.items()}
        rt = app_ai.tk.StringVar(
            value=rev.get(self.config.rvrt_task, next(iter(app_ai.RVRT_TASKS)))
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

            app_ai.ttk.Button(f, text="参照...", command=pick).grid(
                row=r, column=2
            )

        app_ai.ttk.Label(f, text="RVRT (vsrvrt)", font=("", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        row(1, "RVRT Python", "rp")
        app_ai.ttk.Label(f, text="RVRTモデル").grid(row=2, column=0, sticky="w")
        app_ai.ttk.Combobox(
            f,
            textvariable=rt,
            values=list(app_ai.RVRT_TASKS),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", padx=8)

        radv = app_ai.ttk.Frame(f)
        radv.grid(row=3, column=1, sticky="w", padx=8, pady=6)
        app_ai.ttk.Label(radv, text="Chunk").pack(side="left")
        app_ai.ttk.Entry(radv, width=7, textvariable=vals["rc"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(radv, text="Overlap").pack(side="left")
        app_ai.ttk.Entry(radv, width=7, textvariable=vals["ro"]).pack(
            side="left", padx=(3, 10)
        )

        app_ai.ttk.Separator(f).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=10
        )
        app_ai.ttk.Label(f, text="SeedVR2", font=("", 10, "bold")).grid(
            row=5, column=0, sticky="w"
        )
        row(6, "SeedVR2フォルダ", "sr", True)
        row(7, "SeedVR2 Python", "sp")
        app_ai.ttk.Label(f, text="Model").grid(row=8, column=0, sticky="w")
        app_ai.ttk.Entry(f, textvariable=vals["sm"]).grid(
            row=8, column=1, sticky="ew", padx=8
        )

        adv = app_ai.ttk.Frame(f)
        adv.grid(row=9, column=1, sticky="w", padx=8, pady=6)
        for label, key in [
            ("Batch", "sb"),
            ("BlockSwap", "ss"),
            ("処理短辺(0=ネイティブ)", "sx"),
        ]:
            app_ai.ttk.Label(adv, text=label).pack(side="left")
            app_ai.ttk.Entry(adv, width=7, textvariable=vals[key]).pack(
                side="left", padx=(3, 10)
            )

        app_ai.ttk.Label(f, text="長尺動画 / RAM").grid(
            row=10, column=0, sticky="w", pady=3
        )
        cadv = app_ai.ttk.Frame(f)
        cadv.grid(row=10, column=1, sticky="w", padx=8, pady=6)
        app_ai.ttk.Label(cadv, text="Chunk").pack(side="left")
        app_ai.ttk.Entry(cadv, width=7, textvariable=vals["sc"]).pack(
            side="left", padx=(3, 10)
        )
        app_ai.ttk.Label(cadv, text="Overlap").pack(side="left")
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
                "Batchは主にVRAM、長尺Chunkは主にシステムRAM使用量へ影響します。"
                " 1080p長尺でArrayMemoryErrorならChunkを25程度へ下げてください。"
            ),
            foreground="#555",
            wraplength=780,
        ).grid(row=11, column=0, columnspan=3, sticky="w", pady=(4, 2))
        app_ai.ttk.Label(
            f,
            text=(
                "4070 Ti SUPER 16GB向け初期値: 3B FP8 / Batch 5 / BlockSwap 20 / "
                "SeedVR2 Chunk 45 / Overlap 5 / VAE tiling。"
            ),
            foreground="#555",
            wraplength=780,
        ).grid(row=12, column=0, columnspan=3, sticky="w", pady=(2, 8))

        def save():
            try:
                rchunk = int(vals["rc"].get())
                rover = int(vals["ro"].get())
                batch = int(vals["sb"].get())
                swap = int(vals["ss"].get())
                res = int(vals["sx"].get())
                schunk = int(vals["sc"].get())
                sover = int(vals["so"].get())
                if (
                    rchunk < 4
                    or rover < 0
                    or rover >= rchunk
                    or batch < 1
                    or swap < 0
                    or res < 0
                    or schunk < 5
                    or schunk < batch
                    or sover < 0
                    or sover >= schunk
                ):
                    raise ValueError
            except ValueError:
                app_ai.messagebox.showerror(
                    "AI設定",
                    (
                        "RVRT: Chunk>=4 / 0<=Overlap<Chunk\n"
                        "SeedVR2: Batch>=1 / Chunk>=max(5, Batch) / 0<=Overlap<Chunk\n"
                        "BlockSwap・処理短辺は0以上の整数にしてください。"
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
                seedvr2_repo=vals["sr"].get().strip(),
                seedvr2_python=vals["sp"].get().strip(),
                seedvr2_model=vals["sm"].get().strip(),
                seedvr2_batch_size=batch,
                seedvr2_blocks_to_swap=swap,
                seedvr2_temporal_overlap=self.config.seedvr2_temporal_overlap,
                seedvr2_resolution_override=res,
                seedvr2_vae_tiling=True,
                seedvr2_vae_tile_size=self.config.seedvr2_vae_tile_size,
                seedvr2_vae_tile_overlap=self.config.seedvr2_vae_tile_overlap,
                seedvr2_chunk_size=schunk,
                seedvr2_chunk_overlap=sover,
            )
            self.config.save(self.config_path)
            self._refresh_ai_state()
            w.destroy()

        bar = app_ai.ttk.Frame(f)
        bar.grid(row=13, column=0, columnspan=3, sticky="e", pady=(10, 0))
        app_ai.ttk.Button(bar, text="キャンセル", command=w.destroy).pack(
            side="right"
        )
        app_ai.ttk.Button(bar, text="保存", command=save).pack(
            side="right", padx=8
        )

    app_ai.App._settings = settings
