# ============================================================
# model_registry.py - 模型隔离层 + 注册中心 v1.0
# ============================================================
# 所有模型调用必须通过此层，实现一键切换模型
# ============================================================

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class ModelCapability:
    """模型能力描述"""
    max_reference_images: int = 0       # 最多支持多少张参考图
    max_reference_videos: int = 0       # 最多支持多少个参考视频
    supports_prompt: bool = True        # 是否支持文字prompt
    supports_negative_prompt: bool = False
    supports_image_embed: bool = False  # 是否支持图片镶嵌
    supports_first_last_frame: bool = False  # 首尾帧模式
    supports_style_reference: bool = False   # 风格参考
    max_prompt_length: int = 2000
    supported_resolutions: List[str] = field(default_factory=lambda: ["1080x1920"])
    supported_durations: List[int] = field(default_factory=lambda: [5])
    notes: str = ""  # 补充说明


# ============================================================
# 抽象基类：文本引擎
# ============================================================

class BaseTextEngine(ABC):
    """文本分析引擎抽象层 - 分镜/角色提取/翻译/prompt生成"""

    @abstractmethod
    def get_name(self) -> str:
        """引擎名称"""
        pass

    @abstractmethod
    def detect_genre(self, text_sample: str) -> str:
        """检测小说类型"""
        pass

    @abstractmethod
    def extract_characters(self, episode_text: str,
                           existing_characters: str = "",
                           episode_num: int = 1) -> list:
        """提取角色信息"""
        pass

    @abstractmethod
    def generate_storyboard(self, episode_text: str,
                            characters_summary: str = "",
                            style: str = "动漫风",
                            episode_num: int = 1,
                            target_duration: int = 90) -> dict:
        """生成分镜剧本"""
        pass

    @abstractmethod
    def translate_cn_to_en(self, chinese_text: str) -> Optional[str]:
        """中文→英文翻译"""
        pass

    @abstractmethod
    def translate_en_to_cn(self, english_text: str) -> Optional[str]:
        """英文→中文翻译"""
        pass

    @abstractmethod
    def generate_video_prompts(self, script: dict) -> list:
        """为场景生成视频运动prompt"""
        pass

    @abstractmethod
    def generate_single_video_prompt(self, scene: dict) -> str:
        """为单个场景生成视频prompt"""
        pass

    # 可选方法（有默认实现）
    def set_character_profiles(self, characters: list):
        """设置角色外貌缓存"""
        pass

    def set_outfit_dna_cache(self, outfit_dna: dict):
        """设置服装DNA缓存"""
        pass


# ============================================================
# 抽象基类：图片引擎
# ============================================================

class BaseImageEngine(ABC):
    """图片生成引擎抽象层"""

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_capability(self) -> ModelCapability:
        """返回此图片模型的能力"""
        pass

    @abstractmethod
    def generate_image(self, prompt: str, save_path: str,
                       style_prefix: str = "",
                       reference_image_paths: Optional[List[str]] = None,
                       **kwargs) -> Optional[str]:
        """生成单张图片
        
        Args:
            prompt: 图片描述prompt
            save_path: 保存路径（不含扩展名）
            style_prefix: 风格前缀
            reference_image_paths: 参考图路径列表
            
        Returns:
            实际保存路径（含扩展名）或 None
        """
        pass

    def generate_image_candidates(self, prompt: str, save_dir: str,
                                  base_name: str, count: int = 3,
                                  style_prefix: str = "",
                                  reference_image_paths: Optional[List[str]] = None,
                                  **kwargs) -> List[str]:
        """生成多张候选图（默认实现：循环调用generate_image）"""
        import time, os
        candidates = []
        for i in range(count):
            sp = os.path.join(save_dir, f"{base_name}_candidate_{i+1}")
            result = self.generate_image(prompt, sp, style_prefix,
                                         reference_image_paths, **kwargs)
            if result:
                candidates.append(result)
            time.sleep(2)
        return candidates

    def generate_next_frame(self, prev_frame_path: str,
                            next_scene_prompt: str,
                            save_path: str,
                            style_prefix: str = "",
                            character_ref_paths: Optional[List[str]] = None,
                            **kwargs) -> Optional[str]:
        """链式帧生成（基于上一帧+新prompt → 下一帧）
        默认实现：退化为纯prompt生成（不支持链式的模型用此回退）
        """
        return self.generate_image(next_scene_prompt, save_path,
                                   style_prefix, character_ref_paths, **kwargs)


# ============================================================
# 抽象基类：视频引擎
# ============================================================

class BaseVideoEngine(ABC):
    """视频生成引擎抽象层"""

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_capability(self) -> ModelCapability:
        """返回此视频模型的能力"""
        pass

    @abstractmethod
    def image_to_video(self, image_path: str, save_path: str,
                       duration: int = 5, prompt: str = "",
                       reference_image_paths: Optional[List[str]] = None,
                       reference_video_path: Optional[str] = None,
                       **kwargs) -> Optional[str]:
        """单图→视频
        
        Args:
            image_path: 主图路径
            save_path: 视频保存路径
            duration: 时长(秒)
            prompt: 运动描述prompt
            reference_image_paths: 额外参考图列表
            reference_video_path: 参考视频路径
            
        Returns:
            视频保存路径 或 None
        """
        pass

    def first_last_frame_to_video(self, first_image_path: str,
                                  last_image_path: str,
                                  save_path: str,
                                  duration: int = 5,
                                  prompt: str = "",
                                  reference_image_paths: Optional[List[str]] = None,
                                  **kwargs) -> Optional[str]:
        """首尾帧→视频（默认实现：退化为单图模式）"""
        return self.image_to_video(first_image_path, save_path,
                                   duration, prompt,
                                   reference_image_paths, **kwargs)

    def text_to_video(self, prompt: str, save_path: str,
                      duration: int = 5,
                      reference_image_paths: Optional[List[str]] = None,
                      **kwargs) -> Optional[str]:
        """纯文字→视频（默认返回None，不支持的模型不实现）"""
        return None

    @abstractmethod
    def batch_generate_videos(self, tasks: List[dict],
                              episode_num: int) -> List[Optional[str]]:
        """批量生成视频
        
        Args:
            tasks: [{"first_frame": path, "last_frame": path|None, 
                     "prompt": str, "ref_images": [path], "ref_video": path|None}, ...]
            episode_num: 集数
            
        Returns:
            [video_path|None, ...]
        """
        pass


# ============================================================
# 抽象基类：TTS引擎
# ============================================================

class BaseTTSEngine(ABC):
    """语音合成引擎抽象层"""

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def synthesize(self, text: str, output_path: str,
                   voice_name: str = "", emotion: str = "",
                   speed: float = 1.0, volume: float = 1.0,
                   **kwargs) -> dict:
        """合成语音
        Returns: {"path": str|None, "duration": float}
        """
        pass

    @abstractmethod
    def generate_silence(self, duration: float, output_path: str) -> dict:
        """生成静音音频"""
        pass

    def get_voice_options(self) -> List[str]:
        """返回可选音色列表"""
        return []


# ============================================================
# 模型注册中心
# ============================================================

class ModelRegistry:
    """全局模型注册中心 - 按功能分类，一键切换"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 注册表
        self._text_engines: Dict[str, type] = {}
        self._image_engines: Dict[str, type] = {}
        self._video_engines: Dict[str, type] = {}
        self._tts_engines: Dict[str, type] = {}

        # 当前选中
        self._active_text: str = ""
        self._active_image: str = ""
        self._active_video: str = ""
        self._active_tts: str = ""

        # 缓存的实例
        self._instances: Dict[str, Any] = {}

        print("[ModelRegistry] 模型注册中心初始化")

    # ==================== 注册 ====================

    def register_text(self, name: str, engine_class: type):
        self._text_engines[name] = engine_class
        if not self._active_text:
            self._active_text = name
        print(f"  📝 注册文本引擎: {name}")

    def register_image(self, name: str, engine_class: type):
        self._image_engines[name] = engine_class
        if not self._active_image:
            self._active_image = name
        print(f"  🎨 注册图片引擎: {name}")

    def register_video(self, name: str, engine_class: type):
        self._video_engines[name] = engine_class
        if not self._active_video:
            self._active_video = name
        print(f"  🎬 注册视频引擎: {name}")

    def register_tts(self, name: str, engine_class: type):
        self._tts_engines[name] = engine_class
        if not self._active_tts:
            self._active_tts = name
        print(f"  🔊 注册TTS引擎: {name}")

    # ==================== 切换 ====================

    def set_active_text(self, name: str):
        if name in self._text_engines:
            self._active_text = name
            # 清除旧实例缓存
            self._instances.pop(f"text_{name}", None)
            print(f"  ✅ 切换文本引擎: {name}")
        else:
            raise ValueError(f"未注册的文本引擎: {name}, 可选: {list(self._text_engines.keys())}")

    def set_active_image(self, name: str):
        if name in self._image_engines:
            self._active_image = name
            self._instances.pop(f"image_{name}", None)
            print(f"  ✅ 切换图片引擎: {name}")
        else:
            raise ValueError(f"未注册的图片引擎: {name}, 可选: {list(self._image_engines.keys())}")

    def set_active_video(self, name: str):
        if name in self._video_engines:
            self._active_video = name
            self._instances.pop(f"video_{name}", None)
            print(f"  ✅ 切换视频引擎: {name}")
        else:
            raise ValueError(f"未注册的视频引擎: {name}, 可选: {list(self._video_engines.keys())}")

    def set_active_tts(self, name: str):
        if name in self._tts_engines:
            self._active_tts = name
            self._instances.pop(f"tts_{name}", None)
            print(f"  ✅ 切换TTS引擎: {name}")
        else:
            raise ValueError(f"未注册的TTS引擎: {name}, 可选: {list(self._tts_engines.keys())}")

    # ==================== 获取实例 ====================

    def _get_or_create(self, category: str, name: str, registry: dict) -> Any:
        cache_key = f"{category}_{name}"
        if cache_key not in self._instances:
            if name not in registry:
                raise ValueError(f"未注册的{category}引擎: {name}")
            self._instances[cache_key] = registry[name]()
        return self._instances[cache_key]

    def get_text_engine(self, name: str = None) -> BaseTextEngine:
        name = name or self._active_text
        return self._get_or_create("text", name, self._text_engines)

    def get_image_engine(self, name: str = None) -> BaseImageEngine:
        name = name or self._active_image
        return self._get_or_create("image", name, self._image_engines)

    def get_video_engine(self, name: str = None) -> BaseVideoEngine:
        name = name or self._active_video
        return self._get_or_create("video", name, self._video_engines)

    def get_tts_engine(self, name: str = None) -> BaseTTSEngine:
        name = name or self._active_tts
        return self._get_or_create("tts", name, self._tts_engines)

    # ==================== 查询 ====================

    def list_text_engines(self) -> List[str]:
        return list(self._text_engines.keys())

    def list_image_engines(self) -> List[str]:
        return list(self._image_engines.keys())

    def list_video_engines(self) -> List[str]:
        return list(self._video_engines.keys())

    def list_tts_engines(self) -> List[str]:
        return list(self._tts_engines.keys())

    def get_active_names(self) -> dict:
        return {
            "text": self._active_text,
            "image": self._active_image,
            "video": self._active_video,
            "tts": self._active_tts,
        }

    def get_video_capability(self, name: str = None) -> ModelCapability:
        """获取视频引擎能力描述（GUI用来动态显示上传区域）"""
        engine = self.get_video_engine(name)
        return engine.get_capability()

    def get_image_capability(self, name: str = None) -> ModelCapability:
        """获取图片引擎能力描述"""
        engine = self.get_image_engine(name)
        return engine.get_capability()

    def get_all_capabilities(self) -> dict:
        """获取所有活跃引擎的能力（GUI总览用）"""
        result = {}
        try:
            result["image"] = {
                "name": self._active_image,
                "cap": self.get_image_engine().get_capability()
            }
        except:
            pass
        try:
            result["video"] = {
                "name": self._active_video,
                "cap": self.get_video_engine().get_capability()
            }
        except:
            pass
        return result


# ============================================================
# 全局单例快捷访问
# ============================================================

def get_registry() -> ModelRegistry:
    """获取全局模型注册中心"""
    return ModelRegistry()
