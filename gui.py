"""
==========================================
🎬 小说转视频 — 分步审核GUI v4.1
- 修复：断点续传（图片/音频/视频跳过已完成项）
- 修复：Step1导入完整流程
- 修复：episodes初始化
- 改进：图片prompt自动注入角色外貌
==========================================
"""
import os
import sys
import json
import threading
import tkinter as tk
import time
from tkinter import ttk, filedialog, scrolledtext, messagebox
from PIL import Image, ImageTk

from config import *
from gemini_engine import GeminiEngine
from novel_splitter import NovelSplitter
from character_manager import CharacterManager
from tts_engine import TTSEngine
from state_manager import StateManager
from bootstrap import get_text_engine, get_video_engine, get_tts_engine, init_all_engines, get_registry
from capcut_editor import CapcutEditor
from task_manager import TaskManager



class ImageSelectorDialog:
    """弹窗：显示多张候选图片，让用户选择一张"""

    def __init__(self, parent, candidates, scene_id):
        self.result = None  # 用户选中的路径
        self.win = tk.Toplevel(parent)
        self.win.title(f"选择场景 {scene_id} 的图片")
        self.win.grab_set()
        self.win.focus_force()

        tk.Label(self.win, text=f"场景 {scene_id} — 请选择最佳图片",
                 font=("Microsoft YaHei", 12, "bold")).pack(pady=10)

        frame = tk.Frame(self.win)
        frame.pack(padx=10, pady=10)

        self._photo_refs = []  # 防止GC回收
        for i, path in enumerate(candidates):
            try:
                img = Image.open(path)
                img.thumbnail((300, 300))
                photo = ImageTk.PhotoImage(img)
                self._photo_refs.append(photo)
                btn = tk.Button(frame, image=photo, relief='raised', bd=3,
                                command=lambda p=path: self._select(p))
                btn.grid(row=0, column=i, padx=8, pady=5)
                tk.Label(frame, text=f"候选 {i+1}",
                         font=("Microsoft YaHei", 9)).grid(row=1, column=i)
            except Exception as e:
                tk.Label(frame, text=f"加载失败\n{e}",
                         width=20, height=10).grid(row=0, column=i, padx=8)

        tk.Button(self.win, text="跳过（不选）", fg="gray",
                  command=lambda: self._select(None)).pack(pady=8)

        self.win.protocol('WM_DELETE_WINDOW', lambda: self._select(None))
        self.win.wait_window()

    def _select(self, path):
        self.result = path
        self.win.destroy()

class StepGUI:
    """分步审核式 小说转视频 GUI v4.1"""

    STEPS = [
        "① 导入小说",
        "② 分集预览",
        "③ 角色管理",
        "④ 分镜剧本",
        "⑤ 图片生成",
        "⑥ 语音合成",
        "⑦ 视频生成",
        "⑧ 最终合成",
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📖 小说转视频 v4.1 — 分步审核")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1a1a2e")
        self.root.minsize(1200, 800)

        # ===== 任务管理 =====
        self.task_mgr = TaskManager()
        self.current_task = None
        self.current_task_name = None

        # ===== 数据状态 =====
        self.novel_path = None
        self.novel_text = ""
        self.episodes = []           # ★ 修复：初始化
        self.characters = []
        self.characters_locked = False
        self.current_ep = 0
        self.storyboard = None
        self.image_results = []
        self.frame_sequence = []  # 链式帧序列
        self.audio_results = []
        self.current_step = 0
        self.video_results = []

        # ===== 引擎 =====
        self.gemini = None
        self.char_manager = None
        self.tts = None
        self.state = None
        self.splitter = None

        # ===== UI =====
        self._build_ui()

    # ══════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#0f3460", height=50)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="🎬 小说转视频 — 分步审核工作台 v4.1",
                 font=("Microsoft YaHei", 16, "bold"),
                 fg="white", bg="#0f3460").pack(side="left", padx=20)
        self.step_label = tk.Label(top, text="当前: ① 导入小说",
                                   font=("Microsoft YaHei", 12),
                                   fg="#e94560", bg="#0f3460")
        self.step_label.pack(side="right", padx=20)

        left = tk.Frame(self.root, bg="#16213e", width=200)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # -- Task Management UI --
        task_frame = tk.LabelFrame(left, text="📂 任务管理",
                                    font=("Microsoft YaHei", 10, "bold"),
                                    fg="#e94560", bg="#16213e", padx=5, pady=5)
        task_frame.pack(fill="x", padx=8, pady=(10, 5))

        self.task_combo = ttk.Combobox(task_frame, width=16, state="readonly")
        self.task_combo.pack(fill="x", pady=(0, 5))
        self.task_combo.bind("<<ComboboxSelected>>", self._on_task_selected)
        self._refresh_task_list()

        task_btn_row = tk.Frame(task_frame, bg="#16213e")
        task_btn_row.pack(fill="x")
        tk.Button(task_btn_row, text="➕ 新建", font=("Microsoft YaHei", 9),
                  bg="#2a6041", fg="white", relief="flat", padx=8,
                  command=self._create_new_task).pack(side="left", padx=2)
        tk.Button(task_btn_row, text="🗑 删除", font=("Microsoft YaHei", 9),
                  bg="#8b0000", fg="white", relief="flat", padx=8,
                  command=self._delete_current_task).pack(side="left", padx=2)

        self.task_status_label = tk.Label(task_frame, text="未选择任务",
                                           font=("Microsoft YaHei", 8),
                                           fg="#888", bg="#16213e")
        self.task_status_label.pack(anchor="w", pady=(3, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=10, pady=8)

        tk.Label(left, text="📋 流程步骤", font=("Microsoft YaHei", 12, "bold"),
                 fg="white", bg="#16213e").pack(pady=(5, 10))

        self.step_buttons = []
        for i, name in enumerate(self.STEPS):
            btn = tk.Button(left, text=name, font=("Microsoft YaHei", 10),
                           fg="white", bg="#1a1a2e", relief="flat",
                           anchor="w", padx=15, pady=6,
                           command=lambda idx=i: self._goto_step(idx))
            btn.pack(fill="x", padx=8, pady=2)
            self.step_buttons.append(btn)

        self.step_buttons[0].config(bg="#e94560")

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=10, pady=15)

        tk.Label(left, text="🎬 当前处理集数", font=("Microsoft YaHei", 10),
                 fg="#aaa", bg="#16213e").pack()
        self.ep_selector = ttk.Combobox(left, values=["先导入小说"], width=18, state="readonly")
        self.ep_selector.set("先导入小说")
        self.ep_selector.pack(padx=10, pady=5)
        self.ep_selector.bind("<<ComboboxSelected>>", self._on_ep_changed)

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=10, pady=15)
        self.progress_label = tk.Label(left, text="进度: 0%",
                                        font=("Microsoft YaHei", 10),
                                        fg="#aaa", bg="#16213e")
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(left, length=170, mode='determinate')
        self.progress_bar.pack(padx=15, pady=5)

        self.main_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.main_frame.pack(side="right", fill="both", expand=True)

        self.work_area = tk.Frame(self.main_frame, bg="#1a1a2e")
        self.work_area.pack(fill="both", expand=True, padx=15, pady=10)

        bottom = tk.Frame(self.main_frame, bg="#16213e", height=55)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        self.btn_prev = tk.Button(bottom, text="◀ 上一步", font=("Microsoft YaHei", 11),
                                  fg="white", bg="#555", relief="flat", padx=20,
                                  command=self._prev_step, state="disabled")
        self.btn_prev.pack(side="left", padx=20, pady=10)

        self.btn_execute = tk.Button(bottom, text="▶ 执行当前步骤",
                                     font=("Microsoft YaHei", 12, "bold"),
                                     fg="white", bg="#e94560", relief="flat", padx=30,
                                     command=self._execute_step)
        self.btn_execute.pack(side="left", padx=10, pady=10)

        self.btn_next = tk.Button(bottom, text="下一步 ▶", font=("Microsoft YaHei", 11),
                                  fg="white", bg="#0f3460", relief="flat", padx=20,
                                  command=self._next_step, state="disabled")
        self.btn_next.pack(side="right", padx=20, pady=10)

        self.log_frame = tk.LabelFrame(self.main_frame, text="📋 日志",
                                        font=("Microsoft YaHei", 9),
                                        fg="#aaa", bg="#16213e", height=120)
        self.log_frame.pack(fill="x", side="bottom", padx=15, pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap="word",
                                                   bg="#0a0a1a", fg="#0f0",
                                                   font=("Consolas", 8), height=6, insertbackground="lime")
        self.log_text.pack(fill="both", expand=True, padx=3, pady=3)

        self._show_step(0)

    # ══════════════════════════════════════
    #  步骤切换
    # ══════════════════════════════════════

    def _goto_step(self, idx):
        if idx > self.current_step + 1:
            messagebox.showinfo("提示", "请按顺序完成每一步")
            return
        self._show_step(idx)

    def _prev_step(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _next_step(self):
        if self.current_step < len(self.STEPS) - 1:
            self._show_step(self.current_step + 1)

    def _show_step(self, idx):
        self.current_step = idx
        self.step_label.config(text=f"当前: {self.STEPS[idx]}")

        for i, btn in enumerate(self.step_buttons):
            if i == idx:
                btn.config(bg="#e94560")
            elif i < idx:
                btn.config(bg="#2a6041")
            else:
                btn.config(bg="#1a1a2e")

        self.btn_prev.config(state="normal" if idx > 0 else "disabled")
        self.btn_next.config(state="disabled")

        for w in self.work_area.winfo_children():
            w.destroy()

        step_builders = [
            self._build_step1_import,
            self._build_step2_episodes,
            self._build_step3_characters,
            self._build_step4_storyboard,
            self._build_step5_images,
            self._build_step6_tts,
            self._build_step7_video,
            self._build_step8_final,
        ]
        step_builders[idx]()

    def _log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def _enable_next(self):
        self.btn_next.config(state="normal")

    def _run_in_thread(self, func, callback=None):
        self.btn_execute.config(state="disabled", text="⏳ 执行中...")

        def worker():
            try:
                result = func()
                self.root.after(0, lambda: self._on_thread_done(result, callback))
            except Exception as e:
                self.root.after(0, lambda err=e: self._on_thread_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_thread_done(self, result, callback):
        self.btn_execute.config(state="normal", text="▶ 执行当前步骤")
        if callback:
            callback(result)

    def _on_thread_error(self, error):
        self.btn_execute.config(state="normal", text="▶ 执行当前步骤")
        self._log(f"❌ 错误: {error}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("错误", str(error))

    # ══════════════════════════════════════
    #  Step 1: 导入小说
    # ══════════════════════════════════════

    def _build_step1_import(self):
        f = self.work_area
        tk.Label(f, text="📖 第一步：导入小说文件",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 10))

        row = tk.Frame(f, bg="#1a1a2e")
        row.pack(fill="x", pady=5)
        self.novel_entry = tk.Entry(row, font=("Consolas", 11), width=60)
        self.novel_entry.pack(side="left", padx=(0, 10))
        if self.novel_path:
            self.novel_entry.insert(0, self.novel_path)
        tk.Button(row, text="浏览...", command=self._browse_novel,
                  bg="#0f3460", fg="white", font=("Microsoft YaHei", 10)).pack(side="left")

        tk.Label(f, text="📄 小说预览（前2000字）：",
                 font=("Microsoft YaHei", 10), fg="#aaa", bg="#1a1a2e").pack(anchor="w", pady=(15, 5))
        self.novel_preview = scrolledtext.ScrolledText(f, wrap="word", bg="#0a0a1a", fg="white",
                                                        font=("Microsoft YaHei", 10), height=20)
        self.novel_preview.pack(fill="both", expand=True)

        if self.novel_text:
            self.novel_preview.insert("1.0", self.novel_text[:2000] + "\n\n... (后略)")

        self.genre_label = tk.Label(f, text="", font=("Microsoft YaHei", 11),
                                     fg="#e94560", bg="#1a1a2e")
        self.genre_label.pack(anchor="w", pady=5)

        self.btn_execute.config(text="▶ 导入并检测类型")

    def _browse_novel(self):
        path = filedialog.askopenfilename(
            title="选择小说文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            self.novel_entry.delete(0, "end")
            self.novel_entry.insert(0, path)

    # ══════════════════════════════════════
    #  Step 2: 分集预览
    # ══════════════════════════════════════

    def _build_step2_episodes(self):
        f = self.work_area
        tk.Label(f, text="✂️ 第二步：分集预览（可编辑后确认）",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 10))

        pane = tk.PanedWindow(f, orient="horizontal", bg="#1a1a2e", sashwidth=5)
        pane.pack(fill="both", expand=True)

        left_f = tk.Frame(pane, bg="#16213e")
        pane.add(left_f, width=300)

        tk.Label(left_f, text=f"共 {len(self.episodes)} 集",
                 font=("Microsoft YaHei", 11, "bold"), fg="white", bg="#16213e").pack(pady=5)

        self.ep_listbox = tk.Listbox(left_f, bg="#0a0a1a", fg="white",
                                      font=("Microsoft YaHei", 10),
                                      selectbackground="#e94560", height=25)
        self.ep_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.ep_listbox.bind("<<ListboxSelect>>", self._on_ep_list_select)

        for ep in self.episodes:
            title = ep.get("title", f"第{ep['episode']}集")
            chars = len(ep.get("text", ""))
            self.ep_listbox.insert("end", f"第{ep['episode']}集: {title} ({chars}字)")

        right_f = tk.Frame(pane, bg="#1a1a2e")
        pane.add(right_f)

        tk.Label(right_f, text="📝 选中集数的内容（可编辑）：",
                 font=("Microsoft YaHei", 10), fg="#aaa", bg="#1a1a2e").pack(anchor="w", pady=5)

        self.ep_edit = scrolledtext.ScrolledText(right_f, wrap="word", bg="#0a0a1a", fg="white",
                                                  font=("Microsoft YaHei", 10))
        self.ep_edit.pack(fill="both", expand=True)

        btn_row = tk.Frame(right_f, bg="#1a1a2e")
        btn_row.pack(fill="x", pady=5)
        tk.Button(btn_row, text="💾 保存修改", command=self._save_ep_edit,
                  bg="#2a6041", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

        self.btn_execute.config(text="▶ AI智能分集")
        if self.episodes:
            self._enable_next()

    def _on_ep_list_select(self, event=None):
        sel = self.ep_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._selected_ep_idx = idx
        self.ep_edit.delete("1.0", "end")
        self.ep_edit.insert("1.0", self.episodes[idx].get("text", ""))

    def _save_ep_edit(self):
        sel = self.ep_listbox.curselection()
        if sel:
            self._selected_ep_idx = sel[0]
        idx = getattr(self, '_selected_ep_idx', None)
        if idx is None:
            messagebox.showinfo("提示", "请先选择一集")
            return
        self.episodes[idx]["text"] = self.ep_edit.get("1.0", "end").strip()
        self._log(f"✅ 第{idx+1}集内容已保存")

    # ══════════════════════════════════════
    #  Step 3: 角色管理
    # ══════════════════════════════════════

    def _build_step3_characters(self):
        f = self.work_area
        tk.Label(f, text="👥 第三步：角色提取（中英文外貌 + 可编辑）",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 5))

        lock_f = tk.Frame(f, bg="#1a1a2e")
        lock_f.pack(fill="x", pady=3)

        if self.characters_locked:
            self.lock_label = tk.Label(lock_f,
                text="🔒 角色外貌已锁定（所有集数使用统一形象）",
                font=("Microsoft YaHei", 11, "bold"), fg="#00ff88", bg="#1a1a2e")
        else:
            self.lock_label = tk.Label(lock_f,
                text="⚠️ 角色外貌未锁定（切换集数可能导致形象不一致）",
                font=("Microsoft YaHei", 11, "bold"), fg="#ff6600", bg="#1a1a2e")
        self.lock_label.pack(side="left")

        lock_btn_text = "🔓 解锁修改" if self.characters_locked else "🔒 锁定全局形象"
        self.lock_btn = tk.Button(lock_f, text=lock_btn_text,
                                   command=self._toggle_char_lock,
                                   bg="#e94560" if not self.characters_locked else "#2a6041",
                                   fg="white", font=("Microsoft YaHei", 10))
        self.lock_btn.pack(side="right", padx=10)

        cols = ("name", "gender", "age", "voice", "appearance_cn")
        self.char_tree = ttk.Treeview(f, columns=cols, show="headings", height=8)
        self.char_tree.heading("name", text="姓名")
        self.char_tree.heading("gender", text="性别")
        self.char_tree.heading("age", text="年龄")
        self.char_tree.heading("voice", text="配音")
        self.char_tree.heading("appearance_cn", text="中文外貌描述")
        self.char_tree.column("name", width=80)
        self.char_tree.column("gender", width=50)
        self.char_tree.column("age", width=50)
        self.char_tree.column("voice", width=60)
        self.char_tree.column("appearance_cn", width=500)
        self.char_tree.pack(fill="x", pady=5)
        self.char_tree.bind("<<TreeviewSelect>>", self._on_char_select)

        for c in self.characters:
            self.char_tree.insert("", "end", values=(
                c.get("name", ""), c.get("gender", ""), c.get("age", ""),
                c.get("voice", "少年"),
                c.get("appearance_cn", c.get("appearance", ""))[:80]
            ))

        edit_f = tk.LabelFrame(f, text="✏️ 编辑选中角色", font=("Microsoft YaHei", 10),
                               fg="white", bg="#16213e", padx=10, pady=10)
        edit_f.pack(fill="both", expand=True, pady=5)

        grid = tk.Frame(edit_f, bg="#16213e")
        grid.pack(fill="x")
        labels = ["姓名:", "性别:", "年龄:", "配音:"]
        self.char_entries = {}
        for i, lbl in enumerate(labels):
            tk.Label(grid, text=lbl, fg="white", bg="#16213e",
                     font=("Microsoft YaHei", 10)).grid(row=0, column=i*2, padx=5, sticky="e")
            if lbl == "配音:":
                # ★ 配音使用下拉框，显示所有可选音色
                try:
                    from tts_engine import get_voice_options
                    voice_opts = get_voice_options()
                except:
                    voice_opts = ["旁白男", "旁白女", "硬汉", "少年", "少女", "霸总", "反派", "干练女", "御姐", "沉稳男"]
                import tkinter.ttk as _ttk
                combo = _ttk.Combobox(grid, values=voice_opts, width=10, state="readonly",
                                      font=("Microsoft YaHei", 9))
                combo.grid(row=0, column=i*2+1, padx=5)
                combo.set(voice_opts[0] if voice_opts else "旁白男")
                self.char_entries[lbl] = combo
            else:
                entry = tk.Entry(grid, font=("Consolas", 10), width=10)
                entry.grid(row=0, column=i*2+1, padx=5)
                self.char_entries[lbl] = entry

        tk.Label(edit_f, text="中文外貌描述（修改后英文会自动同步翻译）:",
                 fg="#e94560", bg="#16213e", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.char_appearance_cn = scrolledtext.ScrolledText(edit_f, wrap="word", bg="#0a0a1a", fg="white",
                                                             font=("Microsoft YaHei", 10), height=3, insertbackground="white")
        self.char_appearance_cn.pack(fill="x")

        tk.Label(edit_f, text="英文外貌描述（用于AI生图，保证角色一致性）:",
                 fg="#aaa", bg="#16213e", font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(5, 0))
        self.char_appearance_en = scrolledtext.ScrolledText(edit_f, wrap="word", bg="#0a0a1a", fg="#88ccff",
                                                             font=("Consolas", 10), height=3, insertbackground="white")
        self.char_appearance_en.pack(fill="x")

        btn_row = tk.Frame(edit_f, bg="#16213e")
        btn_row.pack(fill="x", pady=8)
        tk.Button(btn_row, text="💾 保存角色修改", command=self._save_char_edit,
                  bg="#2a6041", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="🔄 中文→英文翻译", command=self._translate_char_cn_to_en,
                  bg="#0f3460", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="🔄 英文→中文翻译", command=self._translate_char_en_to_cn,
                 bg="#0f3460", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="➕ 手动添加角色", command=self._add_char,
                  bg="#0f3460", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="🗑 删除选中", command=self._delete_char,
                  bg="#8b0000", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="📷 上传参考图", command=self._upload_reference_image,
                bg="#9b59b6", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Button(btn_row, text="🎨 AI生成定妆照", command=self._generate_portrait_for_char,
                bg="#d4ac0d", fg="black", font=("Microsoft YaHei", 10, "bold")).pack(side="left", padx=5)
        tk.Button(btn_row, text="🖼 查看定妆照", command=self._show_portraits,
                bg="#8e44ad", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

        self.btn_execute.config(text="▶ AI提取角色")
        if self.characters:
            self._enable_next()



    def _generate_portrait_for_char(self):
        """AI生成选中角色的定妆照（正面/半身/全身）"""
        sel = self.char_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在角色列表中选择一个角色")
            return
        if not self.gemini:
            messagebox.showerror("错误", "请先完成第一步导入（初始化引擎）")
            return
        if not self.char_manager:
            messagebox.showerror("错误", "角色管理器未初始化")
            return

        values = self.char_tree.item(sel[0], "values")
        char_name = values[0]

        import tkinter.simpledialog as simpledialog
        choice = simpledialog.askstring(
            "生成定妆照",
            f"为【{char_name}】生成AI定妆照\n\n"
            f"请选择生成类型:\n"
            f"  1 = 仅正面头像\n"
            f"  2 = 仅半身照\n"
            f"  3 = 仅全身照\n"
            f"  4 = 全套（正面+半身+全身）\n"
            f"  ───── 三视图模式 ─────\n"
            f"  5 = 三视图（正面全身+侧面全身+背面全身）\n"
            f"  6 = 仅正面全身\n"
            f"  7 = 仅侧面全身\n"
            f"  8 = 仅背面全身\n",
            initialvalue="5"
        )
        if not choice:
            return

        type_map = {
            "1": ["face_front"],
            "2": ["half_body"],
            "3": ["full_body"],
            "4": ["face_front", "half_body", "full_body"],
            "5": ["tri_front", "tri_side", "tri_back"],
            "6": ["tri_front"],
            "7": ["tri_side"],
            "8": ["tri_back"],
        }
        types = type_map.get(choice)
        if not types:
            messagebox.showinfo("提示", "无效选择，请输入 1/2/3/4")
            return

        self._log(f"🎨 开始为【{char_name}】生成定妆照: {types}")

        def do_gen():
            results = self.char_manager.generate_all_portraits(
                char_name, self.gemini, style_prefix=self.char_manager.visual_prefix, types=types
            )
            return results

        def on_done(results):
            success = sum(1 for v in results.values() if v is not None)
            total = len(results)
            self._log(f"✅ 【{char_name}】定妆照完成: {success}/{total} 张成功")
            if success > 0:
                self._log(f"   路径: {list(results.values())}")
                messagebox.showinfo("生成完成",
                    f"【{char_name}】定妆照生成 {success}/{total} 张\n\n"
                    + "\n".join(f"  {k}: {'✅' if v else '❌'}" for k, v in results.items())
                )
            else:
                messagebox.showerror("失败", f"【{char_name}】所有定妆照生成失败")

        self._run_in_thread(do_gen, on_done)

    def _show_portraits(self):
        """弹窗显示选中角色的所有定妆照"""
        sel = self.char_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在角色列表中选择一个角色")
            return
        if not self.char_manager:
            messagebox.showerror("错误", "角色管理器未初始化")
            return

        values = self.char_tree.item(sel[0], "values")
        char_name = values[0]

        all_refs = self.char_manager.get_all_reference_images(char_name)
        if not all_refs:
            messagebox.showinfo("无定妆照", f"【{char_name}】尚未生成或上传定妆照\n\n请先点击「🎨 AI生成定妆照」或「📷 上传参考图」")
            return

        win = tk.Toplevel(self.root)
        win.title(f"🖼 {char_name} 的定妆照")
        win.configure(bg="#1a1a2e")
        win.grab_set()

        tk.Label(win, text=f"👤 {char_name} — 定妆照一览",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(pady=10)

        frame = tk.Frame(win, bg="#1a1a2e")
        frame.pack(padx=15, pady=10)

        _photo_refs = []
        col = 0
        for img_type, img_path in all_refs.items():
            if not os.path.exists(img_path):
                continue
            try:
                img = Image.open(img_path)
                img.thumbnail((250, 350))
                photo = ImageTk.PhotoImage(img)
                _photo_refs.append(photo)

                cell = tk.Frame(frame, bg="#16213e", padx=5, pady=5)
                cell.grid(row=0, column=col, padx=8, pady=5)

                lbl = tk.Label(cell, image=photo, bg="#16213e")
                lbl.pack()

                type_names = {
                    "face_front": "正面头像",
                    "face_side": "侧面头像",
                    "face_back": "背面",
                    "half_body": "半身照",
                    "full_body": "全身照",
                "tri_front": "三视图-正面",
                "tri_side": "三视图-侧面",
                "tri_back": "三视图-背面",
                }
                type_cn = type_names.get(img_type, img_type)
                tk.Label(cell, text=type_cn,
                         font=("Microsoft YaHei", 10, "bold"),
                         fg="#e94560", bg="#16213e").pack(pady=(5, 0))
                tk.Label(cell, text=os.path.basename(img_path),
                         font=("Consolas", 8),
                         fg="#888", bg="#16213e").pack()

                col += 1
            except Exception as e:
                tk.Label(frame, text=f"{img_type}\n加载失败: {e}",
                         fg="red", bg="#1a1a2e").grid(row=0, column=col, padx=8)
                col += 1

        win._photo_refs = _photo_refs  # 防GC

        btn_frame = tk.Frame(win, bg="#1a1a2e")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="关闭", command=win.destroy,
                  bg="#555", fg="white", font=("Microsoft YaHei", 10),
                  padx=20).pack()

    def _upload_reference_image(self):
        """Upload reference image for selected character"""
        sel = self.char_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在角色列表中选择一个角色")
            return
        values = self.char_tree.item(sel[0], "values")
        char_name = values[0]

        import tkinter.simpledialog as simpledialog
        type_map = {"1": "face_front", "2": "half_body", "3": "full_body", "4": "tri_front", "5": "tri_side", "6": "tri_back"}
        choice = simpledialog.askstring(
            "参考图类型",
            f"为【{char_name}】上传参考图\n\n请输入编号:\n  1 = 正脸 (face_front)\n  2 = 半身 (half_body)\n  3 = 全身 (full_body)",
            initialvalue="1"
        )
        if not choice or choice not in type_map:
            if choice:
                messagebox.showinfo("提示", "无效的编号，请输入 1/2/3")
            return
        image_type = type_map[choice]

        file_path = filedialog.askopenfilename(
            title=f"为【{char_name}】选择{image_type}参考图",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        if self.char_manager:
            self.char_manager.set_reference_image(char_name, image_type, file_path)
            self.char_manager.save()
            ref_count = len(self.char_manager.get_all_reference_images(char_name))
            self._log(f"📷 已为【{char_name}】设置 {image_type} 参考图: {file_path}")
            self._log(f"   该角色当前共 {ref_count} 张参考图")
            messagebox.showinfo("成功", f"已为【{char_name}】设置 {image_type} 参考图\n\n路径: {file_path}")
        else:
            messagebox.showerror("错误", "角色管理器未初始化")

    def _on_char_select(self, event=None):
        sel = self.char_tree.selection()
        if not sel:
            return
        values = self.char_tree.item(sel[0], "values")
        keys = ["姓名:", "性别:", "年龄:", "配音:"]
        for i, key in enumerate(keys):
            widget = self.char_entries[key]
            if key == "配音:" and hasattr(widget, 'set'):
                widget.set(values[i] if i < len(values) else "")
            else:
                widget.delete(0, "end")
                widget.insert(0, values[i] if i < len(values) else "")

        name = values[0]
        for c in self.characters:
            if c.get("name") == name:
                self.char_appearance_cn.delete("1.0", "end")
                self.char_appearance_cn.insert("1.0", c.get("appearance_cn", ""))
                self.char_appearance_en.delete("1.0", "end")
                self.char_appearance_en.insert("1.0", c.get("appearance_en", c.get("appearance", "")))
                self._orig_char_cn = c.get("appearance_cn", "")
                self._orig_char_en = c.get("appearance_en", c.get("appearance", ""))
                break

    def _save_char_edit(self):
        sel = self.char_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个角色")
            return
        item = sel[0]
        old_name = self.char_tree.item(item, "values")[0]
        new_name = self.char_entries["姓名:"].get().strip()
        new_gender = self.char_entries["性别:"].get().strip()
        new_age = self.char_entries["年龄:"].get().strip()
        new_voice = self.char_entries["配音:"].get().strip()
        new_cn = self.char_appearance_cn.get("1.0", "end").strip()
        new_en = self.char_appearance_en.get("1.0", "end").strip()

        # 检测中英文变化
        orig_cn = getattr(self, "_orig_char_cn", "")
        orig_en = getattr(self, "_orig_char_en", "")
        cn_changed = (new_cn != orig_cn)
        en_changed = (new_en != orig_en)

        self.char_tree.item(item, values=(new_name, new_gender, new_age, new_voice, new_cn[:80]))

        for c in self.characters:
            if c.get("name") == old_name:
                c["name"] = new_name
                c["gender"] = new_gender
                c["age"] = new_age
                c["voice"] = new_voice
                c["appearance_cn"] = new_cn
                c["appearance_en"] = new_en
                break

        if self.gemini:
            self.gemini.set_character_profiles(self.characters)
        if self.char_manager:
            self.char_manager.update_characters(self.characters)

        self._log(f"✅ 角色 {new_name} 已更新（中英文外貌已保存）")

        # 自动双向翻译
        if cn_changed and not en_changed and new_cn:
            self._log(f"🔄 检测到中文外貌修改，自动翻译为英文...")
            self._auto_translate_char_cn_to_en(new_name, new_cn)
        elif en_changed and not cn_changed and new_en:
            self._log(f"🔄 检测到英文外貌修改，自动翻译为中文...")
            self._auto_translate_char_en_to_cn(new_name, new_en)
        elif cn_changed and en_changed:
            self._log(f"📝 中英文均已修改，保持当前内容")

        # 更新原始值
        self._orig_char_cn = new_cn
        self._orig_char_en = new_en

    def _auto_translate_char_cn_to_en(self, char_name, cn_text):
        """角色保存时自动 中文→英文"""
        def do_translate():
            return self.gemini.translate_cn_to_en(cn_text)
        def on_done(en_text):
            if en_text:
                self.char_appearance_en.delete("1.0", "end")
                self.char_appearance_en.insert("1.0", en_text)
                for c in self.characters:
                    if c.get("name") == char_name:
                        c["appearance_en"] = en_text
                        break
                if self.gemini:
                    self.gemini.set_character_profiles(self.characters)
                self._orig_char_en = en_text
                self._log(f"✅ 角色 {char_name} 英文外貌已自动更新")
            else:
                self._log(f"❌ 自动翻译失败")
        self._run_in_thread(do_translate, on_done)

    def _auto_translate_char_en_to_cn(self, char_name, en_text):
        """角色保存时自动 英文→中文"""
        def do_translate():
            return self.gemini.translate_en_to_cn(en_text)
        def on_done(cn_text):
            if cn_text:
                self.char_appearance_cn.delete("1.0", "end")
                self.char_appearance_cn.insert("1.0", cn_text)
                for c in self.characters:
                    if c.get("name") == char_name:
                        c["appearance_cn"] = cn_text
                        break
                self._orig_char_cn = cn_text
                self._log(f"✅ 角色 {char_name} 中文外貌已自动更新")
            else:
                self._log(f"❌ 自动翻译失败")
        self._run_in_thread(do_translate, on_done)

    def _translate_char_cn_to_en(self):
        cn_text = self.char_appearance_cn.get("1.0", "end").strip()
        if not cn_text:
            messagebox.showinfo("提示", "请先填写中文外貌描述")
            return
        if not self.gemini:
            messagebox.showerror("错误", "请先完成第一步导入")
            return

    def _translate_char_en_to_cn(self):
        """手动按钮：英文→中文翻译角色外貌"""
        en_text = self.char_appearance_en.get("1.0", "end").strip()
        if not en_text:
            messagebox.showinfo("提示", "请先填写英文外貌描述")
            return
        if not self.gemini:
            messagebox.showerror("错误", "请先完成第一步导入（初始化引擎）")
            return

        def do_translate():
            return self.gemini.translate_en_to_cn(en_text)

        def on_done(cn_text):
            if cn_text:
                self.char_appearance_cn.delete("1.0", "end")
                self.char_appearance_cn.insert("1.0", cn_text)
                self._orig_char_cn = cn_text
                self._log(f"✅ 翻译完成（英文→中文）")
            else:
                self._log(f"❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)

        def do_translate():
            return self.gemini.translate_cn_to_en(cn_text)

        def on_done(en_text):
            if en_text:
                self.char_appearance_en.delete("1.0", "end")
                self.char_appearance_en.insert("1.0", en_text)
                self._log(f"✅ 翻译完成")
            else:
                self._log(f"❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)

    def _add_char(self):
        new = {
            "name": "新角色", "gender": "male", "age": "25",
            "voice": "少年", "appearance_cn": "", "appearance_en": ""
        }
        self.characters.append(new)
        self.char_tree.insert("", "end", values=("新角色", "male", "25", "少年", ""))
        self._log("➕ 已添加新角色，请编辑")

    def _delete_char(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        name = self.char_tree.item(sel[0], "values")[0]
        self.char_tree.delete(sel[0])
        self.characters = [c for c in self.characters if c.get("name") != name]
        self._log(f"🗑 已删除角色: {name}")

    def _toggle_char_lock(self):
        if not self.characters_locked:
            if not self.characters:
                messagebox.showinfo("提示", "请先提取或添加角色")
                return
            missing = [c.get("name") for c in self.characters
                       if not c.get("appearance_en", "").strip()]
            if missing:
                messagebox.showwarning("警告",
                    f"以下角色缺少英文外貌描述，锁定后生图可能不一致：\n{', '.join(missing)}\n\n建议先补充英文外貌再锁定。")
            self.characters_locked = True
            self._save_locked_characters()
            self._log("🔒 角色外貌已锁定！所有集数将使用统一形象")
        else:
            if messagebox.askyesno("确认", "解锁后切换集数可能导致角色形象不一致，确定解锁吗？"):
                self.characters_locked = False
                self._log("🔓 角色外貌已解锁")
        self._show_step(2)

    def _save_locked_characters(self):
        lock_path = os.path.join(SCRIPTS_DIR, "characters_locked.json")
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(self.characters, f, ensure_ascii=False, indent=2)
        self._log(f"💾 角色档案已保存: {lock_path}")

    def _load_locked_characters(self):
        lock_path = os.path.join(SCRIPTS_DIR, "characters_locked.json")
        if os.path.exists(lock_path):
            with open(lock_path, "r", encoding="utf-8") as f:
                self.characters = json.loads(f.read())
            self.characters_locked = True
            if self.gemini:
                self.gemini.set_character_profiles(self.characters)
            if self.char_manager:
                self.char_manager.update_characters(self.characters)
            return True
        return False

    # ══════════════════════════════════════
    #  Step 4: 分镜剧本
    # ══════════════════════════════════════

    def _build_step4_storyboard(self):
        f = self.work_area
        ep_num = self.current_ep + 1
        tk.Label(f, text=f"📝 第四步：分镜剧本 — 第{ep_num}集（中英文对照）",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 10))

        cols = ("id", "type", "speaker", "dialogue", "visual_cn")
        self.scene_tree = ttk.Treeview(f, columns=cols, show="headings", height=10)
        self.scene_tree.heading("id", text="#")
        self.scene_tree.heading("type", text="类型")
        self.scene_tree.heading("speaker", text="说话人")
        self.scene_tree.heading("dialogue", text="台词")
        self.scene_tree.heading("visual_cn", text="画面描述(中文)")
        self.scene_tree.column("id", width=35)
        self.scene_tree.column("type", width=60)
        self.scene_tree.column("speaker", width=70)
        self.scene_tree.column("dialogue", width=200)
        self.scene_tree.column("visual_cn", width=450)
        self.scene_tree.pack(fill="x", pady=5)
        self.scene_tree.bind("<<TreeviewSelect>>", self._on_scene_select)

        # ★ 自动加载已有剧本
        if not self.storyboard:
            ep_num_s4 = self.current_ep + 1
            script_path_s4 = os.path.join(SCRIPTS_DIR, f"ep{ep_num_s4:03d}_script.json")
            if os.path.exists(script_path_s4):
                try:
                    with open(script_path_s4, "r", encoding="utf-8") as ff:
                        self.storyboard = json.load(ff)
                    self._log(f"📂 自动加载第{ep_num_s4}集剧本")
                except:
                    pass

        if self.storyboard:
            for s in self.storyboard.get("scenes", []):
                self.scene_tree.insert("", "end", values=(
                    s.get("scene_id", ""), s.get("scene_type", ""),
                    s.get("speaker", ""), s.get("dialogue", "")[:30],
                    s.get("visual_description_cn", "")[:60]
                ))

        edit_f = tk.LabelFrame(f, text="✏️ 编辑选中场景", font=("Microsoft YaHei", 10),
                               fg="white", bg="#16213e", padx=10, pady=10)
        edit_f.pack(fill="both", expand=True, pady=5)

        row1 = tk.Frame(edit_f, bg="#16213e")
        row1.pack(fill="x", pady=3)
        tk.Label(row1, text="说话人:", fg="white", bg="#16213e").pack(side="left")
        self.scene_speaker = tk.Entry(row1, font=("Consolas", 10), width=15)
        self.scene_speaker.pack(side="left", padx=10)
        tk.Label(row1, text="类型:", fg="white", bg="#16213e").pack(side="left")
        self.scene_type = ttk.Combobox(row1, values=["dialogue", "action", "narration"], width=10)
        self.scene_type.pack(side="left", padx=10)

        tk.Label(edit_f, text="台词:", fg="white", bg="#16213e").pack(anchor="w")
        self.scene_dialogue = tk.Entry(edit_f, font=("Microsoft YaHei", 10), width=80, insertbackground="white")
        self.scene_dialogue.pack(fill="x", pady=3)

        tk.Label(edit_f, text="🇨🇳 画面描述（中文，修改后可翻译为英文）:",
                 fg="#e94560", bg="#16213e", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")
        self.scene_visual_cn = scrolledtext.ScrolledText(edit_f, wrap="word", bg="#0a0a1a", fg="white",
                                                          font=("Microsoft YaHei", 9), height=3, insertbackground="white")
        self.scene_visual_cn.pack(fill="x", pady=2)

        tk.Label(edit_f, text="🇺🇸 画面描述（英文Prompt，用于AI生图）:",
                 fg="#aaa", bg="#16213e", font=("Microsoft YaHei", 10)).pack(anchor="w")
        self.scene_visual_en = scrolledtext.ScrolledText(edit_f, wrap="word", bg="#0a0a1a", fg="#88ccff",
                                                          font=("Consolas", 9), height=3, insertbackground="white")
        self.scene_visual_en.pack(fill="x", pady=2)

        btn_row = tk.Frame(edit_f, bg="#16213e")
        btn_row.pack(fill="x", pady=5)
        tk.Button(btn_row, text="💾 保存场景修改", command=self._save_scene_edit,
                  bg="#2a6041", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="🔄 中文→英文翻译", command=self._translate_scene_cn_to_en,
                  bg="#0f3460", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="➕ 添加场景", command=self._add_scene,
                  bg="#0f3460", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="🗑删除场景", command=self._delete_scene,
                 bg="#8b0000", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="🔄 英文→中文翻译", command=self._translate_scene_en_to_cn,
                 bg="#0f3460", fg="white").pack(side="left", padx=5)

        self.btn_execute.config(text="▶ AI生成分镜剧本")
        if self.storyboard and self.storyboard.get("scenes"):
            self._enable_next()

    def _on_scene_select(self, event=None):
        sel = self.scene_tree.selection()
        if not sel:
            return
        vals = self.scene_tree.item(sel[0], "values")
        scene_id = int(vals[0]) if vals[0] else 0
        if self.storyboard:
            for s in self.storyboard.get("scenes", []):
                if s.get("scene_id") == scene_id:
                    self.scene_speaker.delete(0, "end")
                    self.scene_speaker.insert(0, s.get("speaker", ""))
                    self.scene_type.set(s.get("scene_type", "action"))
                    self.scene_dialogue.delete(0, "end")
                    self.scene_dialogue.insert(0, s.get("dialogue", ""))
                    self.scene_visual_cn.delete("1.0", "end")
                    self.scene_visual_cn.insert("1.0", s.get("visual_description_cn", ""))
                    self.scene_visual_en.delete("1.0", "end")
                    self.scene_visual_en.insert("1.0", s.get("visual_description_en",
                                                              s.get("visual_description", "")))
                    # 记录原始值，用于检测变化
                    self._orig_cn = s.get("visual_description_cn", "")
                    self._orig_en = s.get("visual_description_en", s.get("visual_description", ""))
                    break

    def _save_scene_edit(self):
        sel = self.scene_tree.selection()
        if not sel:
            return
        vals = self.scene_tree.item(sel[0], "values")
        scene_id = int(vals[0]) if vals[0] else 0

        new_speaker = self.scene_speaker.get().strip()
        new_type = self.scene_type.get()
        new_dialogue = self.scene_dialogue.get().strip()
        new_cn = self.scene_visual_cn.get("1.0", "end").strip()
        new_en = self.scene_visual_en.get("1.0", "end").strip()

        # 检测中英文哪个被修改了
        orig_cn = getattr(self, "_orig_cn", "")
        orig_en = getattr(self, "_orig_en", "")
        cn_changed = (new_cn != orig_cn)
        en_changed = (new_en != orig_en)

        # 先保存当前值
        self.scene_tree.item(sel[0], values=(
            scene_id, new_type, new_speaker, new_dialogue[:30], new_cn[:60]
        ))

        if self.storyboard:
            for s in self.storyboard.get("scenes", []):
                if s.get("scene_id") == scene_id:
                    s["speaker"] = new_speaker
                    s["scene_type"] = new_type
                    s["dialogue"] = new_dialogue
                    s["visual_description_cn"] = new_cn
                    s["visual_description_en"] = new_en
                    s["visual_description"] = new_en
                    break

        self._log(f"✅ 场景 {scene_id} 已更新")

        # 自动双向翻译
        if cn_changed and not en_changed and new_cn:
            self._log(f"🔄 检测到中文修改，自动翻译为英文...")
            self._auto_translate_cn_to_en(scene_id, new_cn)
        elif en_changed and not cn_changed and new_en:
            self._log(f"🔄 检测到英文修改，自动翻译为中文...")
            self._auto_translate_en_to_cn(scene_id, new_en)
        elif cn_changed and en_changed:
            self._log(f"📝 中英文均已修改，保持当前内容")

        # 更新原始值
        self._orig_cn = new_cn
        self._orig_en = new_en

        # ★ 同步保存剧本到文件（确保语音合成读取最新数据）
        self._save_storyboard()

    def _auto_translate_cn_to_en(self, scene_id, cn_text):
        """保存时自动 中文→英文"""
        def do_translate():
            return self.gemini.translate_cn_to_en(cn_text)
        def on_done(en_text):
            if en_text:
                self.scene_visual_en.delete("1.0", "end")
                self.scene_visual_en.insert("1.0", en_text)
                # 同步到 storyboard
                if self.storyboard:
                    for s in self.storyboard.get("scenes", []):
                        if s.get("scene_id") == scene_id:
                            s["visual_description_en"] = en_text
                            s["visual_description"] = en_text
                            break
                self._orig_en = en_text
                self._log(f"✅ 自动翻译完成：中文→英文")
            else:
                self._log(f"❌ 自动翻译失败")
        self._run_in_thread(do_translate, on_done)

    def _auto_translate_en_to_cn(self, scene_id, en_text):
        """保存时自动 英文→中文"""
        def do_translate():
            return self.gemini.translate_en_to_cn(en_text)
        def on_done(cn_text):
            if cn_text:
                self.scene_visual_cn.delete("1.0", "end")
                self.scene_visual_cn.insert("1.0", cn_text)
                # 同步到 storyboard
                if self.storyboard:
                    for s in self.storyboard.get("scenes", []):
                        if s.get("scene_id") == scene_id:
                            s["visual_description_cn"] = cn_text
                            break
                self._orig_cn = cn_text
                self._log(f"✅ 自动翻译完成：英文→中文")
            else:
                self._log(f"❌ 自动翻译失败")
        self._run_in_thread(do_translate, on_done)

    def _translate_scene_cn_to_en(self):
        cn_text = self.scene_visual_cn.get("1.0", "end").strip()
        if not cn_text:
            messagebox.showinfo("提示", "请先填写中文画面描述")
            return

    def _translate_scene_en_to_cn(self):
        """手动按钮：英文→中文翻译"""
        en_text = self.scene_visual_en.get("1.0", "end").strip()
        if not en_text:
            messagebox.showinfo("提示", "请先填写英文画面描述")
            return

        def do_translate():
            return self.gemini.translate_en_to_cn(en_text)

        def on_done(cn_text):
            if cn_text:
                self.scene_visual_cn.delete("1.0", "end")
                self.scene_visual_cn.insert("1.0", cn_text)
                self._orig_cn = cn_text
                self._log(f"✅ 场景描述翻译完成（英文→中文）")
            else:
                self._log(f"❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)

        def do_translate():
            return self.gemini.translate_cn_to_en(cn_text)

        def on_done(en_text):
            if en_text:
                self.scene_visual_en.delete("1.0", "end")
                self.scene_visual_en.insert("1.0", en_text)
                self._log(f"✅ 场景描述翻译完成")
            else:
                self._log(f"❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)

    def _add_scene(self):
        if not self.storyboard:
            self.storyboard = {"scenes": []}
        scenes = self.storyboard["scenes"]
        new_id = max([s.get("scene_id", 0) for s in scenes], default=0) + 1
        new_scene = {
            "scene_id": new_id, "scene_type": "action", "speaker": "",
            "dialogue": "", "visual_description_en": "", "visual_description_cn": "",
            "visual_description": "", "characters": [], "duration": 1.2
        }
        scenes.append(new_scene)
        self.scene_tree.insert("", "end", values=(new_id, "action", "", "", ""))

    def _delete_scene(self):
        sel = self.scene_tree.selection()
        if not sel:
            return
        vals = self.scene_tree.item(sel[0], "values")
        scene_id = int(vals[0]) if vals[0] else 0
        self.scene_tree.delete(sel[0])
        if self.storyboard:
            self.storyboard["scenes"] = [
                s for s in self.storyboard["scenes"] if s.get("scene_id") != scene_id
            ]
    def _save_storyboard(self):
        """保存当前剧本到文件"""
        if not self.storyboard:
            return
        ep_num = self.current_ep + 1
        script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
        try:
            os.makedirs(SCRIPTS_DIR, exist_ok=True)
            with open(script_path, "w", encoding="utf-8") as ff:
                json.dump(self.storyboard, ff, ensure_ascii=False, indent=2)
            self._log(f"💾 剧本已保存: {script_path}")
        except Exception as e:
            self._log(f"❌ 剧本保存失败: {e}")


    # ══════════════════════════════════════
    #  Step 5: 图片生成
    # ══════════════════════════════════════

    def _build_step5_images(self):
        f = self.work_area
        ep_num = self.current_ep + 1
        tk.Label(f, text=f"🎨 第五步：图片生成 — 第{ep_num}集",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 5))

        # ? ???????
        img_model_frame = tk.Frame(f, bg="#1a1a2e")
        img_model_frame.pack(fill="x", padx=5, pady=(0, 5))
        tk.Label(img_model_frame, text="🖼️ 图生模型:", fg="#aaa", bg="#1a1a2e",
                 font=("Microsoft YaHei", 9)).pack(side="left")
        self._img_model_var = tk.StringVar()
        _img_registry = get_registry()
        _img_engines = _img_registry.list_image_engines()
        _img_active = _img_registry.get_active_names().get("image", "")
        self._img_model_var.set(_img_active)
        self._img_model_combo = ttk.Combobox(img_model_frame, textvariable=self._img_model_var,
                                              values=_img_engines, state="readonly", width=20)
        self._img_model_combo.pack(side="left", padx=(5, 0))
        self._img_model_combo.bind("<<ComboboxSelected>>", self._on_image_model_change)

        pane = tk.PanedWindow(f, orient="horizontal", bg="#1a1a2e", sashwidth=5)
        pane.pack(fill="both", expand=True)

        # === 左侧：场景列表 ===
        left_f = tk.Frame(pane, bg="#16213e")
        pane.add(left_f, width=320)

        tk.Label(left_f, text="场景图片列表（🟢已生成 ⬜未生成）",
                 font=("Microsoft YaHei", 10, "bold"),
                 fg="white", bg="#16213e").pack(pady=5)

        self.img_listbox = tk.Listbox(left_f, bg="#0a0a1a", fg="white",
                                       font=("Microsoft YaHei", 10),
                                       selectbackground="#e94560",
                                       exportselection=False,
                                       height=15)
        self.img_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.img_listbox.bind("<<ListboxSelect>>", self._on_img_select)

        # ★ 记录当前选中的场景索引
        self._selected_img_idx = None

        # ★ 自动加载已有剧本（断点续传）
        if not self.storyboard:
            ep_num = self.current_ep + 1
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            if os.path.exists(script_path):
                try:
                    with open(script_path, "r", encoding="utf-8") as ff:
                        self.storyboard = json.load(ff)
                    self._log(f"📂 自动加载第{ep_num}集剧本（{len(self.storyboard.get('scenes',[]))}个场景）")
                except Exception as e:
                    self._log(f"❌ 剧本加载失败: {e}")

        if self.storyboard:
            self._scan_existing_images()
            for s in self.storyboard.get("scenes", []):
                sid = s.get("scene_id", 0)
                has_img = any(r.get("scene_id") == sid and r.get("success")
                              for r in self.image_results)
                status = "🟢" if has_img else "⬜"
                dlg = s.get("dialogue", "")[:12]
                cn = s.get("visual_description_cn", "")[:15]
                self.img_listbox.insert("end", f"{status} 场景{sid}: {dlg or cn}")

        btn_frame = tk.Frame(left_f, bg="#16213e")
        btn_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(btn_frame, text="🎨 生成选中场景", command=self._generate_single_image,
                  bg="#e94560", fg="white", font=("Microsoft YaHei", 9)).pack(fill="x", pady=2)
        tk.Button(btn_frame, text="🔄 重新生成选中", command=self._regenerate_image,
                  bg="#cc5500", fg="white", font=("Microsoft YaHei", 9)).pack(fill="x", pady=2)

        self.btn_execute.config(text="▶ 批量生成全部图片（跳过已有）")

        # ★ 手动替换图片按钮
        btn_replace = tk.Button(f, text="📂 替换选中场景图片", bg="#555", fg="white",
                                font=("Microsoft YaHei", 10),
                                command=self._replace_selected_image)
        btn_replace.pack(pady=3)

        # === 右侧：上方图片预览 + 下方Prompt编辑 ===
        right_f = tk.Frame(pane, bg="#1a1a2e")
        pane.add(right_f)

        right_pane = tk.PanedWindow(right_f, orient="vertical", bg="#1a1a2e", sashwidth=5)
        right_pane.pack(fill="both", expand=True)

        # 上方：图片预览
        img_frame = tk.Frame(right_pane, bg="#0a0a1a")
        right_pane.add(img_frame, height=350, minsize=200)

        self.img_preview_label = tk.Label(img_frame, text="← 选择场景查看图片",
                                           bg="#0a0a1a", fg="#aaa",
                                           font=("Microsoft YaHei", 12))
        self.img_preview_label.pack(fill="both", expand=True)

        # 下方：Prompt编辑区
        prompt_f = tk.LabelFrame(right_pane, text="✏️ Prompt编辑（修改后点重新生成）",
                                  font=("Microsoft YaHei", 9),
                                  fg="white", bg="#16213e")
        right_pane.add(prompt_f, height=250, minsize=180)

        # ★ 显示当前选中的场景信息
        self.img_scene_info = tk.Label(prompt_f, text="未选中场景",
                                        font=("Microsoft YaHei", 10, "bold"),
                                        fg="#e94560", bg="#16213e")
        self.img_scene_info.pack(anchor="w", padx=5, pady=(5, 0))

        tk.Label(prompt_f, text="🇨🇳 中文描述:", fg="#e94560", bg="#16213e",
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=5)
        self.img_prompt_cn = scrolledtext.ScrolledText(prompt_f, wrap="word", bg="#0a0a1a",
                                                        fg="white", font=("Microsoft YaHei", 9),
                                                        height=2, insertbackground="white")
        self.img_prompt_cn.pack(fill="x", padx=5, pady=2)

        tk.Label(prompt_f, text="🇺🇸 英文Prompt（实际用于生图）:", fg="#aaa", bg="#16213e",
                 font=("Microsoft YaHei", 9)).pack(anchor="w", padx=5)
        self.img_prompt_en = scrolledtext.ScrolledText(prompt_f, wrap="word", bg="#0a0a1a",
                                                        fg="#88ccff", font=("Consolas", 9),
                                                        height=3, insertbackground="white")
        self.img_prompt_en.pack(fill="x", padx=5, pady=2)

        prompt_btn_row = tk.Frame(prompt_f, bg="#16213e")
        prompt_btn_row.pack(fill="x", padx=5, pady=5)
        tk.Button(prompt_btn_row, text="💾 保存Prompt", command=self._save_img_prompt,
                  bg="#2a6041", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=3)
        tk.Button(prompt_btn_row, text="🔄 中文→英文", command=self._translate_img_prompt,
                  bg="#0f3460", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=3)
        tk.Button(prompt_btn_row, text="🔄 英文→中文", command=self._translate_img_prompt_en_to_cn,
                  bg="#604060", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=3)

        if self.image_results and all(r.get("success") for r in self.image_results):
            self._enable_next()


    def _scan_existing_images(self):
        """扫描已存在的图片文件，填充 self.image_results"""
        import glob
        self.image_results = []
        if not self.storyboard:
            return
        ep_num = self.current_ep + 1
        scenes = self.storyboard.get("scenes", [])
        for i, scene in enumerate(scenes):
            sid = scene.get("scene_id", i + 1)
            pattern = os.path.join(IMAGES_DIR, f"ep{ep_num:03d}_scene{sid:03d}.png")
            found = glob.glob(pattern)
            if found:
                self.image_results.append({
                    "scene_id": sid,
                    "image_path": found[0],
                    "success": True
                })
            else:
                self.image_results.append({
                    "scene_id": sid,
                    "image_path": None,
                    "success": False
                })



        # 扫描帧序列文件 (链式帧生成的结果)
        self.frame_sequence = []
        ep_num = self.current_ep + 1
        frame_idx = 1
        while True:
            frame_pattern = os.path.join(IMAGES_DIR, f"ep{ep_num:03d}_frame{frame_idx:03d}.png")
            found_frames = glob.glob(frame_pattern)
            if found_frames:
                self.frame_sequence.append(found_frames[0])
                frame_idx += 1
            else:
                break
        if self.frame_sequence:
            print(f"扫描到 {len(self.frame_sequence)} 张帧序列文件")

    def _scan_existing_audio(self):
        """扫描已存在的音频文件，填充 self.audio_results"""
        self.audio_results = []
        if not self.storyboard:
            return
        ep_num = self.current_ep + 1
        scenes = self.storyboard.get("scenes", [])
        for i, scene in enumerate(scenes):
            sid = scene.get("scene_id", i + 1)
            audio_path = os.path.join(AUDIO_DIR, f"ep{ep_num:03d}_scene{sid:03d}.mp3")
            if os.path.exists(audio_path):
                self.audio_results.append(audio_path)
            else:
                self.audio_results.append(None)

    def _get_selected_scene_idx(self):
        """优先用缓存的选中索引，防止焦点丢失"""
        sel = self.img_listbox.curselection()
        if sel:
            self._selected_img_idx = sel[0]
            return sel[0]
        # 焦点丢失时用缓存
        if self._selected_img_idx is not None:
            return self._selected_img_idx
        return None

    def _on_img_select(self, event=None):
        sel = self.img_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._selected_img_idx = idx  # ★ 缓存选中索引

        # 更新场景信息标签
        if hasattr(self, 'img_scene_info'):
            self.img_scene_info.config(text=f"📌 当前编辑: 场景 {idx + 1}")

        if self.storyboard:
            scenes = self.storyboard.get("scenes", [])
            if idx < len(scenes):
                scene = scenes[idx]
                self.img_prompt_cn.delete("1.0", "end")
                self.img_prompt_cn.insert("1.0", scene.get("visual_description_cn", ""))
                self.img_prompt_en.delete("1.0", "end")
                self.img_prompt_en.insert("1.0", scene.get("visual_description_en",
                                                            scene.get("visual_description", "")))

        if idx < len(self.image_results):
            img_path = self.image_results[idx].get("image_path")
            if img_path and os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    img.thumbnail((450, 750))
                    photo = ImageTk.PhotoImage(img)
                    self.img_preview_label.config(image=photo, text="")
                    self.img_preview_label._photo = photo
                except Exception as e:
                    self.img_preview_label.config(text=f"图片加载失败: {e}", image="")
            else:
                self.img_preview_label.config(text="⬜ 图片尚未生成", image="")
        else:
            self.img_preview_label.config(text="⬜ 图片尚未生成", image="")

    def _save_img_prompt(self):
        idx = self._get_selected_scene_idx()
        if idx is None:
            messagebox.showinfo("提示", "请先在左侧列表点击选择一个场景")
            return
        if not self.storyboard:
            return
        scenes = self.storyboard.get("scenes", [])
        if idx >= len(scenes):
            return

        new_cn = self.img_prompt_cn.get("1.0", "end").strip()
        new_en = self.img_prompt_en.get("1.0", "end").strip()
        scenes[idx]["visual_description_cn"] = new_cn
        scenes[idx]["visual_description_en"] = new_en
        scenes[idx]["visual_description"] = new_en

        # ★ 同步保存到剧本文件
        ep_num = self.current_ep + 1
        script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
        try:
            with open(script_path, "w", encoding="utf-8") as ff:
                json.dump(self.storyboard, ff, ensure_ascii=False, indent=2)
        except:
            pass

        sid = scenes[idx].get("scene_id", idx + 1)
        self._log(f"✅ 场景{sid} Prompt已保存（中文+英文）")
        messagebox.showinfo("保存成功", f"场景{sid}的Prompt已保存！\n修改后点击「重新生成选中」即可更新图片。")




    def _translate_img_prompt_en_to_cn(self):
        """Step5: 英文Prompt→中文描述"""
        en_text = self.img_prompt_en.get("1.0", "end").strip()
        if not en_text:
            messagebox.showinfo("提示", "英文Prompt为空")
            return

        self._log("🔄 英文→中文翻译中...")

        def do_translate():
            system = "你是翻译专家。将以下英文图片描述翻译成简洁的中文，不超过30个字。只输出中文译文。"
            result = self.gemini._call_text(system, en_text, temperature=0.3)
            return result.strip() if result else ""

        def on_done(cn_text):
            if cn_text:
                self.img_prompt_cn.delete("1.0", "end")
                self.img_prompt_cn.insert("1.0", cn_text)
                self._log(f"✅ 翻译完成: {cn_text[:30]}")
            else:
                self._log("❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)


    def _translate_img_prompt(self):
        cn_text = self.img_prompt_cn.get("1.0", "end").strip()
        if not cn_text:
            messagebox.showinfo("提示", "请先填写中文描述")
            return

        def do_translate():
            return self.gemini.translate_cn_to_en(cn_text)

        def on_done(en_text):
            if en_text:
                self.img_prompt_en.delete("1.0", "end")
                self.img_prompt_en.insert("1.0", en_text)
                self._log("✅ Prompt翻译完成")
            else:
                self._log("❌ 翻译失败")

        self._run_in_thread(do_translate, on_done)

    def _generate_single_image(self):
        idx = self._get_selected_scene_idx()
        if idx is None:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        self._do_generate_image(idx)

    def _regenerate_image(self):
        idx = self._get_selected_scene_idx()
        if idx is None:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        self._do_generate_image(idx, force=True)

    def _do_generate_image(self, idx, force=False):
        if not self.storyboard:
            return
        scenes = self.storyboard.get("scenes", [])
        if idx >= len(scenes):
            return

        scene = scenes[idx]
        current_en = self.img_prompt_en.get("1.0", "end").strip()
        current_cn = self.img_prompt_cn.get("1.0", "end").strip()
        if current_en:
            scene["visual_description_en"] = current_en
            scene["visual_description"] = current_en
        if current_cn:
            scene["visual_description_cn"] = current_cn

        prompt = scene.get("visual_description_en", scene.get("visual_description", ""))
        if not prompt:
            messagebox.showinfo("提示", "请先填写英文Prompt")
            return

        # ★ P0安全保险：确保character_profiles和outfit_dna已加载
        if self.gemini:
            if self.characters and not self.gemini.character_profiles:
                self.gemini.set_character_profiles(self.characters)
            if self.char_manager and not getattr(self.gemini, '_outfit_dna_cache', None):
                _odna = self.char_manager.get_all_outfit_dna()
                if _odna and hasattr(self.gemini, 'set_outfit_dna_cache'):
                    self.gemini.set_outfit_dna_cache(_odna)
        
        # ★ 改进：自动注入角色外貌到prompt
        char_names = scene.get("characters", [])
        if self.gemini and char_names:
            prompt = self.gemini._enrich_prompt_with_characters(prompt, char_names)

        def do_gen():
            ep_num = self.current_ep + 1
            sid = scene.get("scene_id", idx + 1)
            save_path = os.path.join(IMAGES_DIR, f"ep{ep_num:03d}_scene{sid:03d}")
            if force:
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    old = save_path + ext
                    if os.path.exists(old):
                        os.remove(old)
            self.root.after(0, lambda: self._log(f"🎨 生成场景{sid}..."))
            # ★ 收集角色参考图
            ref_image_paths = []
            if self.char_manager and char_names:
                for _cn in char_names:
                    _ref = self.char_manager.get_reference_image(_cn)
                    if _ref:
                        ref_image_paths.append(_ref)
            if ref_image_paths:
                self.root.after(0, lambda: self._log(f"📎 附加 {len(ref_image_paths)} 张角色参考图"))
            # ★ 传递 style_prefix
            style_prefix = ""
            if self.gemini and hasattr(self.gemini, 'genre_style'):
                style_prefix = self.gemini.genre_style.get("visual_prefix", "")
            result = self.gemini.generate_image(prompt, save_path, style_prefix=style_prefix, reference_image_paths=ref_image_paths if ref_image_paths else None)
            return {"scene_id": sid, "image_path": result, "success": result is not None, "idx": idx}

        def on_done(result):
            while len(self.image_results) <= idx:
                self.image_results.append({"scene_id": idx + 1, "image_path": None, "success": False})
            self.image_results[idx] = result

            status = "✅" if result["success"] else "❌"
            scenes = self.storyboard.get("scenes", [])
            dlg = scenes[idx].get("dialogue", "")[:12] if idx < len(scenes) else ""
            cn = scenes[idx].get("visual_description_cn", "")[:15] if idx < len(scenes) else ""
            self.img_listbox.delete(idx)
            self.img_listbox.insert(idx, f"{status} 场景{result['scene_id']}: {dlg or cn}")
            self.img_listbox.selection_set(idx)

            self._on_img_select()
            self._log(f"{'✅' if result['success'] else '❌'} 场景{result['scene_id']} 生成完成")

            if all(r.get("success") for r in self.image_results):
                self._enable_next()

        self._run_in_thread(do_gen, on_done)

    # ══════════════════════════════════════
    #  Step 6: 语音合成
    # ══════════════════════════════════════

    def _build_step6_tts(self):
        f = self.work_area
        ep_num = self.current_ep + 1
        tk.Label(f, text=f"🔊 第六步：语音合成 — 第{ep_num}集",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 10))

        cols = ("id", "speaker", "voice", "dialogue", "status")
        self.tts_tree = ttk.Treeview(f, columns=cols, show="headings", height=15)
        self.tts_tree.heading("id", text="#")
        self.tts_tree.heading("speaker", text="说话人")
        self.tts_tree.heading("voice", text="音色")
        self.tts_tree.heading("dialogue", text="台词")
        self.tts_tree.heading("status", text="状态")
        self.tts_tree.column("id", width=35)
        self.tts_tree.column("speaker", width=70)
        self.tts_tree.column("voice", width=60)
        self.tts_tree.column("dialogue", width=400)
        self.tts_tree.column("status", width=60)
        self.tts_tree.pack(fill="both", expand=True, pady=5)

        # ★ 自动加载已有剧本（断点续传）
        if not self.storyboard:
            ep_num2 = self.current_ep + 1
            script_path2 = os.path.join(SCRIPTS_DIR, f"ep{ep_num2:03d}_script.json")
            if os.path.exists(script_path2):
                try:
                    with open(script_path2, "r", encoding="utf-8") as ff:
                        self.storyboard = json.load(ff)
                    self._log(f"📂 自动加载第{ep_num2}集剧本")
                except:
                    pass

        # ★ 修复：扫描已有音频
        if self.storyboard:
            self._scan_existing_audio()

        if self.storyboard:
            for i, s in enumerate(self.storyboard.get("scenes", [])):
                sid = s.get("scene_id", 0)
                speaker = s.get("speaker", "")
                voice = ""
                if self.char_manager and speaker:
                    voice = self.char_manager.get_voice(speaker)
                dialogue = s.get("dialogue", "") or "(动作场景-静音)"
                # 显示已有状态
                has_audio = (i < len(self.audio_results) and self.audio_results[i] is not None)
                status = "✅" if has_audio else "⬜"
                self.tts_tree.insert("", "end", values=(sid, speaker, voice, dialogue[:50], status))

        btn_row = tk.Frame(f, bg="#1a1a2e")
        btn_row.pack(fill="x", pady=5)
        tk.Button(btn_row, text="🔊 试听选中", command=self._play_audio,
                  bg="#0f3460", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

        # ★ 单条生成按钮
        btn_single_tts = tk.Button(f, text="🔊 合成选中语音",
                                    command=self._synthesize_single_audio,
                                    bg="#2a6041", fg="white",
                                    font=("Microsoft YaHei", 10))
        btn_single_tts.pack(pady=5)
        
        self.btn_execute.config(text="▶ 批量合成语音（跳过已有）")

        # ★ 音色切换
        voice_frame = tk.Frame(f, bg="#1a1a2e")
        voice_frame.pack(anchor="w", pady=3)
        tk.Label(voice_frame, text="🎤 切换选中场景音色:", bg="#1a1a2e", fg="#aaa",
                 font=("Microsoft YaHei", 10)).pack(side="left")
        try:
            from tts_engine import VOICE_MAP
            voice_names = list(VOICE_MAP.keys())
        except:
            voice_names = ["少年", "少女", "御姐", "萝莉", "大叔"]
        self.voice_combo = ttk.Combobox(voice_frame, values=voice_names, width=12, state="readonly")
        self.voice_combo.pack(side="left", padx=5)
        if voice_names:
            self.voice_combo.set(voice_names[0])
        btn_voice = tk.Button(voice_frame, text="应用", bg="#444", fg="white",
                              font=("Microsoft YaHei", 9),
                              command=self._apply_voice_change)
        btn_voice.pack(side="left", padx=3)
        if self.audio_results and all(r is not None for r in self.audio_results):
            self._enable_next()

    def _play_audio(self):
        sel = self.tts_tree.selection()
        if not sel:
            return
        vals = self.tts_tree.item(sel[0], "values")
        sid = int(vals[0])
        ep_num = self.current_ep + 1
        audio_path = os.path.join(AUDIO_DIR, f"ep{ep_num:03d}_scene{sid:03d}.mp3")
        if os.path.exists(audio_path):
            os.startfile(audio_path)
        else:
            messagebox.showinfo("提示", "音频尚未生成")

    # ══════════════════════════════════════
    def _replace_selected_image(self):
        """替换选中场景的图片：优先从候选图中选择，没有候选图则重新生成"""
        idx = self._get_selected_scene_idx()
        if idx is None:
            messagebox.showinfo("提示", "请先在左侧列表选择一个场景")
            return
        
        # 获取场景信息
        import glob
        scenes = self.storyboard.get("scenes", [])
        if idx >= len(scenes):
            self._regenerate_image()
            return
        
        scene = scenes[idx]
        sid = scene.get("scene_id", idx + 1)
        ep_num = self.current_ep + 1
        
        # 查找候选图
        pattern = os.path.join(IMAGES_DIR, f"ep{ep_num:03d}_scene{sid:03d}_candidate_*.png")
        candidates = sorted(glob.glob(pattern))
        
        if len(candidates) >= 2:
            # 有候选图，弹出选择对话框
            dialog = ImageSelectorDialog(self.root, candidates, sid)
            chosen = dialog.result
            
            if chosen and chosen in candidates:
                # 复制选中的图片为正式图片
                import shutil
                final_path = os.path.join(IMAGES_DIR, f"ep{ep_num:03d}_scene{sid:03d}.png")
                shutil.copy2(chosen, final_path)
                
                # 更新storyboard中的路径
                scene["image_path"] = final_path
                self._save_storyboard()
                
                # 刷新显示
                self._on_scene_select()
                self._log(f"✅ 场景 {sid} 已选择：{os.path.basename(chosen)}")
            else:
                self._log(f"⏭️ 场景 {sid} 跳过选择")
        else:
            # 没有候选图，重新生成
            self._regenerate_image()

    def _apply_voice_change(self):
        """将选中的音色应用到tts_tree选中行"""
        sel = self.tts_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一个场景")
            return
        new_voice = self.voice_combo.get()
        if not new_voice:
            messagebox.showinfo("提示", "请选择一个音色")
            return
        vals = list(self.tts_tree.item(sel[0], "values"))
        vals[2] = new_voice
        self.tts_tree.item(sel[0], values=vals)
        sid = int(vals[0])
        if self.storyboard:
            scenes = self.storyboard.get("scenes", [])
            for s in scenes:
                if s.get("scene_id", 0) == sid:
                    s["voice_override"] = new_voice
                    break
        idx = None
        for i, item in enumerate(self.tts_tree.get_children()):
            if item == sel[0]:
                idx = i
                break
        if idx is not None and idx < len(self.audio_results):
            self.audio_results[idx] = None
            vals[4] = "□"
            self.tts_tree.item(sel[0], values=vals)
        self._log(f"🎤 场景 {sid} 音色已切换为: {new_voice}")

    #  Step 7: 视频生成
    # ══════════════════════════════════════

# ============================================================
# Step7 视频界面改造 - 完整替换代码
# 将以下所有方法替换到 gui.py 中对应位置
# ============================================================

    def _scan_existing_videos(self):
        """扫描已存在的视频"""
        self.video_results = []
        if not self.storyboard:
            return
        ep_num = self.current_ep + 1
        scenes = self.storyboard.get("scenes", [])
        for i, scene in enumerate(scenes):
            sid = scene.get("scene_id", i + 1)
            video_path = os.path.join(VIDEOS_DIR, f"ep{ep_num:03d}_scene{sid:03d}.mp4")
            if os.path.exists(video_path) and os.path.getsize(video_path) > 1000:
                self.video_results.append(video_path)
            else:
                self.video_results.append(None)

    def _refresh_vid_tree(self):
        """刷新视频Treeview表格数据（不重建UI）"""
        if not hasattr(self, 'vid_tree') or not self.vid_tree.winfo_exists():
            return
        # 清空现有行
        for item in self.vid_tree.get_children():
            self.vid_tree.delete(item)

        scenes = self.storyboard.get("scenes", []) if self.storyboard else []
        for i, s in enumerate(scenes):
            sid = s.get("scene_id", i + 1)
            # 首帧
            fi = "\u274C 无"
            if i < len(self.frame_sequence) and self.frame_sequence[i]:
                fi = "\u2705 " + os.path.basename(self.frame_sequence[i])
            elif i < len(self.image_results) and self.image_results[i].get("success"):
                fi = "\U0001f5bc " + os.path.basename(self.image_results[i]["image_path"])
            # 尾帧
            li = "-- 末尾"
            if i + 1 < len(self.frame_sequence) and self.frame_sequence[i + 1]:
                li = "\u2705 " + os.path.basename(self.frame_sequence[i + 1])
            elif i + 1 < len(self.image_results) and self.image_results[i + 1].get("success"):
                li = "\U0001f5bc " + os.path.basename(self.image_results[i + 1]["image_path"])
            # 视频状态
            vs = "\u25a1 未生成"
            if i < len(self.video_results) and self.video_results[i]:
                vs = "\u2705 已生成"
            # prompt状态
            has_prompt = "✅" if s.get("video_prompt", "") else "—"
            self.vid_tree.insert("", "end", values=(sid, fi, li, vs, has_prompt))

    def _build_step7_video(self):
        f = self.work_area
        ep_num = self.current_ep + 1

        # ===== 标题区 =====
        title_frame = tk.Frame(f, bg="#1a1a2e")
        title_frame.pack(fill="x", pady=(0, 5))
        tk.Label(title_frame, text=f"🎞 第七步：图片转视频 — 第{ep_num}集",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(side="left")

        # ===== 模型选择 + 说明 =====
        top_bar = tk.Frame(f, bg="#1a1a2e")
        top_bar.pack(fill="x", padx=5, pady=(0, 5))

        tk.Label(top_bar, text="🎬 视频模型:", fg="#aaa", bg="#1a1a2e",
                 font=("Microsoft YaHei", 9)).pack(side="left")
        self._vid_model_var = tk.StringVar()
        _vid_registry = get_registry()
        _vid_engines = _vid_registry.list_video_engines()
        _vid_active = _vid_registry.get_active_names().get("video", "")
        self._vid_model_var.set(_vid_active)
        self._vid_model_combo = ttk.Combobox(top_bar, textvariable=self._vid_model_var,
                                              values=_vid_engines, state="readonly", width=20)
        self._vid_model_combo.pack(side="left", padx=(5, 10))
        self._vid_model_combo.bind("<<ComboboxSelected>>", self._on_video_model_change)

        tk.Label(top_bar, text="相邻场景图片作为首尾帧，生成过渡视频",
                 font=("Microsoft YaHei", 9), fg="#666", bg="#1a1a2e").pack(side="left")

        # ===== 加载 storyboard =====
        if not self.storyboard:
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            if os.path.exists(script_path):
                try:
                    with open(script_path, "r", encoding="utf-8") as ff:
                        self.storyboard = json.load(ff)
                except:
                    pass

        if not self.storyboard:
            tk.Label(f, text="⚠ 请先完成前面步骤（生成分镜剧本）",
                     fg="#ff6600", bg="#1a1a2e",
                     font=("Microsoft YaHei", 12)).pack(pady=20)
            return

        self._scan_existing_images()
        self._scan_existing_videos()

        # ===== 主内容区：左右布局 =====
        main_pane = tk.Frame(f, bg="#1a1a2e")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        # --- 左侧：表格 + 按钮 ---
        left_frame = tk.Frame(main_pane, bg="#1a1a2e")
        left_frame.pack(side="left", fill="both", expand=True)

        # Treeview（新增 prompt 列）
        cols = ("id", "first_frame", "last_frame", "video_status", "prompt_status")
        self.vid_tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=10)
        self.vid_tree.heading("id", text="#")
        self.vid_tree.heading("first_frame", text="首帧")
        self.vid_tree.heading("last_frame", text="尾帧")
        self.vid_tree.heading("video_status", text="视频")
        self.vid_tree.heading("prompt_status", text="Prompt")
        self.vid_tree.column("id", width=35, anchor="center")
        self.vid_tree.column("first_frame", width=220)
        self.vid_tree.column("last_frame", width=220)
        self.vid_tree.column("video_status", width=75, anchor="center")
        self.vid_tree.column("prompt_status", width=55, anchor="center")

        # 滚动条
        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.vid_tree.yview)
        self.vid_tree.configure(yscrollcommand=tree_scroll.set)
        self.vid_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.vid_tree.bind("<<TreeviewSelect>>", self._on_vid_select)

        # 填充表格数据
        self._refresh_vid_tree()

        # --- 右侧：预览 + 操作 ---
        right_frame = tk.Frame(main_pane, bg="#1a1a2e", width=320)
        right_frame.pack(side="right", fill="y", padx=(10, 0))
        right_frame.pack_propagate(False)

        # 首帧预览
        ff_frame = tk.LabelFrame(right_frame, text="首帧预览", fg="white", bg="#16213e",
                                font=("Microsoft YaHei", 9))
        ff_frame.pack(fill="x", padx=3, pady=(0, 3))
        self.vid_first_frame_label = tk.Label(ff_frame, bg="#0a0a1a", width=300, height=170)
        self.vid_first_frame_label.pack(padx=2, pady=2)
        self.vid_first_frame_label.config(text="← 选择场景", fg="#aaa")

        # 尾帧预览
        lf_frame = tk.LabelFrame(right_frame, text="尾帧预览", fg="white", bg="#16213e",
                                font=("Microsoft YaHei", 9))
        lf_frame.pack(fill="x", padx=3, pady=(0, 3))
        self.vid_last_frame_label = tk.Label(lf_frame, bg="#0a0a1a", width=300, height=170)
        self.vid_last_frame_label.pack(padx=2, pady=2)
        self.vid_last_frame_label.config(text="← 选择场景", fg="#aaa")

        # 操作按钮组
        tk.Button(right_frame, text="🎬 生成选中视频",
                  command=self._generate_single_video,
                  bg="#2a6041", fg="white",
                  font=("Microsoft YaHei", 10), width=18).pack(pady=(5, 3))
        tk.Button(right_frame, text="▶ 播放选中视频",
                  command=self._play_selected_video,
                  bg="#1a5276", fg="white",
                  font=("Microsoft YaHei", 9), width=18).pack(pady=3)
        tk.Button(right_frame, text="📂 打开视频目录",
                  command=lambda: os.startfile(VIDEOS_DIR) if os.path.exists(VIDEOS_DIR) else None,
                  bg="#555", fg="white",
                  font=("Microsoft YaHei", 9), width=18).pack(pady=3)
        tk.Button(right_frame, text="🔄 刷新状态",
                  command=self._refresh_step7_status,
                  bg="#555", fg="white",
                  font=("Microsoft YaHei", 9), width=18).pack(pady=3)

        # ===== 底部：提示词编辑区 =====
        prompt_frame = tk.LabelFrame(f, text="📝 视频提示词（Prompt）— 选中场景后编辑",
                                     fg="white", bg="#16213e",
                                     font=("Microsoft YaHei", 10))
        prompt_frame.pack(fill="x", pady=(5, 3), padx=5)

        prompt_btn_frame = tk.Frame(prompt_frame, bg="#16213e")
        prompt_btn_frame.pack(fill="x", padx=5, pady=(5, 0))

        tk.Button(prompt_btn_frame, text="🤖 AI生成当前Prompt",
                  command=self._generate_current_video_prompt,
                  bg="#2a6041", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 5))
        tk.Button(prompt_btn_frame, text="🤖 AI批量生成全部Prompt",
                  command=self._generate_all_video_prompts,
                  bg="#2a6041", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 5))
        tk.Button(prompt_btn_frame, text="💾 保存当前Prompt",
                  command=self._save_current_video_prompt,
                  bg="#1a5276", fg="white", font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 5))

        # 记录当前编辑的场景索引
        self._current_vid_prompt_idx = -1

        self.video_prompt_text = tk.Text(prompt_frame, height=3, bg="#0a0a1a", fg="#00ff88",
                                         insertbackground="white", font=("Consolas", 10),
                                         wrap="word")
        self.video_prompt_text.pack(fill="x", padx=5, pady=5)
        self.video_prompt_text.insert("1.0", "← 选择一个场景查看/编辑提示词")

        # ===== 底部执行按钮 =====
        self.btn_execute.config(text="▶ 批量生成全部视频（首尾帧模式）")

        if self.video_results and all(v is not None for v in self.video_results):
            self._enable_next()

    def _refresh_step7_status(self):
        """刷新Step7状态：重新扫描文件 + 刷新表格"""
        self._scan_existing_images()
        self._scan_existing_videos()
        self._refresh_vid_tree()
        success = sum(1 for v in self.video_results if v is not None)
        total = len(self.video_results)
        self._log(f"🔄 刷新完成: {success}/{total} 个视频已生成")
        if success > 0 and success == total:
            self._enable_next()


    def _on_image_model_change(self, event=None):
        """切换图片引擎"""
        name = self._img_model_var.get()
        if name:
            registry = get_registry()
            try:
                registry.set_active_image(name)
                self._log(f"✅ 图片引擎已切换：{name}")
            except Exception as e:
                self._log(f"❌ 切换失败：{e}")
    def _on_video_model_change(self, event=None):
        """切换视频引擎"""
        name = self._vid_model_var.get()
        if name:
            registry = get_registry()
            try:
                registry.set_active_video(name)
                self._log(f"✅ 视频引擎已切换: {name}")
            except Exception as e:
                self._log(f"❌ 切换失败: {e}")

    def _on_vid_select(self, event=None):
        """选中视频场景时：自动保存上一个 → 显示新场景预览 + 提示词"""
        sel = self.vid_tree.selection()
        if not sel:
            return
        try:
            vals = self.vid_tree.item(sel[0], "values")
            idx = int(vals[0]) - 1
            scenes = self.storyboard.get("scenes", []) if self.storyboard else []

            # ★ 自动保存上一个场景的prompt（如果有修改）
            if (self._current_vid_prompt_idx >= 0
                    and self._current_vid_prompt_idx != idx
                    and self._current_vid_prompt_idx < len(scenes)):
                old_prompt = self.video_prompt_text.get("1.0", "end").strip()
                placeholder_texts = ("← 选择", "（无提示词")
                if old_prompt and not any(old_prompt.startswith(p) for p in placeholder_texts):
                    scenes[self._current_vid_prompt_idx]["video_prompt"] = old_prompt

            self._current_vid_prompt_idx = idx

            from PIL import Image, ImageTk

            # === 首帧预览 ===
            first_path = None
            if idx < len(self.frame_sequence) and self.frame_sequence[idx]:
                first_path = self.frame_sequence[idx]
            elif idx < len(self.image_results) and self.image_results[idx].get("success"):
                first_path = self.image_results[idx]["image_path"]

            if first_path and os.path.exists(first_path):
                try:
                    img = Image.open(first_path)
                    img.thumbnail((296, 166), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.vid_first_frame_label.config(image=photo, text="")
                    self.vid_first_frame_label._photo = photo
                except:
                    self.vid_first_frame_label.config(text="加载失败", image="")
            else:
                self.vid_first_frame_label.config(text="❌ 无图片", image="")

            # === 尾帧预览（安全边界检查）===
            last_path = None
            next_idx = idx + 1
            if next_idx < len(self.frame_sequence) and self.frame_sequence[next_idx]:
                last_path = self.frame_sequence[next_idx]
            elif next_idx < len(self.image_results) and self.image_results[next_idx].get("success"):
                last_path = self.image_results[next_idx]["image_path"]

            if last_path and os.path.exists(last_path):
                try:
                    img = Image.open(last_path)
                    img.thumbnail((296, 166), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.vid_last_frame_label.config(image=photo, text="")
                    self.vid_last_frame_label._photo = photo
                except:
                    self.vid_last_frame_label.config(text="加载失败", image="")
            else:
                self.vid_last_frame_label.config(text="末尾场景(单图模式)", image="")

            # === 显示提示词 ===
            if idx < len(scenes):
                scene = scenes[idx]
                vp = scene.get("video_prompt", "")
            if not vp:
                desc_cn = str(scene.get('visual_description_cn', '') or '')
                desc_en = str(scene.get('visual_description_en', '') or '')
                start_frame_en = str(scene.get('start_frame_description_en', '') or '')
                cam = str(scene.get('camera_movement', '') or '')
                cam_map = {"固定镜头": "static camera", "缓慢推进": "camera slowly pushes in", "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in", "向左平移": "camera pans left", "向右平移": "camera pans right", "跟随镜头": "tracking shot", "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot", "手持镜头": "handheld camera", "特写推进": "extreme close-up push in", "升降镜头": "crane shot"}
                cam_en = cam_map.get(cam, cam if any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement") if cam else "smooth camera movement"
                desc = start_frame_en or desc_en or desc_cn
                if desc and desc != 'NONE':
                    vp = f"Cinematic shot, {desc[:200]}, {cam_en}, 8K quality"
                else:
                    vp = f"Cinematic shot, cinematic scene, {cam_en}, 8K quality"
            self.video_prompt_text.delete("1.0", "end")
            self.video_prompt_text.insert("1.0", vp if vp else " (无提示词，请点AI生成或手动输入) ")

        except Exception as e:
            print(f"vid_select error: {e}")
            import traceback
            traceback.print_exc()

    def _save_current_video_prompt(self):
        """保存当前编辑的提示词到storyboard并写入文件"""
        sel = self.vid_tree.selection()
        if not sel:
            self._log("⚠ 请先选择一个场景")
            return
        vals = self.vid_tree.item(sel[0], "values")
        idx = int(vals[0]) - 1
        scenes = self.storyboard.get("scenes", [])
        if idx < len(scenes):
            prompt = self.video_prompt_text.get("1.0", "end").strip()
            # 不保存占位文本
            if prompt.startswith("← 选择") or prompt.startswith("（无提示词"):
                self._log("⚠ 没有有效的提示词内容")
                return
            scenes[idx]["video_prompt"] = prompt
            ep_num = self.current_ep + 1
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            try:
                with open(script_path, "w", encoding="utf-8") as ff:
                    json.dump(self.storyboard, ff, ensure_ascii=False, indent=2)
                self._log(f"✅ 场景 {idx+1} 提示词已保存")
                # 刷新表格中的prompt状态列
                self._refresh_vid_tree()
                # 重新选中当前行
                for item in self.vid_tree.get_children():
                    if self.vid_tree.item(item, "values")[0] == str(idx + 1):
                        self.vid_tree.selection_set(item)
                        break
            except Exception as e:
                self._log(f"❌ 保存失败: {e}")

    def _generate_current_video_prompt(self):
        """AI生成当前选中场景的视频提示词"""
        sel = self.vid_tree.selection()
        if not sel:
            self._log("⚠ 请先选择一个场景")
            return
        vals = self.vid_tree.item(sel[0], "values")
        idx = int(vals[0]) - 1
        scenes = self.storyboard.get("scenes", [])
        if idx >= len(scenes):
            return
        scene = scenes[idx]
        self._log(f"🤖 正在为场景 {idx+1} 生成视频提示词...")

        def do_gen():
            try:
                prompt = get_text_engine().generate_single_video_prompt(scene)
                return {"idx": idx, "prompt": prompt}
            except Exception as e:
                desc_en = str(scene.get('visual_description_en', '') or scene.get('visual_description', ''))
                desc_cn = str(scene.get('visual_description_cn', '') or '')
                desc = desc_en if desc_en else desc_cn
                cam = str(scene.get("camera_movement", "") or "")
                cam_map = {"固定镜头": "static camera", "缓慢推进": "camera slowly pushes in", "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in", "向左平移": "camera pans left", "向右平移": "camera pans right", "跟随镜头": "tracking shot", "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot", "手持镜头": "handheld camera", "特写推进": "extreme close-up push in", "升降镜头": "crane shot"}
                cam_en = cam_map.get(cam, cam if cam and any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement")
                fallback = f"Cinematic shot, {desc[:200]}, {cam_en}, cinematic lighting, 8K photorealistic, film grain"
                return {"idx": idx, "prompt": fallback}

        def on_done(data):
            if data and data.get("prompt"):
                i = data["idx"]
                prompt = data["prompt"]
                scenes[i]["video_prompt"] = prompt
                # 如果当前还是选中这个场景，更新编辑框
                if self._current_vid_prompt_idx == i:
                    self.video_prompt_text.delete("1.0", "end")
                    self.video_prompt_text.insert("1.0", prompt)
                self._log(f"✅ 场景 {i+1} 提示词生成完成")
                # 自动保存到文件
                self._auto_save_storyboard()
                self._refresh_vid_tree()

        self._run_in_thread(do_gen, on_done)

    def _generate_all_video_prompts(self):
        """AI批量生成所有场景的视频提示词"""
        self._log("🤖 正在批量生成所有场景视频提示词...")

        def do_gen():
            try:
                scene_prompts = get_text_engine().generate_video_prompts(self.storyboard)
                return scene_prompts
            except Exception as e:
                self.root.after(0, lambda: self._log(f"⚠ AI批量生成失败: {e}, 使用fallback"))
                scenes = self.storyboard.get("scenes", [])
                prompts = []
                for s in scenes:
                    desc = s.get("visual_description_en", "") or s.get("visual_description", "")
                    cam = s.get("camera_movement", "")
                    cam_map = {"固定镜头": "static camera", "缓慢推进": "camera slowly pushes in", "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in", "向左平移": "camera pans left", "向右平移": "camera pans right", "跟随镜头": "tracking shot", "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot", "手持镜头": "handheld camera", "特写推进": "extreme close-up push in", "升降镜头": "crane shot"}
                    cam_en = cam_map.get(cam, cam if cam and any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement")
                    vp = f"Cinematic shot, {desc[:200]}, {cam_en}, cinematic lighting, 8K photorealistic, film grain, shallow depth of field"
                return prompts

        def on_done(prompts):
            if prompts:
                scenes = self.storyboard.get("scenes", [])
                for i, s in enumerate(scenes):
                    if i < len(prompts) and prompts[i]:
                        s["video_prompt"] = prompts[i]
                self._auto_save_storyboard()
                self._log(f"✅ 已生成 {len(prompts)} 个场景提示词并保存")
                self._refresh_vid_tree()
                # 刷新当前选中场景的编辑框
                sel = self.vid_tree.selection()
                if sel:
                    self._on_vid_select()

        self._run_in_thread(do_gen, on_done)

    def _auto_save_storyboard(self):
        """自动保存storyboard到文件（内部工具方法）"""
        if not self.storyboard:
            return
        ep_num = self.current_ep + 1
        script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
        try:
            with open(script_path, "w", encoding="utf-8") as ff:
                json.dump(self.storyboard, ff, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"auto_save_storyboard error: {e}")

    def _play_selected_video(self):
        """播放选中场景的视频"""
        sel = self.vid_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        vals = self.vid_tree.item(sel[0], "values")
        idx = int(vals[0]) - 1
        if idx < len(self.video_results) and self.video_results[idx]:
            vid_path = self.video_results[idx]
            if os.path.exists(vid_path):
                os.startfile(vid_path)
            else:
                messagebox.showinfo("提示", f"视频文件不存在: {vid_path}")
        else:
            messagebox.showinfo("提示", "该场景视频尚未生成")

    def _generate_single_video(self):
        """生成选中场景的视频 - 使用首尾帧模式（唯一版本）"""
        sel = self.vid_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        item = sel[0]
        vals = self.vid_tree.item(item, "values")
        idx = int(vals[0]) - 1
        scenes = self.storyboard.get("scenes", [])

        if idx >= len(scenes):
            self._log(f"❌ 场景索引越界: {idx}")
            return

        self._log(f"🎬 开始生成场景 {vals[0]} 的视频...")

        def do_gen():
            scene = scenes[idx]

            # --- 获取首帧 ---
            first_frame = None
            if idx < len(self.frame_sequence) and self.frame_sequence[idx]:
                first_frame = self.frame_sequence[idx]
            elif idx < len(self.image_results) and self.image_results[idx].get("success"):
                first_frame = self.image_results[idx]["image_path"]

            if not first_frame or not os.path.exists(first_frame):
                self.root.after(0, lambda: self._log(f"❌ 场景 {vals[0]} 无首帧图片，请先生成图片"))
                return None

            # --- 获取尾帧（安全边界）---
            last_frame = None
            next_idx = idx + 1
            if next_idx < len(self.frame_sequence) and self.frame_sequence[next_idx]:
                last_frame = self.frame_sequence[next_idx]
            elif next_idx < len(self.image_results) and self.image_results[next_idx].get("success"):
                last_frame = self.image_results[next_idx]["image_path"]
            if last_frame and not os.path.exists(last_frame):
                last_frame = None

            # --- 获取prompt（优先编辑框 → storyboard → fallback）---
            video_prompt = ""
            # 如果当前选中的就是这个场景，从编辑框取
            if self._current_vid_prompt_idx == idx:
                video_prompt = self.video_prompt_text.get("1.0", "end").strip()
            # 过滤占位文本
            if not video_prompt or video_prompt.startswith("（无提示词") or video_prompt.startswith("← 选择"):
                video_prompt = scene.get("video_prompt", "")
            # fallback - 利用分镜的 camera_movement 和英文描述
            if not video_prompt:
                desc_cn = str(scene.get('visual_description_cn', '') or '')
                desc_en = str(scene.get('visual_description_en', '') or '')
                start_frame_en = str(scene.get('start_frame_description_en', '') or '')
                cam = str(scene.get('camera_movement', '') or '')
                # 运镜中文→英文简易映射
                cam_map = {
                    "固定镜头": "static camera", "缓慢推进": "camera slowly pushes in",
                    "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in",
                    "镜头拉远": "camera zooms out", "向左平移": "camera pans left",
                    "向右平移": "camera pans right", "向上平移": "camera tilts up",
                    "向下平移": "camera tilts down", "跟随镜头": "tracking shot",
                    "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot",
                    "手持镜头": "handheld camera", "特写推进": "extreme close-up push in",
                    "升降镜头": "crane shot", "旋转镜头": "spinning shot",
                }
                cam_en = cam_map.get(cam, cam if any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement")
                # 优先用英文描述/start_frame
                desc = start_frame_en or desc_en or desc_cn or "cinematic scene"
                if desc and desc != 'NONE':
                    video_prompt = f'Cinematic shot, {desc[:200]}, {cam_en}, 8K quality'
                else:
                    video_prompt = f'Cinematic shot, cinematic scene, {cam_en}, 8K quality'

            # --- 调用视频引擎 ---
            jimeng = get_video_engine()
            ep_num = self.current_ep + 1
            scene_id = scene.get('scene_id', idx + 1)
            save_path = os.path.join(VIDEOS_DIR, f'ep{ep_num:03d}_scene{scene_id:03d}.mp4')

            self.root.after(0, lambda: self._log(f'[DEBUG] prompt: {video_prompt[:80]}...'))

            if last_frame and os.path.exists(last_frame):
                self.root.after(0, lambda: self._log(
                    f"🎬 首尾帧模式: {os.path.basename(first_frame)} → {os.path.basename(last_frame)}"))
                result = jimeng.first_last_frame_to_video(first_frame, last_frame, save_path, prompt=video_prompt)
            else:
                self.root.after(0, lambda: self._log(
                    f"🎬 单图模式: {os.path.basename(first_frame)}"))
                result = jimeng.image_to_video(first_frame, save_path, prompt=video_prompt)

            return {"idx": idx, "result": result}

        def on_done(data):
            if data and data.get("result"):
                result = data["result"]
                vid_idx = data["idx"]
                # 安全扩展 video_results 列表
                while len(self.video_results) <= vid_idx:
                    self.video_results.append(None)
                self.video_results[vid_idx] = result
                self._scan_existing_videos()
                self._refresh_vid_tree()
                self._log(f"✅ 场景 {vals[0]} 视频生成完成")
                # 检查是否全部完成
                if all(v is not None for v in self.video_results):
                    self._enable_next()
            else:
                self._log(f"❌ 场景 {vals[0]} 视频生成失败")

        self._run_in_thread(do_gen, on_done)

    def _exec_step7(self):
        """批量生成全部视频 - 首尾帧模式"""
        if not self.storyboard:
            messagebox.showerror("错误", "请先完成前面步骤")
            return
        self._scan_existing_images()
        scenes = self.storyboard.get("scenes", [])
        ep_num = self.current_ep + 1

        def do_videos():
            video_api = get_video_engine()

            # ★ 构建首尾帧pairs
            self.root.after(0, lambda: self._log("📐 构建首尾帧视频对..."))
            pairs = []
            for i in range(len(scenes)):
                fp = None
                lp = None
                if i < len(self.frame_sequence) and self.frame_sequence[i]:
                    fp = self.frame_sequence[i]
                elif i < len(self.image_results) and self.image_results[i] and self.image_results[i].get("success"):
                    fp = self.image_results[i]["image_path"]
                next_i = i + 1
                if next_i < len(self.frame_sequence) and self.frame_sequence[next_i]:
                    lp = self.frame_sequence[next_i]
                elif next_i < len(self.image_results) and self.image_results[next_i] and self.image_results[next_i].get("success"):
                    lp = self.image_results[next_i]["image_path"]
                pairs.append((fp, lp))

            self.root.after(0, lambda: self._log(f"📐 构建了 {len(pairs)} 个视频对"))

            # ★ 获取场景提示词
            scene_prompts = []
            has_prompts = any(s.get("video_prompt", "") for s in scenes)

            if has_prompts:
                self.root.after(0, lambda: self._log("📝 使用已保存的视频提示词"))
                for s in scenes:
                    vp = s.get("video_prompt", "")
                    if not vp:
                        desc = s.get("start_frame_description_en", "") or s.get("visual_description_en", "") or s.get("visual_description", "")
                        cam = s.get("camera_movement", "")
                        cam_map = {"固定镜头": "static camera", "缓慢推进": "camera slowly pushes in", "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in", "向左平移": "camera pans left", "向右平移": "camera pans right", "跟随镜头": "tracking shot", "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot", "手持镜头": "handheld camera", "特写推进": "extreme close-up push in", "升降镜头": "crane shot"}
                        cam_en = cam_map.get(cam, cam if cam and any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement")
                        vp = f"Cinematic shot, {desc[:200]}, {cam_en}, professional lighting, 8K quality, shallow depth of field"
                    scene_prompts.append(vp)
            else:
                self.root.after(0, lambda: self._log("🤖 正在用 AI 生成视频prompt..."))
                try:
                    scene_prompts = get_text_engine().generate_video_prompts(self.storyboard)
                    self.root.after(0, lambda: self._log(f"✅ 视频prompt生成完成: {len(scene_prompts)} 个"))
                    for i, s in enumerate(scenes):
                        if i < len(scene_prompts) and scene_prompts[i]:
                            s["video_prompt"] = scene_prompts[i]
                    self._auto_save_storyboard()
                except Exception as e:
                    self.root.after(0, lambda: self._log(f"⚠ prompt生成失败: {e}, 使用fallback"))
                    scene_prompts = []
                    for s in scenes:
                        desc = s.get("visual_description_en", "") or s.get("visual_description", "")
                        cam = s.get("camera_movement", "")
                        cam_map = {"固定镜头": "static camera", "缓慢推进": "camera slowly pushes in", "缓慢拉远": "camera slowly pulls back", "镜头拉近": "camera zooms in", "向左平移": "camera pans left", "向右平移": "camera pans right", "跟随镜头": "tracking shot", "环绕镜头": "orbital shot", "航拍镜头": "aerial drone shot", "手持镜头": "handheld camera", "特写推进": "extreme close-up push in", "升降镜头": "crane shot"}
                        cam_en = cam_map.get(cam, cam if cam and any(c.isascii() and c.isalpha() for c in cam) else "smooth camera movement")
                        vp = f"Cinematic shot, {desc[:200]}, {cam_en}, cinematic lighting, 8K photorealistic, film grain, shallow depth of field"
                        scene_prompts.append(vp)

            self.root.after(0, lambda: self._log(f"🎬 开始生成 {len(pairs)} 个视频..."))
            results = video_api.batch_generate_videos_with_frames(pairs, ep_num, scene_prompts=scene_prompts)
            return results

        def on_done(results):
            self.video_results = results
            success = sum(1 for r in results if r is not None)
            self._log(f"✅ 视频完成: {success}/{len(results)}")
            # 刷新界面
            self._show_step(6)
            if success > 0:
                try:
                    if hasattr(self, 'state_manager') and self.state_manager:
                        self.state_manager.save()
                except:
                    pass
                self._enable_next()

        self._run_in_thread(do_videos, on_done)

    def _synthesize_single_audio(self):
        """合成选中场景的语音"""
        sel = self.tts_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        item = sel[0]
        vals = self.tts_tree.item(item, "values")
        sid = int(vals[0]) - 1

        self._log(f"🔊 开始合成场景 {vals[0]} 的语音...")

        def do_tts():
            scenes = self.storyboard.get("scenes", [])
            if sid >= len(scenes):
                return None
            scene = scenes[sid]
            speaker = scene.get("speaker", "旁白")
            dialogue = scene.get("dialogue", "")
            if not dialogue:
                return None

            voice = ""
            if self.char_manager and speaker:
                voice = self.char_manager.get_voice(speaker)
            
            emotion = scene.get("emotion", "default")
            
            from tts_engine import TTSEngine
            tts = TTSEngine()
            ep_num = self.current_ep + 1
            scene = scenes[sid]
            scene_id = scene.get("scene_id", sid + 1)
            os.makedirs(AUDIO_DIR, exist_ok=True)
            out = os.path.join(AUDIO_DIR, f"ep{ep_num:03d}_scene{scene_id:03d}.mp3")
            
            result = tts.synthesize(dialogue, out, voice_name=voice if voice else speaker, emotion=emotion)
            return result

        def on_done(result):
            if result:
                self._scan_existing_audio()
                self._log(f"✅ 场景{vals[0]}语音合成完成")
            else:
                self._log(f"❌ 场景{vals[0]}语音合成失败")

        self._run_in_thread(do_tts, on_done)


    def _build_step8_final(self):
        f = self.work_area
        ep_num = self.current_ep + 1
        tk.Label(f, text=f"🎞 第八步：最终视频合成 — 第{ep_num}集",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#1a1a2e").pack(anchor="w", pady=(0, 10))

        if not self.storyboard:
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            if os.path.exists(script_path):
                try:
                    with open(script_path, "r", encoding="utf-8") as ff:
                        self.storyboard = json.load(ff)
                except:
                    pass

        self._scan_existing_images()
        self._scan_existing_audio()
        if hasattr(self, '_scan_existing_videos'):
            self._scan_existing_videos()
        else:
            self.video_results = []

        scenes = self.storyboard.get("scenes", []) if self.storyboard else []
        ic = sum(1 for r in self.image_results if r and r.get("success"))
        ac = sum(1 for r in self.audio_results if r is not None)
        vc = sum(1 for r in self.video_results if r is not None)

        info = f"📊 {len(scenes)}场景 | {ic}图片 | {ac}音频 | {vc}视频"
        tk.Label(f, text=info, font=("Microsoft YaHei", 11), fg="#00ff88", bg="#1a1a2e").pack(anchor="w", pady=5)
        tk.Label(f, text="优先使用即梦视频，无视频用图片Ken Burns\n叠加音频+字幕合成完整视频",
                 font=("Microsoft YaHei", 10), fg="#aaa", bg="#1a1a2e", justify="left").pack(anchor="w", pady=10)
        self.btn_execute.config(text="▶ 合成最终视频（FFmpeg）")

    # ══════════════════════════════════════
    #  执行引擎
    # ══════════════════════════════════════

    def _execute_step(self):
        handlers = [
            self._exec_step1, self._exec_step2, self._exec_step3,
            self._exec_step4, self._exec_step5, self._exec_step6,
            self._exec_step7, self._exec_step8,
        ]
        handlers[self.current_step]()

    # --- Step 1 ---
    def _exec_step1(self):
        if not self.current_task_name:
            messagebox.showwarning('未选择任务', '请先在左侧「任务管理」中新建或选择一个任务。')
            return
        path = self.novel_entry.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror("错误", "请选择有效的小说文件")
            return

        self.novel_path = path
        with open(path, "r", encoding="utf-8") as f:
            self.novel_text = f.read()

        self.novel_preview.delete("1.0", "end")
        self.novel_preview.insert("1.0", self.novel_text[:2000] + "\n\n... (后略)")
        self._log(f"📖 已导入: {path} ({len(self.novel_text)}字)")

        if self.current_task_name:
            self.task_mgr.update_task(self.current_task_name, novel_path=path, status='importing')

        self.gemini = GeminiEngine()
        self.splitter = NovelSplitter()
        self.char_manager = CharacterManager()
        self.tts = TTSEngine()
        self.state = StateManager(path)

        # ★ 修复：尝试加载已锁定的角色
        self._load_locked_characters()

        def do_detect():
            return self.gemini.detect_genre(self.novel_text)

        def on_done(genre):
            genre_name = self.gemini.genre_style.get('cn_name', '未知')
            self.genre_label.config(text=f"📚 检测类型: {genre_name}")
            self._log(f"✅ 类型检测完成: {genre_name}")
            # ★ 自动保存任务状态
            try:
                if hasattr(self, 'state_manager') and self.state_manager:
                    self.state_manager.save()
            except:
                pass
                self._enable_next()

        self._run_in_thread(do_detect, on_done)

    # --- Step 2 ---
    def _exec_step2(self):
        if not self.novel_text:
            messagebox.showerror("错误", "请先导入小说")
            return

        def do_split():
            return self.splitter.split(self.novel_text)

        def on_done(episodes):
            self.episodes = episodes
            ep_names = [f"第{ep['episode']}集: {ep.get('title', '')[:15]}" for ep in episodes]
            self.ep_selector.config(values=ep_names)
            if ep_names:
                self.ep_selector.set(ep_names[0])
            # ★ 保存分集数据供任务恢复
            try:
                os.makedirs(SCRIPTS_DIR, exist_ok=True)
                ep_save_path = os.path.join(SCRIPTS_DIR, 'episodes.json')
                with open(ep_save_path, 'w', encoding='utf-8') as ef:
                    json.dump(episodes, ef, ensure_ascii=False, indent=2)
            except:
                pass
            self._show_step(1)
            # ★ 自动保存任务状态
            try:
                if hasattr(self, 'state_manager') and self.state_manager:
                    self.state_manager.save()
            except:
                pass
                self._enable_next()
            self._log(f"✅ 分为 {len(episodes)} 集")

        self._run_in_thread(do_split, on_done)

    # --- Step 3 ---
    def _exec_step3(self):
        if not self.episodes:
            messagebox.showerror("错误", "请先完成分集")
            return

        if self.characters_locked:
            if not messagebox.askyesno("角色已锁定",
                "角色外貌已锁定，重新提取会覆盖现有角色。\n\n要先解锁再提取吗？"):
                return
            self.characters_locked = False

        def do_extract():
            all_chars = []
            ep = self.episodes[self.current_ep]
            ep_text = ep["text"]
            ep_num = ep["episode"]

            if len(ep_text) < 200:
                self.root.after(0, lambda: self._log(f"❌ 第{ep_num}集内容太短({len(ep_text)}字)，请切换到有内容的集"))
                return []

            self.root.after(0, lambda: self._log(f"🔍 提取第{ep_num}集角色..."))

            chars = None
            for retry in range(3):
                chars = self.gemini.extract_characters(ep_text, "", ep_num)
                if chars:
                    break
                self.root.after(0, lambda r=retry+1:
                                self._log(f"⚠ 第{r}次提取失败，重试..."))
                time.sleep(3)

            if chars:
                all_chars.extend(chars)
                self.char_manager.update_characters(chars)
                self.root.after(0, lambda c=len(chars):
                                self._log(f"✅ 提取到 {c} 个角色"))
            else:
                self.root.after(0, lambda: self._log(f"❌ 角色提取3次均失败"))

            return all_chars

        def on_done(chars):
            self.characters = chars
            if self.gemini:
                self.gemini.set_character_profiles(chars)
            self._show_step(2)
            if chars:
                # ★ 自动保存任务状态
                try:
                    if hasattr(self, 'state_manager') and self.state_manager:
                        self.state_manager.save()
                except:
                    pass
                    self._enable_next()
                self._log(f"✅ 共提取 {len(chars)} 个角色")

        self._run_in_thread(do_extract, on_done)

    # --- Step 4 ---
    def _exec_step4(self):
        if not self.episodes:
            messagebox.showerror("错误", "请先完成分集")
            return

        ep_data = self.episodes[self.current_ep]
        ep_text = ep_data["text"]
        ep_num = ep_data["episode"]
        chars_summary = self.char_manager.build_characters_summary()

        if self.gemini:
            self.gemini.set_character_profiles(self.characters)
            # 传递固定服装DNA
            if self.char_manager:
                _odna = self.char_manager.get_all_outfit_dna()
                if hasattr(self.gemini, 'set_outfit_dna_cache'):
                    self.gemini.set_outfit_dna_cache(_odna)

        def do_storyboard():
            return self.gemini.generate_storyboard(ep_text, chars_summary, episode_num=ep_num)

        def on_done(sb):
            self.storyboard = sb
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            with open(script_path, "w", encoding="utf-8") as ff:
                json.dump(sb, ff, ensure_ascii=False, indent=2)

            scenes = sb.get("scenes", [])
            empty_cn = [s for s in scenes if not s.get("visual_description_cn")]
            if empty_cn:
                self._log(f"⏳ {len(empty_cn)}个场景缺少中文描述，自动翻译中...")
                for s in empty_cn:
                    en = s.get("visual_description_en", "")
                    if en:
                        cn = self.gemini.translate_en_to_cn(en)
                        s["visual_description_cn"] = cn if cn else ""
                        time.sleep(0.5)

            self._show_step(3)
            # ★ 自动保存任务状态
            try:
                if hasattr(self, 'state_manager') and self.state_manager:
                    self.state_manager.save()
            except:
                pass
                self._enable_next()
            self._log(f"✅ 第{ep_num}集: {len(scenes)}个场景")

        self._run_in_thread(do_storyboard, on_done)

    # --- Step 5 --- ★ 断点续传版
    def _exec_step5(self):
        """批量生成全部图片 — 跳过已有图片 + 服装DNA"""
        if not self.storyboard:
            messagebox.showerror("错误", "请先生成分镜剧本")
            return

        # 确保outfit_dna已传递
        if self.gemini and self.char_manager:
            self.gemini.set_character_profiles(self.characters)
            _odna = self.char_manager.get_all_outfit_dna()
            if hasattr(self.gemini, 'set_outfit_dna_cache'):
                self.gemini.set_outfit_dna_cache(_odna)

        scenes = self.storyboard.get("scenes", [])
        ep_num = self.current_ep + 1

        # ★ 先扫描已有图片
        self._scan_existing_images()

        def do_images():
            results = list(self.image_results)  # 拷贝现有结果
            skipped = 0
            generated = 0
            candidates_map = {}  # {i: [path1, path2, path3]}

            for i, scene in enumerate(scenes):
                sid = scene.get('scene_id', i + 1)

                # ★ 断点续传：如果已有图片且成功，跳过
                if i < len(results) and results[i].get('success'):
                    skipped += 1
                    self.root.after(0, lambda s=sid, sk=skipped, t=len(scenes):
                            self._log(f"🖼跳过场景{s}（已有图片）[{sk}/{t}]"))
                    continue

                prompt = scene.get('visual_description_en',
                                    scene.get('visual_description', ''))

                # ★ 改进：注入角色外貌
                char_names = scene.get('characters', [])
                if char_names:
                    prompt = self.gemini._enrich_prompt_with_characters(prompt, char_names)

                save_dir = IMAGES_DIR
                base_name = f'ep{ep_num:03d}_scene{sid:03d}'

                self.root.after(0, lambda s=sid, t=len(scenes):
                        self._log(f"🎨 生成场景{s}/{t} 的3张候选图..."))

                # 生成多张候选
                # ★ 收集角色参考图
                ref_image_paths = []
                if self.char_manager and char_names:
                    for _cn in char_names:
                        _ref = self.char_manager.get_reference_image(_cn)
                        if _ref:
                            ref_image_paths.append(_ref)
                if ref_image_paths:
                    self.root.after(0, lambda: self._log(f"📎 附加 {len(ref_image_paths)} 张角色参考图"))

                cands = self.gemini.generate_image_candidates(
                    prompt, save_dir, base_name, count=3, reference_image_paths=ref_image_paths if ref_image_paths else None)

                if cands:
                    candidates_map[i] = {
                        'scene_id': sid,
                        'candidates': cands,
                        'prompt': prompt,
                        'base_name': base_name
                    }
                    # 先用第一张作为默认
                    result = {
                        'scene_id': sid,
                        'image_path': cands[0],
                        'success': True
                    }
                else:
                    result = {
                        'scene_id': sid,
                        'image_path': None,
                        'success': False
                    }

                # 确保results列表够长
                while len(results) <= i:
                    results.append({'scene_id': i + 1, 'image_path': None, 'success': False})
                results[i] = result
                generated += 1
                time.sleep(2)

            return {'results': results, 'skipped': skipped,
                    'generated': generated, 'candidates_map': candidates_map}

        def on_done(data):
            results = data['results']
            skipped = data['skipped']
            generated = data['generated']
            candidates_map = data['candidates_map']

            # 弹出选择对话框让用户逐个选图
            for i, info in candidates_map.items():
                sid = info['scene_id']
                cands = info['candidates']
                if len(cands) <= 1:
                    continue  # 只有1张或0张，无需选择

                dialog = ImageSelectorDialog(self.root, cands, sid)
                chosen = dialog.result

                if chosen and chosen in cands:
                    results[i]['image_path'] = chosen
                    # 删除未选中的候选图
                    # for c in cands:
                    # if c != chosen:
                    # try:
                    # os.remove(c)
                    # self._log(f"  🗑 删除未选候选: {os.path.basename(c)}")
                    # except:
                    # pass
                    self._log(f"✅ 场景{sid} 已选择: {os.path.basename(chosen)}")
                else:
                    # 用户跳过，保留第一张，删除其余
                    if cands:
                        results[i]['image_path'] = cands[0]
                    # for c in cands[1:]:
                    # try:
                    # os.remove(c)
                    # except:
                    # pass
                    self._log(f"⏭ 场景{sid} 跳过选择，使用第一张")

            self.image_results = results
            self._show_step(4)
            success = sum(1 for r in results if r.get('success'))
            self._log(f"✅ 图片完成：{success}/{len(results)} 张成功（跳过{skipped}张，新生成{generated}张）")
            if success > 0:
                # ★ 自动保存任务状态
                try:
                    if hasattr(self, 'state_manager') and self.state_manager:
                        self.state_manager.save()
                except:
                    pass
            # ★ 链式帧生成：基于选定的图片生成帧序列
            if self.gemini and self.storyboard:
                try:
                    self._log(f"🔗 开始链式帧生成...")
                    frame_seq = self.gemini.generate_scene_frames_chain(
                        self.storyboard,
                        IMAGES_DIR,
                        style_prefix=getattr(self, "style_prefix", ""),
                        _progress=lambda msg: self.root.after(0, lambda m=msg: self._log(m))
                    )
                    self.frame_sequence = frame_seq
                    self._scan_existing_images()
                    self._log(f"✅ 链式帧生成完成，共 {len(frame_seq)} 帧")
                except Exception as e:
                    self._log(f"⚠️ 链式帧生成失败: {e}")

                self._enable_next()

        self._run_in_thread(do_images, on_done)

    # --- Step 6 --- ★ 断点续传版
    def _exec_step6(self):
        """批量合成语音 — 跳过已有音频"""
        if not self.storyboard:
            return
        scenes = self.storyboard.get("scenes", [])
        ep_num = self.current_ep + 1

        # ★ 先扫描已有音频
        self._scan_existing_audio()

        def do_tts():
            results = list(self.audio_results)
            skipped = 0
            generated = 0

            for i, s in enumerate(scenes):
                sid = s.get("scene_id", 0)

                # ★ 断点续传：如果已有音频，跳过
                if i < len(results) and results[i] is not None:
                    skipped += 1
                    continue

                dialogue = s.get("dialogue", "")
                speaker = s.get("speaker", "")
                scene_type = s.get("scene_type", "action")
                voice = self.char_manager.get_voice(speaker) if speaker else "旁白"
                emotion = s.get("emotion", "default")
                audio_path = os.path.join(AUDIO_DIR, f"ep{ep_num:03d}_scene{sid:03d}.mp3")

                if scene_type in ("dialogue", "narration") and dialogue:
                    result = self.tts.synthesize(dialogue, audio_path, voice_name=voice, emotion=emotion)
                else:
                    result = self.tts.generate_silence(3.0, audio_path)

                while len(results) <= i:
                    results.append(None)
                results[i] = result
                generated += 1

            return {"results": results, "skipped": skipped, "generated": generated}

        def on_done(data):
            results = data["results"]
            skipped = data["skipped"]
            generated = data["generated"]
            self.audio_results = results
            for item in self.tts_tree.get_children():
                vals = list(self.tts_tree.item(item, "values"))
                vals[4] = "✅"
                self.tts_tree.item(item, values=vals)
                # ★ 自动保存任务状态
                try:
                    if hasattr(self, 'state_manager') and self.state_manager:
                        self.state_manager.save()
                except:
                    pass
                self._enable_next()
            self._log(f"✅ 语音完成: {len(results)} 条 (跳过{skipped}条, 新合成{generated}条)")

        self._run_in_thread(do_tts, on_done)

    # --- Step 7 ---
    def _exec_step8(self):
        """最终视频合成"""
        if not self.storyboard:
            messagebox.showerror("错误", "请先完成前面步骤")
            return
        scenes = self.storyboard.get("scenes", [])
        ep_num = self.current_ep + 1
        self._scan_existing_images()
        self._scan_existing_audio()
        if hasattr(self, '_scan_existing_videos'):
            self._scan_existing_videos()
        else:
            self.video_results = []

        def do_final():
            from capcut_editor import CapcutEditor
            editor = CapcutEditor()
            for i, scene in enumerate(scenes):
                sid = scene.get("scene_id", i + 1)
                ip = None
                if i < len(self.image_results) and self.image_results[i].get("success"):
                    ip = self.image_results[i]["image_path"]
                vp = None
                if i < len(self.video_results) and self.video_results[i]:
                    vp = self.video_results[i]
                ap = None
                ad = 3.0
                if i < len(self.audio_results) and self.audio_results[i] is not None:
                    ai = self.audio_results[i]
                    if isinstance(ai, dict):
                        ap = ai.get("path")
                        ad = ai.get("duration", 3.0)
                    elif isinstance(ai, str):
                        ap = ai
                clip = {
                    "scene_title": f"scene_{sid}",
                    "scene_type": scene.get("scene_type", "action"),
                    "image_path": ip,
                    "video_path": vp,
                    "audio_path": ap,
                    "narrative": scene.get("dialogue", ""),
                    "speaker": scene.get("speaker", ""),
                    "duration": scene.get("duration", 3),
                    "actual_duration": ad if ad > 0 else scene.get("duration", 3),
                }
                editor.add_clip(clip)
                self.root.after(0, lambda s=sid: self._log(f"   📦 场景{s}"))
            editor.build(f"ep{ep_num:03d}")
            final = editor.export_video_ffmpeg(f"ep{ep_num:03d}_final.mp4")
            return final

        def on_done(fp):
            if fp and os.path.exists(fp):
                mb = os.path.getsize(fp) / (1024*1024)
                self._log(f"🎉 最终视频: {fp} ({mb:.1f}MB)")
                messagebox.showinfo("完成", f"视频已生成:\n{fp}\n{mb:.1f}MB")
            else:
                self._log("❌ 合成失败")
                messagebox.showerror("错误", "合成失败")

        self._run_in_thread(do_final, on_done)

    # ══════════════════════════════════════
    #  集数切换
    # ══════════════════════════════════════

    def _on_ep_changed(self, event=None):
        sel = self.ep_selector.current()
        if sel >= 0:
            self.current_ep = sel
            self.storyboard = None
            self.image_results = []
            self.audio_results = []
            self._log(f"🎬 切换到第{sel + 1}集")

            # ★ 修复：尝试加载已有的剧本
            ep_num = sel + 1
            script_path = os.path.join(SCRIPTS_DIR, f"ep{ep_num:03d}_script.json")
            if os.path.exists(script_path):
                try:
                    with open(script_path, "r", encoding="utf-8") as f:
                        self.storyboard = json.load(f)
                    self._log(f"📂 已加载第{ep_num}集剧本")
                except:
                    pass

            if self.characters_locked:
                self._log(f"🔒 角色形象已锁定，保持统一")
                if self.gemini:
                    self.gemini.set_character_profiles(self.characters)

            if self.current_step >= 3:
                self._show_step(self.current_step)

    # ══════════════════════════════════════
    #  启动
    # ══════════════════════════════════════


    # ==============================
    #  Task Management Methods
    # ==============================

    def _refresh_task_list(self):
        tasks = self.task_mgr.list_tasks()
        names = [t['display_name'] for t in tasks]
        self.task_combo.config(values=names if names else ['无任务'])
        if self.current_task_name:
            for i, t in enumerate(tasks):
                if t['name'] == self.current_task_name:
                    self.task_combo.current(i)
                    break
        else:
            self.task_combo.set('无任务')

    def _create_new_task(self):
        import tkinter.simpledialog as simpledialog
        name = simpledialog.askstring('新建任务', '请输入任务名称:',
                                       parent=self.root)
        if not name or not name.strip():
            return
        task = self.task_mgr.create_task(name)
        if task is None:
            messagebox.showwarning('任务名重复', f'任务「{name.strip()}」已存在！\n请换一个名称。')
            return
        self._switch_to_task(task['name'])
        self._refresh_task_list()
        self._log('📂 新建任务: ' + task['display_name'])
        messagebox.showinfo('成功', '任务「' + task['display_name'] + '」已创建！')

    def _delete_current_task(self):
        if not self.current_task_name:
            messagebox.showinfo('提示', '请先选择一个任务')
            return
        task = self.task_mgr.get_task(self.current_task_name)
        if not task:
            return
        if not messagebox.askyesno('确认删除',
                '确定要删除任务「' + task['display_name'] + '」吗？\n\n⚠ 这将删除该任务的所有数据！'):
            return
        self.task_mgr.delete_task(self.current_task_name)
        self.current_task = None
        self.current_task_name = None
        self._reset_task_state()
        self._refresh_task_list()
        self.task_status_label.config(text='未选择任务')
        self._log('🗑 任务已删除')
        self._show_step(0)

    def _on_task_selected(self, event=None):
        tasks = self.task_mgr.list_tasks()
        idx = self.task_combo.current()
        if idx < 0 or idx >= len(tasks):
            return
        task = tasks[idx]
        if task['name'] != self.current_task_name:
            self._switch_to_task(task['name'])

    def _switch_to_task(self, task_name):
        task = self.task_mgr.get_task(task_name)
        if not task:
            return
        self.current_task = task
        self.current_task_name = task_name

        dirs = self.task_mgr.get_task_dirs(task_name)
        import config as _cfg
        _cfg.SCRIPTS_DIR = dirs['scripts']
        _cfg.IMAGES_DIR = dirs['images']
        _cfg.VIDEOS_DIR = dirs['videos']
        _cfg.AUDIO_DIR = dirs['audio']
        _cfg.FINAL_DIR = dirs['final']
        _cfg.CHARACTERS_DIR = dirs['characters']
        _cfg.BACKGROUNDS_DIR = dirs['backgrounds']
        _cfg.PROFILE_DIR = dirs['profiles']
        _cfg.STATE_DIR = dirs['state']

        global SCRIPTS_DIR, IMAGES_DIR, VIDEOS_DIR, AUDIO_DIR, FINAL_DIR, CHARACTERS_DIR, BACKGROUNDS_DIR, PROFILE_DIR, STATE_DIR
        SCRIPTS_DIR = dirs['scripts']
        IMAGES_DIR = dirs['images']
        VIDEOS_DIR = dirs['videos']
        AUDIO_DIR = dirs['audio']
        FINAL_DIR = dirs['final']
        CHARACTERS_DIR = dirs['characters']
        BACKGROUNDS_DIR = dirs['backgrounds']
        PROFILE_DIR = dirs['profiles']
        STATE_DIR = dirs['state']

        self._reset_task_state()

        self.novel_path = task.get('novel_path')
        if self.novel_path and os.path.exists(self.novel_path):
            with open(self.novel_path, 'r', encoding='utf-8') as f:
                self.novel_text = f.read()

        self._load_locked_characters()

        # ★ 恢复引擎状态
        if self.novel_text:
            self.gemini = GeminiEngine()
            self.splitter = NovelSplitter()
            self.char_manager = CharacterManager()
            self.tts = TTSEngine()
            self.state = StateManager(self.novel_path or '')
            # 检测类型
            self.gemini.detect_genre(self.novel_text)
            # 恢复角色
            if self.characters:
                self.gemini.set_character_profiles(self.characters)
                self.char_manager.update_characters(self.characters)
            # 恢复分集
            try:
                ep_list_path = os.path.join(dirs['scripts'], 'episodes.json')
                if os.path.exists(ep_list_path):
                    with open(ep_list_path, 'r', encoding='utf-8') as ef:
                        self.episodes = json.load(ef)
                    ep_names = [f"第{ep['episode']}集: {ep.get('title', '')[:15]}" for ep in self.episodes]
                    self.ep_selector.config(values=ep_names)
                    if ep_names:
                        self.ep_selector.set(ep_names[0])
                    self._log(f"📂 恢复 {len(self.episodes)} 集")
                elif self.splitter:
                    self.episodes = self.splitter.split(self.novel_text)
                    ep_names = [f"第{ep['episode']}集: {ep.get('title', '')[:15]}" for ep in self.episodes]
                    self.ep_selector.config(values=ep_names)
                    if ep_names:
                        self.ep_selector.set(ep_names[0])
            except Exception as ex:
                self._log(f"⚠ 恢复分集失败: {ex}")
            # 恢复剧本
            ep_num_r = self.current_ep + 1
            script_path_r = os.path.join(dirs['scripts'], f"ep{ep_num_r:03d}_script.json")
            if os.path.exists(script_path_r):
                try:
                    with open(script_path_r, 'r', encoding='utf-8') as sf:
                        self.storyboard = json.load(sf)
                    self._log(f"📂 恢复第{ep_num_r}集剧本")
                except:
                    pass
            # 恢复图片/音频/视频
            self._scan_existing_images()
            self._scan_existing_audio()
            self._scan_existing_videos()

        self.task_status_label.config(text='📂 ' + task['display_name'])
        self.root.title('📖 小说转视频 v4.1 - ' + task['display_name'])
        self._log('📂 切换到任务: ' + task['display_name'])
        self._refresh_task_list()
        # ★ 智能跳转到最后完成的步骤
        resume_step = 0
        if self.novel_text:
            resume_step = 1
        if self.episodes:
            resume_step = 1
        if self.characters:
            resume_step = 2
        if self.storyboard and self.storyboard.get('scenes'):
            resume_step = 3
        if self.image_results and any(r.get('success') for r in self.image_results):
            resume_step = 4
        if self.audio_results and any(r is not None for r in self.audio_results):
            resume_step = 5
        if self.video_results and any(r is not None for r in self.video_results):
            resume_step = 6
        self._show_step(resume_step)
        self.current_step = resume_step

    def _reset_task_state(self):
        self.novel_path = None
        self.novel_text = ''
        self.episodes = []
        self.characters = []
        self.characters_locked = False
        self.current_ep = 0
        self.storyboard = None
        self.image_results = []
        self.audio_results = []
        self.current_step = 0
        self.video_results = []
        self.gemini = None
        self.char_manager = None
        self.tts = None
        self.state = None
        self.splitter = None
        self.ep_selector.set('先导入小说')
        self.ep_selector.config(values=['先导入小说'])


    def run(self):
        self.root.mainloop()


def launch_gui():
    init_all_engines()
    app = StepGUI()
    app.run()


if __name__ == "__main__":
    launch_gui()
