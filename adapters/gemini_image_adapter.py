# ============================================================
# adapters/gemini_image_adapter.py
# 把现有 gemini_engine.py 的图片生成包装为 BaseImageEngine
# ============================================================

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_registry import BaseImageEngine, ModelCapability
from typing import Optional, List


class GeminiImageEngine(BaseImageEngine):
    """Gemini NanoBananaPro 图片引擎适配器"""

    def __init__(self):
        from gemini_engine import GeminiEngine
        self._engine = GeminiEngine()
        print(f"[GeminiImageAdapter] 初始化完成，使用 NanoBananaPro2")

    def get_name(self) -> str:
        return "Gemini-NanoBananaPro2"

    def get_capability(self) -> ModelCapability:
        return ModelCapability(
            max_reference_images=0,  # 当前Gemini图片生成不支持参考图输入
            supports_prompt=True,
            supports_style_reference=False,
            supported_resolutions=["1024x1024", "1080x1920", "1920x1080"],
            notes="Gemini原生图片生成，通过prompt控制风格和内容"
        )

    def generate_image(self, prompt: str, save_path: str,
                       style_prefix: str = "",
                       reference_image_paths: Optional[List[str]] = None,
                       **kwargs) -> Optional[str]:
        """生成单张图片"""
        full_prompt = f"{style_prefix} {prompt}".strip() if style_prefix else prompt
        return self._engine.generate_image(full_prompt, save_path)

    def generate_image_candidates(self, prompt: str, save_dir: str,
                                  base_name: str, count: int = 3,
                                  style_prefix: str = "",
                                  reference_image_paths: Optional[List[str]] = None,
                                  **kwargs) -> List[str]:
        """生成多张候选图 - 委托给现有方法"""
        full_prompt = f"{style_prefix} {prompt}".strip() if style_prefix else prompt
        # 使用现有的 generate_image_candidates
        if hasattr(self._engine, 'generate_image_candidates'):
            return self._engine.generate_image_candidates(
                full_prompt, save_dir, base_name, count
            )
        # 回退到逐张生成
        return super().generate_image_candidates(
            prompt, save_dir, base_name, count, style_prefix,
            reference_image_paths, **kwargs
        )

    def generate_next_frame(self, prev_frame_path: str,
                            next_scene_prompt: str,
                            save_path: str,
                            style_prefix: str = "",
                            character_ref_paths: Optional[List[str]] = None,
                            **kwargs) -> Optional[str]:
        """链式帧生成 - Gemini当前不支持参考图，退化为纯prompt"""
        # TODO: 未来Gemini支持图片输入时可增强
        full_prompt = f"{style_prefix} {next_scene_prompt}".strip() if style_prefix else next_scene_prompt
        return self._engine.generate_image(full_prompt, save_path)
