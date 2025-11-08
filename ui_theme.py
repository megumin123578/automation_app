# ui_theme.py
def setup_theme(style, root,
                bg_dark="#2b2b2b",
                bg_panel="#3c3f41",
                fg_light="#f0f0f0",
                accent="#0078d7"):
    style.theme_use("clam")

    # Spinbox
    style.configure("TSpinbox",
                    fieldbackground=bg_panel,
                    background=bg_panel,
                    foreground=fg_light,
                    arrowsize=14)
    style.map("TSpinbox",
              fieldbackground=[("readonly", bg_panel)],
              foreground=[("readonly", fg_light)])

    # Radiobutton
    style.configure("TRadiobutton",
                    background=bg_dark,
                    foreground=fg_light,
                    font=("Segoe UI", 10))
    style.map("TRadiobutton",
              background=[("active", bg_panel)],
              foreground=[("active", accent)])

    # DateEntry
    style.configure("DateEntry",
                    fieldbackground=bg_panel,
                    background=bg_panel,
                    foreground=fg_light)

    # Frame
    style.configure("TFrame", background=bg_dark)
    style.configure("TLabelframe", background=bg_dark, foreground=fg_light)
    style.configure("TLabelframe.Label", background=bg_dark, foreground=fg_light)

    # Treeview
    style.configure("Treeview",
                    background=bg_panel,
                    foreground=fg_light,
                    rowheight=28,
                    fieldbackground=bg_panel,
                    font=("Segoe UI", 10))
    style.map("Treeview",
              background=[("selected", accent)],
              foreground=[("selected", "white")])
    style.configure("Treeview.Heading",
                    font=("Segoe UI", 10, "bold"),
                    background=bg_dark,
                    foreground=fg_light)

    # Button
    style.configure("TButton",
                    background=bg_panel,
                    foreground=fg_light,
                    font=("Segoe UI", 10, "bold"),
                    padding=6)
    style.map("TButton",
              background=[("active", accent), ("pressed", accent)],
              foreground=[("active", "white"), ("pressed", "white")])

    # Label
    style.configure("TLabel",
                    background=bg_dark,
                    foreground=fg_light,
                    font=("Segoe UI", 10))

    # Entry
    style.configure("TEntry",
                    fieldbackground=bg_panel,
                    foreground=fg_light,
                    insertcolor="white",
                    padding=4)

    # Combobox
    style.configure("TCombobox",
                    fieldbackground=bg_panel,
                    background=bg_panel,
                    foreground=fg_light,
                    selectbackground=accent,
                    selectforeground="white",
                    padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", bg_panel)],
              foreground=[("readonly", fg_light)],
              selectbackground=[("readonly", accent)],
              selectforeground=[("readonly", "white")])

    # Đồng bộ màu nền cửa sổ
    root.configure(bg=bg_dark)
    root.option_add("*Background", bg_dark)
    root.option_add("*Foreground", fg_light)
    root.option_add("*TEntry*background", bg_panel)
    root.option_add("*TEntry*foreground", fg_light)
    root.option_add("*Text*background", bg_panel)
    root.option_add("*Text*foreground", fg_light)
    root.option_add("*Text*insertBackground", "white")
