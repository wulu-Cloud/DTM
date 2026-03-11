# adapters/animatediff_video_adapter.py
# 基于 Forge img2img API 逐帧生成 + FFmpeg 合成视频
# 不依赖任何 AnimateDiff 扩展，只需要 Forge 能跑即可

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import base64
import time
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from model_registry import BaseVideoEngine, ModelCapability
from typing import Optional, List


class AnimateDiffVideoEngine(BaseVideoEngine):
    """视频引擎 - 基于 Forge img2img 逐帧生成 + FFmpeg 合成"""

    def __init__(self, config=None):
        self.base_url = "http://127.0.0.1:7860"
        self.reference_image_b64 = None
        self.ffmpeg_path = self._find_ffmpeg()
        print(f"[VideoEngine] 初始化完成，Forge API: {self.base_url}")
        print(f"[VideoEngine] FFmpeg: {self.ffmpeg_path}")

    def _find_ffmpeg(self) -> str:
        """查找 FFmpeg"""
        forge_ffmpeg = r"D:\stable-diffusion-webui-forge\ffmpeg.exe"
        if os.path.exists(forge_ffmpeg):
            return forge_ffmpeg
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        for p in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Users\五路\ffmpeg\bin\ffmpeg.exe"]:
            if os.path.exists(p):
                return p
        return "ffmpeg"

    def get_name(self) -> str:
        return "SD-Forge-Video"

    def get_capability(self) -> ModelCapability:
        return ModelCapability(
            max_reference_images=1,
            supports_prompt=True,
            supports_first_last_frame=True,
            supported_resolutions=["512x512", "576x1024", "768x768"],
            supported_durations=[2, 3, 4, 5],
            notes="Forge img2img 逐帧生成 + FFmpeg 合成，替代 AnimateDiff"
        )

    def test_connection(self) -> bool:
        """测试 Forge 连接"""
        try:
            r = requests.get(f"{self.base_url}/sdapi/v1/sd-models", timeout=10)
            if r.status_code == 200:
                models = r.json()
                print(f"[VideoEngine] Forge 连接成功，模型数: {len(models)}")
                return True
        except Exception as e:
            print(f"[VideoEngine] Forge 连接失败: {e}")
        return False

    def set_reference_image(self, image_path: str):
        """设置参考图"""
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                self.reference_image_b64 = base64.b64encode(f.read()).decode()
            print(f"[VideoEngine] 参考图已设置: {image_path}")
        else:
            print(f"[VideoEngine] 参考图路径无效: {image_path}")

    def _txt2img(self, prompt: str, negative_prompt: str = "", width: int = 512, height: int = 512, seed: int = -1) -> Optional[str]:
        """txt2img 生成首帧，返回 base64 图片"""
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt or "worst quality, low quality, blurry, deformed",
            "steps": 20,
            "cfg_scale": 7,
            "width": width,
            "height": height,
            "seed": seed,
            "sampler_name": "Euler a",
        }

        # 如果有参考图，加 IPAdapter
        if self.reference_image_b64:
            payload["alwayson_scripts"] = {
                "IP Adapter": {
                    "args": [
                        True,                          # enabled
                        self.reference_image_b64,      # image
                        "",                            # model (auto)
                        1.0,                           # weight
                        "ip-adapter_sd15",             # adapter type
                    ]
                }
            }

        try:
            r = requests.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload, timeout=120)
            if r.status_code == 200:
                data = r.json()
                if data.get("images"):
                    return data["images"][0]
        except Exception as e:
            print(f"[VideoEngine] txt2img 失败: {e}")
        return None

    def _img2img(self, init_image_b64: str, prompt: str, negative_prompt: str = "",
                 width: int = 512, height: int = 512, denoising: float = 0.35, seed: int = -1) -> Optional[str]:
        """img2img 生成下一帧"""
        payload = {
            "init_images": [init_image_b64],
            "prompt": prompt,
            "negative_prompt": negative_prompt or "worst quality, low quality, blurry, deformed",
            "steps": 20,
            "cfg_scale": 7,
            "width": width,
            "height": height,
            "denoising_strength": denoising,
            "seed": seed,
            "sampler_name": "Euler a",
        }

        if self.reference_image_b64:
            payload["alwayson_scripts"] = {
                "IP Adapter": {
                    "args": [
                        True,
                        self.reference_image_b64,
                        "",
                        0.6,  # img2img 时参考图权重降低
                        "ip-adapter_sd15",
                    ]
                }
            }

        try:
            r = requests.post(f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=120)
            if r.status_code == 200:
                data = r.json()
                if data.get("images"):
                    return data["images"][0]
        except Exception as e:
            print(f"[VideoEngine] img2img 失败: {e}")
        return None

    def _frames_to_video(self, frame_dir: str, output_path: str, fps: int = 8) -> bool:
        """FFmpeg 将帧图片合成视频"""
        pattern = os.path.join(frame_dir, "frame_%04d.png")
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-framerate", str(fps),
            "-i", pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-preset", "fast",
            output_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"[VideoEngine] 视频合成成功: {output_path}")
                return True
            else:
                print(f"[VideoEngine] FFmpeg 错误: {result.stderr[:500]}")
        except Exception as e:
            print(f"[VideoEngine] FFmpeg 执行失败: {e}")
        return False

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 3, resolution: str = "512x512",
                       negative_prompt: str = "", seed: int = -1,
                       first_frame_image: str = None,
                       last_frame_image: str = None,
                       reference_image: str = None,
                       **kwargs) -> Optional[str]:
        """
        生成视频 - 主入口
        
        参数与原 AnimateDiff adapter 完全兼容:
        - prompt: 正向提示词
        - output_path: 输出视频路径
        - duration: 视频时长(秒)
        - resolution: 分辨率 如 "512x512"
        - negative_prompt: 负向提示词
        - seed: 随机种子
        - first_frame_image: 首帧图片路径
        - last_frame_image: 末帧图片路径(用于插值)
        - reference_image: IPAdapter参考图路径
        """
        print(f"[VideoEngine] 开始生成视频")
        print(f"  Prompt: {prompt[:80]}...")
        print(f"  Duration: {duration}s, Resolution: {resolution}")

        # 解析分辨率
        try:
            w, h = resolution.split("x")
            width, height = int(w), int(h)
        except:
            width, height = 512, 512

        # 设置参考图
        if reference_image:
            self.set_reference_image(reference_image)

        # 帧数和FPS
        fps = 8
        total_frames = duration * fps

        # 创建临时目录存帧
        frame_dir = tempfile.mkdtemp(prefix="forge_video_")
        print(f"[VideoEngine] 帧目录: {frame_dir}")

        frames_b64 = []

        # === 第1帧 ===
        if first_frame_image and os.path.exists(first_frame_image):
            # 有首帧图片，用 img2img 轻微调整
            with open(first_frame_image, "rb") as f:
                first_b64 = base64.b64encode(f.read()).decode()
            frame = self._img2img(first_b64, prompt, negative_prompt, width, height, denoising=0.15, seed=seed)
            if not frame:
                frame = first_b64
        else:
            # 没有首帧，用 txt2img 生成
            frame = self._txt2img(prompt, negative_prompt, width, height, seed=seed)

        if not frame:
            print("[VideoEngine] 首帧生成失败")
            return None

        frames_b64.append(frame)
        # 保存首帧
        frame_path = os.path.join(frame_dir, "frame_0000.png")
        with open(frame_path, "wb") as f:
            f.write(base64.b64decode(frame))
        print(f"[VideoEngine] 首帧生成完成")

        # === 末帧(如果有) ===
        last_b64 = None
        if last_frame_image and os.path.exists(last_frame_image):
            with open(last_frame_image, "rb") as f:
                last_b64 = base64.b64encode(f.read()).decode()

        # === 中间帧：逐帧 img2img ===
        for i in range(1, total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0

            # denoising 从小到大渐变，让画面慢慢变化
            if last_b64:
                denoising = 0.10 + 0.08 * abs(progress - 0.5) * 2
                if progress > 0.5:
                    prev_frame = last_b64
                    denoising = 0.18 - 0.08 * (progress - 0.5) * 2
                else:
                    prev_frame = frames_b64[-1]

            else:
                # 无末帧：极低 denoising 保持一致性
                denoising = 0.08 + 0.07 * progress
                prev_frame = frames_b64[-1]


            # 微调 seed 让每帧略有不同
            frame_seed = (seed + i * 7) if seed > 0 else -1

            frame = self._img2img(prev_frame, prompt, negative_prompt, width, height,
                                  denoising=denoising, seed=frame_seed)

            if not frame:
                print(f"[VideoEngine] 第{i}帧失败，复用上一帧")
                frame = frames_b64[-1]

            frames_b64.append(frame)

            # 保存帧
            frame_path = os.path.join(frame_dir, f"frame_{i:04d}.png")
            with open(frame_path, "wb") as f:
                f.write(base64.b64decode(frame))

            print(f"[VideoEngine] 帧 {i+1}/{total_frames} 完成 (denoising={denoising:.2f})")

        # === FFmpeg 合成 ===
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        success = self._frames_to_video(frame_dir, output_path, fps=fps)

        # 清理临时帧
        try:
            shutil.rmtree(frame_dir)
        except:
            pass

        if success and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / 1024
            print(f"[VideoEngine] 视频生成完成: {output_path} ({file_size:.1f}KB)")
            return output_path

        print("[VideoEngine] 视频生成失败")
        return None

    def generate_videos_batch(self, tasks: List[dict]) -> List[Optional[str]]:
        """批量生成视频"""
        results = []
        for i, task in enumerate(tasks):
            print(f"\n[VideoEngine] 批量任务 {i+1}/{len(tasks)}")
            result = self.generate_video(**task)
            results.append(result)
        return results
    def batch_generate_videos(self, tasks: List[dict]) -> List[Optional[str]]:
        """批量生成视频（抽象方法实现）"""
        return self.generate_videos_batch(tasks)

    def image_to_video(self, image_path: str, prompt: str, output_path: str,
                       duration: int = 3, resolution: str = "512x512",
                       negative_prompt: str = "", seed: int = -1, **kwargs) -> Optional[str]:
        """图片转视频"""
        return self.generate_video(
            prompt=prompt, output_path=output_path,
            duration=duration, resolution=resolution,
            negative_prompt=negative_prompt, seed=seed,
            first_frame_image=image_path, **kwargs
        )

    def text_to_video(self, prompt: str, output_path: str,
                      duration: int = 3, resolution: str = "512x512",
                      negative_prompt: str = "", seed: int = -1, **kwargs) -> Optional[str]:
        """文字转视频"""
        return self.generate_video(
            prompt=prompt, output_path=output_path,
            duration=duration, resolution=resolution,
            negative_prompt=negative_prompt, seed=seed, **kwargs
        )

    def first_last_frame_to_video(self, first_frame: str, last_frame: str,
                                   prompt: str, output_path: str,
                                   duration: int = 3, resolution: str = "512x512",
                                   negative_prompt: str = "", seed: int = -1, **kwargs) -> Optional[str]:
        """首尾帧转视频"""
        return self.generate_video(
            prompt=prompt, output_path=output_path,
            duration=duration, resolution=resolution,
            negative_prompt=negative_prompt, seed=seed,
            first_frame_image=first_frame, last_frame_image=last_frame, **kwargs
        )
