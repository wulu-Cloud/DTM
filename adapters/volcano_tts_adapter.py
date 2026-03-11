# ============================================================
# adapters/volcano_tts_adapter.py
# 把现有 tts_engine.py 包装为 BaseTTSEngine
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_registry import BaseTTSEngine
from typing import List


class VolcanoTTSEngine(BaseTTSEngine):
    """火山TTS引擎适配器"""

    def __init__(self):
        from tts_engine import TTSEngine
        self._engine = TTSEngine()
        print(f"[VolcanoTTSAdapter] 初始化完成")

    def get_name(self) -> str:
        return "Volcano-TTS"

    def synthesize(self, text: str, output_path: str,
                   voice_name: str = "", emotion: str = "",
                   speed: float = 1.0, volume: float = 1.0,
                   **kwargs) -> dict:
        """合成语音"""
        # 传递voice_type（火山TTS的音色参数）
        voice_type = voice_name or kwargs.get("voice_type", "")
        return self._engine.synthesize(
            text, output_path,
            voice_type=voice_type,
            emotion=emotion,
            speed_ratio=speed
        )

    def generate_silence(self, duration: float, output_path: str) -> dict:
        """生成静音"""
        return self._engine.generate_silence(duration, output_path)

    def get_voice_options(self) -> List[str]:
        """返回可选音色"""
        if hasattr(self._engine, 'get_voice_options'):
            return self._engine.get_voice_options()
        return []
