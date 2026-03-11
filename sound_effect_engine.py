"""
sound_effect_engine.py - 音效自动匹配引擎
按场景类型和关键词自动匹配音效，实现音量分层
"""
import os
import re

# 音效关键词映射（关键词 -> 音效类别）
SCENE_SOUND_MAP = {
    # 环境音效
    "rain": "rain_ambient",
    "雨": "rain_ambient",
    "storm": "storm_ambient",
    "暴风": "storm_ambient",
    "night": "night_crickets",
    "夜": "night_crickets",
    "forest": "forest_birds",
    "森林": "forest_birds",
    "city": "city_traffic",
    "城市": "city_traffic",
    "street": "street_ambient",
    "街道": "street_ambient",
    "ocean": "ocean_waves",
    "sea": "ocean_waves",
    "wind": "wind_howl",
    "风": "wind_howl",
    "snow": "snow_crunch",
    "雪": "snow_crunch",
    
    # 动作音效
    "explosion": "explosion_boom",
    "爆炸": "explosion_boom",
    "fight": "punch_hit",
    "打斗": "punch_hit",
    "sword": "sword_clash",
    "剑": "sword_clash",
    "gun": "gunshot",
    "枪": "gunshot",
    "door": "door_creak",
    "门": "door_creak",
    "footstep": "footsteps",
    "脚步": "footsteps",
    "car": "car_engine",
    "车": "car_engine",
    "glass": "glass_break",
    "破碎": "glass_break",
    "fire": "fire_crackle",
    "火": "fire_crackle",
    
    # 情绪音效
    "scream": "scream_horror",
    "尖叫": "scream_horror",
    "laugh": "laugh_evil",
    "笑": "laugh_crowd",
    "cry": "cry_soft",
    "哭": "cry_soft",
    "heartbeat": "heartbeat_fast",
    "心跳": "heartbeat_fast",
    "thunder": "thunder_crack",
    "雷": "thunder_crack",
    
    # 特殊音效
    "magic": "magic_spell",
    "魔法": "magic_spell",
    "dragon": "dragon_roar",
    "龙": "dragon_roar",
    "警灯": "police_siren",
    "police": "police_siren",
    "alarm": "alarm_beep",
    "钟声": "bell_toll",
    "bell": "bell_toll",
    "翅膀": "wing_flap",
    "wing": "wing_flap",
}

# 音量分层比例
VOLUME_LAYERS = {
    "voice": 1.0,       # 人声 = 基准
    "effect": 0.5,      # 剧情音效 = 人声50%
    "ambient": 0.17,    # 环境音效 = 人声17%
    "bgm": 0.12,        # BGM = 人声12%
}

# 音效类别分类
EFFECT_CATEGORIES = {
    "ambient": [
        "rain_ambient", "storm_ambient", "night_crickets", "forest_birds",
        "city_traffic", "street_ambient", "ocean_waves", "wind_howl",
        "snow_crunch", "fire_crackle",
    ],
    "effect": [
        "explosion_boom", "punch_hit", "sword_clash", "gunshot",
        "door_creak", "footsteps", "car_engine", "glass_break",
        "scream_horror", "laugh_evil", "laugh_crowd", "cry_soft",
        "heartbeat_fast", "thunder_crack", "magic_spell", "dragon_roar",
        "police_siren", "alarm_beep", "bell_toll", "wing_flap",
    ],
}


class SoundEffectEngine:
    """音效自动匹配引擎"""
    
    def __init__(self, sfx_dir="./assets/sfx"):
        self.sfx_dir = sfx_dir
        self.sfx_cache = {}
        self._scan_sfx_files()
    
    def _scan_sfx_files(self):
        """扫描音效素材目录"""
        if not os.path.exists(self.sfx_dir):
            os.makedirs(self.sfx_dir, exist_ok=True)
            print(f"[SFX] 音效目录已创建: {self.sfx_dir}")
            print(f"[SFX] 请将音效文件放入目录，文件名格式: rain_ambient.mp3")
            return
        
        for f in os.listdir(self.sfx_dir):
            if f.endswith(('.mp3', '.wav', '.ogg')):
                name = os.path.splitext(f)[0]
                self.sfx_cache[name] = os.path.join(self.sfx_dir, f)
        
        if self.sfx_cache:
            print(f"[SFX] 已加载 {len(self.sfx_cache)} 个音效文件")
        else:
            print(f"[SFX] 音效目录为空: {self.sfx_dir}")
    
    def match_scene_effects(self, visual_desc: str, dialogue: str = "", scene_type: str = "action") -> list:
        """
        根据场景描述自动匹配音效
        返回: [{"name": "rain_ambient", "path": "...", "category": "ambient", "volume": 0.17}, ...]
        """
        text = f"{visual_desc} {dialogue}".lower()
        matched = []
        seen = set()
        
        for keyword, effect_name in SCENE_SOUND_MAP.items():
            if keyword in text and effect_name not in seen:
                seen.add(effect_name)
                
                # 判断类别
                category = "effect"
                for cat, effects in EFFECT_CATEGORIES.items():
                    if effect_name in effects:
                        category = cat
                        break
                
                # 查找实际文件
                path = self.sfx_cache.get(effect_name)
                
                matched.append({
                    "name": effect_name,
                    "path": path,  # None = 文件不存在
                    "category": category,
                    "volume": VOLUME_LAYERS.get(category, 0.3),
                    "available": path is not None,
                })
        
        return matched
    
    def get_volume_for_layer(self, layer: str) -> float:
        """获取某层音量"""
        return VOLUME_LAYERS.get(layer, 0.3)
    
    def list_available_effects(self) -> list:
        """列出所有可用音效"""
        return list(self.sfx_cache.keys())
    
    def get_missing_effects(self, scenes: list) -> list:
        """分析场景列表，返回缺失的音效文件名"""
        needed = set()
        for scene in scenes:
            desc = scene.get("visual_description_en", "") + " " + scene.get("dialogue", "")
            matches = self.match_scene_effects(desc)
            for m in matches:
                if not m["available"]:
                    needed.add(m["name"])
        return sorted(needed)


if __name__ == "__main__":
    engine = SoundEffectEngine()
    
    # 测试
    test_scenes = [
        "A dark rainy night, the detective walks alone on the street",
        "暴风雨中，龙从天空俯冲而下，翅膀展开发出巨响",
        "Two warriors clash swords in the forest",
        "她在城市街道上哭泣，远处传来警笛声",
    ]
    
    for desc in test_scenes:
        effects = engine.match_scene_effects(desc)
        print(f"\n场景: {desc[:30]}...")
        for e in effects:
            status = "✅" if e["available"] else "❌缺失"
            print(f"  {status} {e['name']} ({e['category']}, vol={e['volume']})")
