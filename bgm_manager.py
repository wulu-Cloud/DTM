"""BGM自动选曲管理器"""
import os
import random

# 情绪关键词 -> BGM映射
MOOD_BGM_MAP = {
    # 紧张/悬疑
    "tense": ["tense", "action"],
    "紧张": ["tense", "action"],
    "焦虑": ["tense"],
    "危险": ["tense", "action"],
    "追赶": ["tense", "action"],
    "逃跑": ["tense", "action"],
    "紧迫": ["tense"],
    # 悲伤
    "sad": ["sad", "romantic"],
    "悲伤": ["sad"],
    "melancholy": ["sad"],
    "忧郁": ["sad"],
    "哭泣": ["sad"],
    "泪": ["sad"],
    "离别": ["sad"],
    "分手": ["sad"],
    "孤独": ["sad"],
    "寂寞": ["sad"],
    "回忆": ["sad", "romantic"],
    "思念": ["sad", "romantic"],
    "伤心": ["sad"],
    "痛苦": ["sad"],
    "遗憾": ["sad"],
    "失去": ["sad"],
    "雨": ["sad", "peaceful"],
    # 快乐
    "happy": ["happy", "peaceful"],
    "开心": ["happy"],
    "joyful": ["happy"],
    "欢乐": ["happy"],
    "庆祝": ["happy"],
    "庆典": ["happy"],
    "笑": ["happy"],
    "喜悦": ["happy"],
    "幸福": ["happy"],
    "快乐": ["happy"],
    "欢笑": ["happy"],
    "热闹": ["happy"],
    "载歌载舞": ["happy"],
    # 浪漫
    "romantic": ["romantic", "peaceful"],
    "浪漫": ["romantic"],
    "温馨": ["romantic", "peaceful"],
    "爱情": ["romantic"],
    "柔情": ["romantic"],
    "蜜意": ["romantic"],
    "相拥": ["romantic"],
    "亲吻": ["romantic"],
    "牵手": ["romantic"],
    "月光": ["romantic", "peaceful"],
    "漫步": ["romantic", "peaceful"],
    "温柔": ["romantic"],
    "深情": ["romantic"],
    "告白": ["romantic"],
    # 神秘/恐怖
    "mysterious": ["mysterious", "horror"],
    "神秘": ["mysterious"],
    "suspense": ["mysterious", "tense"],
    "悬疑": ["mysterious", "tense"],
    "诡异": ["horror", "mysterious"],
    "阴森": ["horror"],
    "horror": ["horror"],
    "恐怖": ["horror"],
    "scary": ["horror"],
    "恐惧": ["horror", "tense"],
    "黑暗": ["horror", "mysterious"],
    "鬼": ["horror"],
    "怪物": ["horror", "action"],
    # 动作/史诗
    "action": ["action", "epic"],
    "战斗": ["action", "epic"],
    "fight": ["action"],
    "打斗": ["action"],
    "激烈": ["action", "epic"],
    "刀": ["action"],
    "剑": ["action"],
    "枪": ["action"],
    "爆炸": ["action", "epic"],
    "冲锋": ["action", "epic"],
    "angry": ["action", "tense"],
    "愤怒": ["action", "tense"],
    # 平静
    "peaceful": ["peaceful", "neutral"],
    "平静": ["peaceful"],
    "calm": ["peaceful"],
    "日常": ["peaceful", "neutral"],
    "宁静": ["peaceful"],
    "清晨": ["peaceful"],
    "自然": ["peaceful"],
    # 史诗/宏大
    "epic": ["epic", "action"],
    "宏大": ["epic"],
    "壮观": ["epic"],
    "壮丽": ["epic"],
    "磅礴": ["epic"],
    "英雄": ["epic", "action"],
    "胜利": ["epic", "happy"],
    "征服": ["epic"],
}

# 场景类型 -> 默认情绪
SCENE_TYPE_MOOD = {
    "action": "action",
    "dialogue": "neutral",
    "romance": "romantic",
    "suspense": "tense",
    "horror": "horror",
    "comedy": "happy",
    "drama": "sad",
    "daily": "peaceful",
}


class BGMManager:
    """自动根据场景情绪选择BGM"""
    
    def __init__(self, bgm_dir="./assets/bgm"):
        self.bgm_dir = bgm_dir
        self.bgm_cache = {}
        self._scan_bgm_files()
        self.current_mood = None
    
    def _scan_bgm_files(self):
        """扫描BGM目录"""
        if not os.path.exists(self.bgm_dir):
            os.makedirs(self.bgm_dir, exist_ok=True)
            print(f"[BGM] BGM目录已创建: {self.bgm_dir}")
            return
        for f in os.listdir(self.bgm_dir):
            if f.endswith(('.mp3', '.wav', '.ogg')):
                name = os.path.splitext(f)[0]
                self.bgm_cache[name] = os.path.join(self.bgm_dir, f)
        if self.bgm_cache:
            print(f"[BGM] 已加载 {len(self.bgm_cache)} 个BGM文件")
        else:
            print(f"[BGM] BGM目录为空: {self.bgm_dir}")
    
    def select_bgm(self, scene_text="", scene_type="", mood="", episode_num=1):
        """
        根据场景信息自动选择BGM
        返回: BGM文件路径 或 None
        """
        if not self.bgm_cache:
            return None
        
        # 优先级1: 直接指定mood
        if mood and mood in self.bgm_cache:
            self.current_mood = mood
            return self.bgm_cache[mood]
        
        # 优先级2: 从情绪关键词匹配
        candidates = self._match_mood_from_text(scene_text)
        
        # 优先级3: 从场景类型推断
        if not candidates and scene_type in SCENE_TYPE_MOOD:
            default_mood = SCENE_TYPE_MOOD[scene_type]
            if default_mood in self.bgm_cache:
                candidates = [default_mood]
        
        # 优先级4: 默认neutral
        if not candidates:
            if "neutral" in self.bgm_cache:
                candidates = ["neutral"]
            else:
                candidates = list(self.bgm_cache.keys())
        
        # 选择
        if candidates:
            chosen = random.choice(candidates)
            self.current_mood = chosen
            return self.bgm_cache.get(chosen)
        
        return None
    
    def _match_mood_from_text(self, text):
        """从文本中匹配情绪关键词"""
        if not text:
            return []
        text_lower = text.lower()
        matched_moods = set()
        for keyword, bgm_names in MOOD_BGM_MAP.items():
            if keyword in text_lower:
                for name in bgm_names:
                    if name in self.bgm_cache:
                        matched_moods.add(name)
        return list(matched_moods)
    
    def select_bgm_for_episode(self, scenes, episode_num=1):
        """
        为整集选择BGM（分析所有场景的整体情绪）
        """
        all_text = ""
        scene_types = []
        for scene in scenes:
            if isinstance(scene, dict):
                all_text += " " + scene.get("visual_description", "")
                all_text += " " + scene.get("dialogue", "")
                all_text += " " + scene.get("narration", "")
                scene_types.append(scene.get("scene_type", ""))
        
        # 统计最常见场景类型
        main_type = ""
        if scene_types:
            from collections import Counter
            type_counts = Counter(t for t in scene_types if t)
            if type_counts:
                main_type = type_counts.most_common(1)[0][0]
        
        return self.select_bgm(scene_text=all_text, scene_type=main_type, episode_num=episode_num)
    
    def get_available_moods(self):
        """返回可用的情绪列表"""
        return list(self.bgm_cache.keys())
