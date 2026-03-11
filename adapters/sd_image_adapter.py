# adapters/sd_image_adapter.py

import requests
import base64
import os
from pathlib import Path


class SDImageEngine:
    def __init__(self, config=None):
        self.base_url = "http://127.0.0.1:7860"
        self.default_model = "anyloraCheckpoint_bakedvaeBlessedFp16.safetensors"
        self.reference_image_b64 = None
        print(f"[SDImageEngine] 初始化完成, 目标: {self.base_url}")

    def set_reference_image(self, image_path: str):
        """设置参考图片, 后续生成会用IP-Adapter保持人物一致性"""
        with open(image_path, "rb") as f:
            self.reference_image_b64 = base64.b64encode(f.read()).decode("utf-8")
        print(f"[SDImageEngine] 已设置参考图: {image_path}")

    def clear_reference_image(self):
        """清除参考图"""
        self.reference_image_b64 = None
        print("[SDImageEngine] 已清除参考图")

    def generate_image(self, prompt: str, save_path: str, **kwargs) -> dict:
        """
        调用本地SD WebUI生成图片, 如果有参考图则自动启用IP-Adapter
        """
        negative_prompt = kwargs.get("negative_prompt",
            "nsfw, lowres, bad anatomy, bad hands, text, error, "
            "missing fingers, extra digit, fewer digits, cropped, "
            "worst quality, low quality, normal quality, jpeg artifacts, "
            "signature, watermark, username, blurry"
        )

        width = kwargs.get("width", 576)
        height = kwargs.get("height", 1024)
        steps = kwargs.get("steps", 25)
        cfg_scale = kwargs.get("cfg_scale", 7)
        sampler = kwargs.get("sampler", "Euler a")
        ip_weight = kwargs.get("ip_weight", 0.7)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler,
            "batch_size": 1,
        }

        # 如果有参考图, 加IP-Adapter保持人物一致性
        if self.reference_image_b64:
            payload["alwayson_scripts"] = {
                "controlnet": {
                    "args": [
                        {
                            "enabled": True,
                            "module": "InsightFace+CLIP-H (IPAdapter)",
                            "model": "ip-adapter-plus-face_sd15 [7f7a633a]",
                            "weight": ip_weight,
                            "resize_mode": "Crop and Resize",
                            "pixel_perfect": True,
                            "guidance_start": 0.0,
                            "guidance_end": 1.0,
                            "image": {
                                "image": self.reference_image_b64,
                                "mask": None
                            },
                        }
                    ]
                }
            }

            print(f"[SDImageEngine] IP-Adapter已启用, weight={ip_weight}")

        try:
            print(f"[SDImageEngine] 开始生成图片...")
            print(f"[SDImageEngine] Prompt: {prompt[:80]}...")

            response = requests.post(
                f"{self.base_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()

            image_data = base64.b64decode(result["images"][0])

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "wb") as f:
                f.write(image_data)

            print(f"[SDImageEngine] 图片保存成功: {save_path}")
            return {"success": True, "path": save_path}

        except requests.exceptions.ConnectionError:
            print(f"[SDImageEngine] 连接失败! 请确认SD WebUI正在运行")
            return {"success": False, "error": "连接失败"}
        except Exception as e:
            print(f"[SDImageEngine] 生成失败: {e}")
            return {"success": False, "error": str(e)}

    def generate_character_sheet(self, prompt: str, save_path: str, **kwargs) -> dict:
        """生成角色定妆照并自动设为参考图"""
        char_prompt = f"(masterpiece, best quality), solo, front view, simple background, white background, full body, {prompt}"
        result = self.generate_image(char_prompt, save_path, **kwargs)
        if result["success"]:
            self.set_reference_image(save_path)
            print(f"[SDImageEngine] 角色定妆照已生成并设为参考图")
        return result

    def test_connection(self) -> bool:
        """测试SD WebUI是否在线"""
        try:
            response = requests.get(f"{self.base_url}/sdapi/v1/sd-models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                print(f"[SDImageEngine] 连接成功, 可用模型数: {len(models)}")
                return True
        except:
            print(f"[SDImageEngine] 无法连接到SD WebUI")
            return False
