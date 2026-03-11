"""
========================================
💾 断点续跑管理器
========================================
"""
import os
import json
import hashlib
import time
import config as _cfg


class StateManager:
    """进度状态管理"""

    STEPS = ["characters", "storyboard", "images", "videos", "tts", "edit", "done"]

    def __init__(self, novel_path: str = None):
        if novel_path and os.path.exists(novel_path):
            self.novel_path = novel_path
            self.novel_id = self._make_id(novel_path)
        else:
            self.novel_path = novel_path or "default"
            self.novel_id = "default"

        self.state_file = os.path.join(_cfg.STATE_DIR, f"{self.novel_id}.json")
        self.state = self._load()
        print(f"💾 进度管理器: {self.novel_id}")

    def _make_id(self, path: str) -> str:
        name = os.path.basename(path)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        raw = f"{name}_{size}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _load(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            print(f"   📂 已加载进度: 共{state.get('total_episodes',0)}集, "
                  f"已完成{len(state.get('completed_episodes',[]))}集")
            return state
        return {
            "novel_id": self.novel_id,
            "novel_name": os.path.basename(self.novel_path) if self.novel_path else "default",
            "total_episodes": 0,
            "completed_episodes": [],
            "current_episode": 0,
            "episodes": {},
            "global_characters": None,
            "style": "",
            "cache": {},
            "updated_at": ""
        }

    def save(self):
        self.state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(_cfg.STATE_DIR, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    # ==================== load_or_run（关键方法） ====================

    def load_or_run(self, key: str, func, force=False):
        """
        如果缓存中有key的结果，直接返回；否则执行func并缓存
        """
        cache = self.state.setdefault("cache", {})

        if not force and key in cache and cache[key] is not None:
            print(f"   💾 从缓存加载: {key}")
            return cache[key]

        print(f"   ⏳ 执行: {key}...")
        result = func()
        cache[key] = result
        self.save()
        print(f"   💾 已缓存: {key}")
        return result

    # ==================== 全局 ====================

    def set_total_episodes(self, total: int):
        self.state["total_episodes"] = total
        self.save()

    def set_style(self, style: str):
        self.state["style"] = style
        self.save()

    def set_global_characters(self, characters):
        self.state["global_characters"] = characters
        self.save()

    def get_global_characters(self):
        return self.state.get("global_characters")

    # ==================== 每集 ====================

    def get_episode_state(self, ep_num: int) -> dict:
        return self.state["episodes"].get(str(ep_num), {})

    def init_episode(self, ep_num: int):
        key = str(ep_num)
        if key not in self.state["episodes"]:
            self.state["episodes"][key] = {
                "status": "pending",
                "steps_completed": [],
                "scene_results": [],
                "storyboard": None,
                "characters": None
            }
            self.save()

    def complete_step(self, ep_num: int, step: str, data: dict = None):
        key = str(ep_num)
        ep = self.state["episodes"].get(key, {})
        if step not in ep.get("steps_completed", []):
            ep.setdefault("steps_completed", []).append(step)
        if data:
            ep.update(data)
        ep["status"] = step
        self.state["episodes"][key] = ep
        self.state["current_episode"] = ep_num
        self.save()
        print(f"   💾 第{ep_num}集 [{step}] ✓ 已保存")

    def mark_episode_done(self, ep_num: int):
        key = str(ep_num)
        self.state["episodes"].setdefault(key, {})["status"] = "done"
        if ep_num not in self.state["completed_episodes"]:
            self.state["completed_episodes"].append(ep_num)
        self.save()

    def is_step_done(self, ep_num: int, step: str) -> bool:
        ep = self.get_episode_state(ep_num)
        return step in ep.get("steps_completed", [])

    def get_resume_point(self) -> tuple:
        for ep_num in range(1, self.state["total_episodes"] + 1):
            ep = self.get_episode_state(ep_num)
            if ep.get("status") == "done":
                continue
            completed = ep.get("steps_completed", [])
            for step in self.STEPS:
                if step not in completed:
                    return (ep_num, step)
        return (None, None)

    def get_progress_summary(self) -> str:
        total = self.state["total_episodes"]
        done = len(self.state["completed_episodes"])
        ep, step = self.get_resume_point()
        if ep is None:
            return f"✅ 全部完成! ({done}/{total}集)"
        return f"📊 进度: {done}/{total}集完成, 下一步: 第{ep}集-{step}"

    def get_scene_status(self, ep_num, scene_id):
        """获取单个场景的完成状态"""
        ep_key = f"ep{ep_num:03d}"
        ep_data = self.state.get("episodes", {}).get(ep_key, {})
        scenes = ep_data.get("scene_status", {})
        return scenes.get(str(scene_id), {
            "image": False,
            "audio": False,
            "video": False,
        })
    
    def set_scene_status(self, ep_num, scene_id, field, value=True):
        """设置单个场景某项的完成状态"""
        ep_key = f"ep{ep_num:03d}"
        if "episodes" not in self.state:
            self.state["episodes"] = {}
        if ep_key not in self.state["episodes"]:
            self.state["episodes"][ep_key] = {}
        ep_data = self.state["episodes"][ep_key]
        if "scene_status" not in ep_data:
            ep_data["scene_status"] = {}
        
        sid = str(scene_id)
        if sid not in ep_data["scene_status"]:
            ep_data["scene_status"][sid] = {"image": False, "audio": False, "video": False}
        
        ep_data["scene_status"][sid][field] = value
        self.save()
    
    def clear_scene_cache(self, ep_num, scene_id, from_field="image"):
        """清除某场景指定阶段及后续的缓存"""
        ep_key = f"ep{ep_num:03d}"
        ep_data = self.state.get("episodes", {}).get(ep_key, {})
        scenes = ep_data.get("scene_status", {})
        sid = str(scene_id)
        if sid in scenes:
            fields = ["image", "audio", "video"]
            start = fields.index(from_field) if from_field in fields else 0
            for f in fields[start:]:
                scenes[sid][f] = False
            self.save()
    
    def get_episode_progress(self, ep_num):
        """获取整集进度概览"""
        ep_key = f"ep{ep_num:03d}"
        ep_data = self.state.get("episodes", {}).get(ep_key, {})
        scenes = ep_data.get("scene_status", {})
        
        total = len(scenes)
        if total == 0:
            return {"total": 0, "image_done": 0, "audio_done": 0, "video_done": 0}
        
        return {
            "total": total,
            "image_done": sum(1 for s in scenes.values() if s.get("image")),
            "audio_done": sum(1 for s in scenes.values() if s.get("audio")),
            "video_done": sum(1 for s in scenes.values() if s.get("video")),
        }

