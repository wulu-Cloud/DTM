# ============================================================
# adapters/jimeng_video_adapter.py
# 把现有 jimeng_api.py 包装为 BaseVideoEngine
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_registry import BaseVideoEngine, ModelCapability
from typing import Optional, List


class JimengVideoEngine(BaseVideoEngine):
    """即梦视频引擎适配器"""

    def __init__(self):
        from jimeng_api import JimengVideoAPI
        self._api = JimengVideoAPI()
        print(f"[JimengVideoAdapter] 初始化完成")

    def get_name(self) -> str:
        return "Jimeng-V3-Pro"

    def get_capability(self) -> ModelCapability:
        return ModelCapability(
            max_reference_images=1,     # 单图模式：1张主图
            supports_prompt=True,        # 支持场景描述prompt
            supports_first_last_frame=True,  # 支持首尾帧模式
            supported_resolutions=["1080x1920"],
            supported_durations=[5],
            notes="即梦API v2.1: 单图→视频 / 首尾帧→视频，均支持prompt"
        )

    def image_to_video(self, image_path: str, save_path: str,
                       duration: int = 5, prompt: str = "",
                       reference_image_paths: Optional[List[str]] = None,
                       reference_video_path: Optional[str] = None,
                       **kwargs) -> Optional[str]:
        """单图→视频"""
        return self._api.image_to_video(image_path, save_path,
                                         duration=duration, prompt=prompt)

    def first_last_frame_to_video(self, first_image_path: str,
                                  last_image_path: str,
                                  save_path: str,
                                  duration: int = 5,
                                  prompt: str = "",
                                  reference_image_paths: Optional[List[str]] = None,
                                  **kwargs) -> Optional[str]:
        """首尾帧→视频"""
        return self._api.first_last_frame_to_video(
            first_image_path, last_image_path,
            save_path, duration=duration, prompt=prompt
        )

    def batch_generate_videos(self, tasks: List[dict],
                              episode_num: int) -> List[Optional[str]]:
        """批量生成视频
        
        tasks格式: [{"first_frame": path, "last_frame": path|None, 
                     "prompt": str, "save_path": str}, ...]
        """
        results = []
        for i, task in enumerate(tasks):
            first_frame = task.get("first_frame")
            last_frame = task.get("last_frame")
            prompt = task.get("prompt", "")
            save_path = task.get("save_path", f"output/ep{episode_num}/video_{i+1}.mp4")
            duration = task.get("duration", 5)

            try:
                if last_frame:
                    result = self.first_last_frame_to_video(
                        first_frame, last_frame, save_path,
                        duration=duration, prompt=prompt
                    )
                else:
                    result = self.image_to_video(
                        first_frame, save_path,
                        duration=duration, prompt=prompt
                    )
                results.append(result)
            except Exception as e:
                print(f"  ❌ 视频 {i+1} 生成失败: {e}")
                results.append(None)

        return results

    # 兼容旧接口：直接暴露底层API的批量方法
    def batch_generate_videos_legacy(self, image_paths, episode_num,
                                     scene_prompts=None):
        """兼容旧 batch_generate_videos 调用"""
        return self._api.batch_generate_videos(image_paths, episode_num,
                                                scene_prompts)

    def batch_generate_videos_with_frames_legacy(self, first_last_pairs,
                                                  episode_num,
                                                  scene_prompts=None):
        """兼容旧 batch_generate_videos_with_frames 调用"""
        return self._api.batch_generate_videos_with_frames(
            first_last_pairs, episode_num, scene_prompts
        )

    def batch_generate_videos_with_frames(self, first_last_pairs, episode_num,
                                          scene_prompts=None):
        """批量生成视频 - 首尾帧模式（兼容gui.py直接调用）"""
        return self._api.batch_generate_videos_with_frames(
            first_last_pairs, episode_num, scene_prompts
        )
