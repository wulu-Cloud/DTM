# adapters/animatediff_video_adapter.py
# 把 Forge/WebUI 的 AnimateDiff 扩展包装为 BaseVideoEngine

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import base64
import time
import json
from pathlib import Path
from model_registry import BaseVideoEngine, ModelCapability
from typing import Optional, List


class AnimateDiffVideoEngine(BaseVideoEngine):
    """AnimateDiff 视频引擎适配器 - 通过 SD WebUI/Forge API"""

    def __init__(self, config=None):
        self.base_url = "http://127.0.0.1:7860"
        self.reference_image_b64 = None
        print(f"[AnimateDiff] 初始化完成，API: {self.base_url}")

    def get_name(self) -> str:
        return "AnimateDiff-Forge"

    def get_capability(self) -> ModelCapability:
        return ModelCapability(
            max_reference_images=1,
            supports_prompt=True,
            supports_first_last_frame=False,  # AnimateDiff不支持首尾帧
            supported_resolutions=["512x512", "576x1024", "768x768"],
            supported_durations=[2, 3, 4],
            notes="AnimateDiff 本地生成，通过Forge API，支持IPAdapter参考图"
        )

    def set_reference_image(self, image_path: str):
        """设置IPAdapter参考图"""
        with open(image_path, "rb") as f:
            self.reference_image_b64 = base64.b64encode(f.read()).decode("utf-8")
        print(f"[AnimateDiff] 参考图已设置: {image_path}")

    def clear_reference_image(self):
        self.reference_image_b64 = None
        print("[AnimateDiff] 已清除参考图")

    def image_to_video(self, image_path: str, save_path: str,
                       duration: int = 3, prompt: str = "",
                       reference_image_paths: Optional[List[str]] = None,
                       reference_video_path: Optional[str] = None,
                       **kwargs) -> Optional[str]:
        """单图生视频 - 用img2img + AnimateDiff"""
        # 读取输入图片
        with open(image_path, "rb") as f:
            init_image_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 如果传了参考图，设置IPAdapter
        if reference_image_paths and len(reference_image_paths) > 0:
            self.set_reference_image(reference_image_paths[0])

        negative_prompt = kwargs.get("negative_prompt",
            "nsfw, lowres, bad anatomy, bad hands, text, error, "
            "missing fingers, extra digit, fewer digits, cropped, "
            "worst quality, low quality, normal quality, jpeg artifacts, "
            "signature, watermark, username, blurry")

        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        steps = kwargs.get("steps", 20)
        cfg_scale = kwargs.get("cfg_scale", 7)
        denoising_strength = kwargs.get("denoising_strength", 0.35)
        fps = kwargs.get("fps", 8)
        frames = duration * fps  # 比如3秒 * 8fps = 24帧

        payload = {
            "init_images": [init_image_b64],
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "denoising_strength": denoising_strength,
            "sampler_name": "Euler a",
            "batch_size": 1,
            "alwayson_scripts": {
                "AnimateDiff": {
                    "args": [{
                        "enable": True,
                        "model": "mm_sd15_v3.safetensors",
                        "video_length": frames,
                        "fps": fps,
                        "loop_number": 0,
                        "closed_loop": "N",
                        "save_format": ["MP4"],
                        "interp": "Off",
                        "interp_x": 10,
                        "video_source": None,
                        "video_path": "",
                        "latent_power": 1,
                        "latent_scale": 32,
                        "last_frame": None,
                        "latent_power_last": 1,
                        "latent_scale_last": 32,
                    }]
                }
            }
        }

        # 加IPAdapter
        if self.reference_image_b64:
            payload["alwayson_scripts"]["controlNet"] = {
                "args": [{
                    "enabled": True,
                    "module": "InsightFace+CLIP-H (IPAdapter)",
                    "model": "ip-adapter-plus-face_sd15 [7f7a633a]",
                    "weight": kwargs.get("ip_weight", 0.7),
                    "resize_mode": "Crop and Resize",
                    "pixel_perfect": True,
                    "guidance_start": 0.0,
                    "guidance_end": 1.0,
                    "image": {
                        "image": self.reference_image_b64,
                        "mask": None
                    }
                }]
            }

        try:
            print(f"[AnimateDiff] img2video 开始生成... {frames}帧 {fps}fps")
            print(f"[AnimateDiff] Prompt: {prompt[:80]}...")

            response = requests.post(
                f"{self.base_url}/sdapi/v1/img2img",
                json=payload,
                timeout=600
            )
            response.raise_for_status()
            result = response.json()

            # AnimateDiff 生成的视频在 info 里或者直接保存到 outputs 目录
            # 先尝试从返回的 images 里找视频
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            # 方法1：检查Forge outputs目录找最新mp4
            video_path = self._find_latest_video(save_path)
            if video_path:
                return video_path

            # 方法2：如果返回了图片帧，用ffmpeg合成
            if "images" in result and len(result["images"]) > 0:
                print(f"[AnimateDiff] 返回了 {len(result['images'])} 张图片/帧")
                # 第一张可能是视频的base64
                return self._save_video_from_response(result, save_path)

            print("[AnimateDiff] ⚠ 未找到生成的视频")
            return None

        except requests.exceptions.ConnectionError:
            print("[AnimateDiff] ❌ 连接失败！请确认Forge WebUI已启动")
            return None
        except Exception as e:
            print(f"[AnimateDiff] ❌ 生成失败: {e}")
            return None

    def first_last_frame_to_video(self, first_image_path: str,
                                   last_image_path: str,
                                   save_path: str,
                                   duration: int = 3,
                                   prompt: str = "",
                                   reference_image_paths: Optional[List[str]] = None,
                                   **kwargs) -> Optional[str]:
        """首尾帧生视频 - AnimateDiff不原生支持，退化为单图生视频"""
        print("[AnimateDiff] ⚠ 不支持首尾帧模式，使用首帧生成")
        return self.image_to_video(first_image_path, save_path,
                                    duration=duration, prompt=prompt,
                                    reference_image_paths=reference_image_paths,
                                    **kwargs)

    def text_to_video(self, prompt: str, save_path: str,
                      duration: int = 3,
                      reference_image_paths: Optional[List[str]] = None,
                      **kwargs) -> Optional[str]:
        """纯文本生视频 - txt2img + AnimateDiff"""
        negative_prompt = kwargs.get("negative_prompt",
            "nsfw, lowres, bad anatomy, bad hands, text, error, "
            "worst quality, low quality, jpeg artifacts, blurry")

        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        fps = kwargs.get("fps", 8)
        frames = duration * fps

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": kwargs.get("steps", 20),
            "cfg_scale": kwargs.get("cfg_scale", 7),
            "sampler_name": "Euler a",
            "batch_size": 1,
            "alwayson_scripts": {
                "AnimateDiff": {
                    "args": [{
                        "enable": True,
                        "model": "mm_sd15_v3.safetensors",
                        "video_length": frames,
                        "fps": fps,
                        "loop_number": 0,
                        "closed_loop": "N",
                        "save_format": ["MP4"],
                    }]
                }
            }
        }

        # 加IPAdapter
        if self.reference_image_b64:
            payload["alwayson_scripts"]["controlNet"] = {
                "args": [{
                    "enabled": True,
                    "module": "InsightFace+CLIP-H (IPAdapter)",
                    "model": "ip-adapter-plus-face_sd15 [7f7a633a]",
                    "weight": kwargs.get("ip_weight", 0.7),
                    "resize_mode": "Crop and Resize",
                    "pixel_perfect": True,
                    "image": {
                        "image": self.reference_image_b64,
                        "mask": None
                    }
                }]
            }

        try:
            print(f"[AnimateDiff] txt2video 开始生成... {frames}帧")
            response = requests.post(
                f"{self.base_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=600
            )
            response.raise_for_status()
            result = response.json()

            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            video_path = self._find_latest_video(save_path)
            if video_path:
                return video_path

            if "images" in result:
                return self._save_video_from_response(result, save_path)

            return None

        except Exception as e:
            print(f"[AnimateDiff] ❌ 生成失败: {e}")
            return None

    def batch_generate_videos(self, tasks: List[dict],
                              episode_num: int) -> List[Optional[str]]:
        """批量生成视频"""
        results = []
        for i, task in enumerate(tasks):
            first_frame = task.get("first_frame")
            last_frame = task.get("last_frame")
            prompt = task.get("prompt", "")
            save_path = task.get("save_path", f"output/ep{episode_num}/video_{i+1}.mp4")
            duration = task.get("duration", 3)

            try:
                result = self.image_to_video(
                    first_frame, save_path,
                    duration=duration, prompt=prompt
                )
                results.append(result)
            except Exception as e:
                print(f"  ❌ 视频 {i+1} 生成失败: {e}")
                results.append(None)

        return results

    def _find_latest_video(self, target_save_path: str) -> Optional[str]:
        """从Forge的outputs目录找最新生成的mp4并移到目标路径"""
        import glob
        import shutil

        # Forge 通常保存到 outputs/img2img-images/AnimateDiff/ 或 outputs/txt2img-images/AnimateDiff/
        possible_dirs = [
            os.path.join(os.path.dirname(self.base_url.replace("http://", "")), "outputs"),
            r"D:\stable-diffusion-webui-forge\outputs\img2img-images\AnimateDiff",
            r"D:\stable-diffusion-webui-forge\outputs\txt2img-images\AnimateDiff",
            # 添加更多可能的路径
        ]

        # 等待一下让文件写入完成
        time.sleep(2)

        for search_dir in possible_dirs:
            if not os.path.isdir(search_dir):
                continue
            mp4_files = glob.glob(os.path.join(search_dir, "**", "*.mp4"), recursive=True)
            if mp4_files:
                latest = max(mp4_files, key=os.path.getmtime)
                # 检查是不是最近30秒内的
                if time.time() - os.path.getmtime(latest) < 30:
                    save_dir = os.path.dirname(target_save_path)
                    if save_dir:
                        os.makedirs(save_dir, exist_ok=True)
                    shutil.copy2(latest, target_save_path)
                    print(f"[AnimateDiff] ✅ 视频已保存: {target_save_path}")
                    return target_save_path

        return None

    def _save_video_from_response(self, result: dict, save_path: str) -> Optional[str]:
        """从API响应中提取视频"""
        try:
            # AnimateDiff可能直接返回视频的base64
            images = result.get("images", [])
            if not images:
                return None

            # 尝试解码第一个为视频
            data = base64.b64decode(images[0])

            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            # 检查是否是mp4格式（mp4文件头）
            if data[:4] == b'\x00\x00\x00' or data[:3] == b'fty':
                with open(save_path, "wb") as f:
                    f.write(data)
                print(f"[AnimateDiff] ✅ 视频已保存: {save_path}")
                return save_path

            # 如果是图片帧，保存为gif或单帧
            print("[AnimateDiff] 返回的是图片帧，非视频文件")
            # 保存第一帧作为预览
            preview_path = save_path.replace(".mp4", "_preview.png")
            with open(preview_path, "wb") as f:
                f.write(data)
            return None

        except Exception as e:
            print(f"[AnimateDiff] 解析响应失败: {e}")
            return None

    def test_connection(self) -> bool:
        """测试Forge连接"""
        try:
            response = requests.get(f"{self.base_url}/sdapi/v1/sd-models", timeout=5)
            if response.status_code == 200:
                print("[AnimateDiff] ✅ Forge连接正常")
                return True
        except:
            pass
        print("[AnimateDiff] ❌ 无法连接Forge WebUI")
        return False
