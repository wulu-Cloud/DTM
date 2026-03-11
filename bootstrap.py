# ============================================================
# bootstrap.py - 引导注册：把所有适配器注册到 ModelRegistry
# ============================================================

from model_registry import get_registry


def init_all_engines():
    """注册所有引擎到模型注册中心"""
    registry = get_registry()

    print("=" * 50)
    print("  🚀 引导注册：加载所有引擎适配器")
    print("=" * 50)

    # ---- 文本引擎 ----
    try:
        from adapters.gemini_text_adapter import GeminiTextEngine
        registry.register_text("gemini", GeminiTextEngine)
    except Exception as e:
        print(f"  ⚠️ Gemini文本引擎注册失败: {e}")

    try:
        from adapters.deepseek_text_adapter import DeepSeekTextEngine
        registry.register_text("deepseek", DeepSeekTextEngine)
    except Exception as e:
        print(f"  ⚠️ DeepSeek文本引擎注册失败: {e}")

    # ---- 图片引擎 ----
    try:
        from adapters.gemini_image_adapter import GeminiImageEngine
        registry.register_image("gemini", GeminiImageEngine)
    except Exception as e:
        print(f"  ⚠️ Gemini图片引擎注册失败: {e}")
    try:
        from adapters.sd_image_adapter import SDImageEngine
        registry.register_image("sd", SDImageEngine)
    except Exception as e:
        print(f"  ⚠️ SD图片引擎注册失败: {e}")
    # ---- 视频引擎 ----
    try:
        from adapters.jimeng_video_adapter import JimengVideoEngine
        registry.register_video("jimeng", JimengVideoEngine)
    except Exception as e:
        print(f"  ⚠️ 即梦视频引擎注册失败: {e}")
    try:
        from adapters.animatediff_video_adapter import AnimateDiffVideoEngine
        registry.register_video("animatediff", AnimateDiffVideoEngine)
    except Exception as e:
        print(f"  ⚠ AnimateDiff视频引擎注册失败：{e}")

    # ---- TTS引擎 ----
    try:
        from adapters.volcano_tts_adapter import VolcanoTTSEngine
        registry.register_tts("volcano", VolcanoTTSEngine)
    except Exception as e:
        print(f"  ⚠️ 火山TTS引擎注册失败: {e}")

    # ---- 设置默认激活（带防护）----
    text_list = registry.list_text_engines()
    image_list = registry.list_image_engines()
    video_list = registry.list_video_engines()
    tts_list = registry.list_tts_engines()

    if "gemini" in text_list:
        registry.set_active_text("gemini")
    elif text_list:
        registry.set_active_text(text_list[0])

    if "sd" in image_list:
        registry.set_active_image("sd")
    elif image_list:
        registry.set_active_image(image_list[0])

    if "animatediff" in video_list:
        registry.set_active_video("animatediff")
    elif "jimeng" in video_list:
        registry.set_active_video("jimeng")

    elif video_list:
        registry.set_active_video(video_list[0])

    if "volcano" in tts_list:
        registry.set_active_tts("volcano")
    elif tts_list:
        registry.set_active_tts(tts_list[0])

    print("=" * 50)
    active = registry.get_active_names()
    print(f"  📝 文本: {active['text']}")
    print(f"  🎨 图片: {active['image']}")
    print(f"  🎬 视频: {active['video']}")
    print(f"  🔊 TTS:  {active['tts']}")
    print("=" * 50)

    return registry


# 便捷函数：旧代码迁移用
# ===========================================================

_bootstrapped = False

def _ensure_init():
    global _bootstrapped
    if not _bootstrapped:
        init_all_engines()
        _bootstrapped = True

def get_text_engine():
    _ensure_init()
    return get_registry().get_text_engine()

def get_image_engine():
    _ensure_init()
    return get_registry().get_image_engine()

def get_video_engine():
    _ensure_init()
    return get_registry().get_video_engine()

def get_tts_engine():
    _ensure_init()
    return get_registry().get_tts_engine()
