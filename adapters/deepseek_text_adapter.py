# ============================================================
# adapters/deepseek_text_adapter.py
# 把现有 deepseek_engine.py 包装为 BaseTextEngine（备用）
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_registry import BaseTextEngine
from typing import Optional


class DeepSeekTextEngine(BaseTextEngine):
    """DeepSeek 文本引擎适配器（备用）"""

    def __init__(self):
        from deepseek_engine import DeepSeekEngine
        self._engine = DeepSeekEngine()
        print(f"[DeepSeekTextAdapter] 初始化完成")

    def get_name(self) -> str:
        return "DeepSeek"

    def detect_genre(self, text_sample: str) -> str:
        return self._engine.detect_genre(text_sample)

    def extract_characters(self, episode_text: str,
                           existing_characters: str = "",
                           episode_num: int = 1) -> list:
        return self._engine.extract_characters(episode_text,
                                                existing_characters,
                                                episode_num)

    def generate_storyboard(self, episode_text: str,
                            characters_summary: str = "",
                            style: str = "动漫风",
                            episode_num: int = 1,
                            target_duration: int = 90) -> dict:
        return self._engine.generate_storyboard(episode_text,
                                                 characters_summary,
                                                 style,
                                                 episode_num,
                                                 target_duration)

    def translate_cn_to_en(self, chinese_text: str) -> Optional[str]:
        if hasattr(self._engine, 'translate_cn_to_en'):
            return self._engine.translate_cn_to_en(chinese_text)
        return None

    def translate_en_to_cn(self, english_text: str) -> Optional[str]:
        if hasattr(self._engine, 'translate_en_to_cn'):
            return self._engine.translate_en_to_cn(english_text)
        return None

    def generate_video_prompts(self, script: dict) -> list:
        if hasattr(self._engine, 'generate_video_prompts'):
            return self._engine.generate_video_prompts(script)
        # 回退：返回空prompt列表
        scenes = script.get("scenes", [])
        return ["" for _ in scenes]

    def generate_single_video_prompt(self, scene: dict) -> str:
        if hasattr(self._engine, 'generate_single_video_prompt'):
            return self._engine.generate_single_video_prompt(scene)
        return ""
