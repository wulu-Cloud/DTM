# ============================================================
# adapters/gemini_text_adapter.py
# 把现有 gemini_engine.py 包装为 BaseTextEngine
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_registry import BaseTextEngine
from typing import Optional


class GeminiTextEngine(BaseTextEngine):
    """Gemini 文本引擎适配器 - 委托给现有 gemini_engine.GeminiEngine"""

    def __init__(self):
        from gemini_engine import GeminiEngine
        self._engine = GeminiEngine()
        print(f"[GeminiTextAdapter] 初始化完成，委托给 GeminiEngine")

    def get_name(self) -> str:
        return "Gemini-2.5-Flash"

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
        return self._engine.translate_cn_to_en(chinese_text)

    def translate_en_to_cn(self, english_text: str) -> Optional[str]:
        return self._engine.translate_en_to_cn(english_text)

    def generate_video_prompts(self, script: dict) -> list:
        return self._engine.generate_video_prompts(script)

    def generate_single_video_prompt(self, scene: dict) -> str:
        return self._engine.generate_single_video_prompt(scene)

    def set_character_profiles(self, characters: list):
        if hasattr(self._engine, 'character_profiles'):
            self._engine.character_profiles = characters

    def set_outfit_dna_cache(self, outfit_dna: dict):
        if hasattr(self._engine, 'outfit_dna_cache'):
            self._engine.outfit_dna_cache = outfit_dna
