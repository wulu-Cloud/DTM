# ============================================================
# tts_engine.py - V3 API 情感语音指令版 v9.1
# ============================================================
# 核心改动：
# 1. VOICE_MAP 扩展为43个音色的完整映射
# 2. voice_type ID 直通（Gemini直接输出voice_type ID）
# 3. 保持旧标签兼容
# ============================================================

"""
==========================================
🔊 TTS 语音合成引擎 v9.1 — 43音色完整版
==========================================
"""
import os
import requests
import json
import base64
import uuid
import re
import time
import subprocess
import config as _cfg

# ================================================================
# 43音色完整库（从 ListSpeakers API 获取）
# ================================================================

# voice_type ID → 音色元数据
VOICE_LIBRARY = {
    # --- 中文女声 uranus ---
    "zh_female_xiaohe_uranus_bigtts":         {"label": "小何",     "gender": "female", "style": "温柔知性"},
    "zh_female_vv_uranus_bigtts":             {"label": "Vivi",    "gender": "female", "style": "活泼甜美"},
    "zh_female_sajiaoxuemei_uranus_bigtts":   {"label": "撒娇学妹", "gender": "female", "style": "撒娇可爱"},
    "zh_female_linjianvhai_uranus_bigtts":    {"label": "邻家女孩", "gender": "female", "style": "清新自然"},
    "zh_female_kefunvsheng_uranus_bigtts":    {"label": "暖阳女声", "gender": "female", "style": "温暖阳光"},
    "zh_female_cancan_uranus_bigtts":         {"label": "知性灿灿", "gender": "female", "style": "知性大方"},
    "zh_female_liuchangnv_uranus_bigtts":     {"label": "流畅女声", "gender": "female", "style": "流畅自然"},
    "zh_female_meilinvyou_uranus_bigtts":     {"label": "魅力女友", "gender": "female", "style": "温柔魅力"},
    "zh_female_jitangnv_uranus_bigtts":       {"label": "鸡汤女",   "gender": "female", "style": "治愈温暖"},
    "zh_female_mizai_uranus_bigtts":          {"label": "咪仔",     "gender": "female", "style": "可爱俏皮"},
    "zh_female_yingyujiaoxue_uranus_bigtts":  {"label": "Tina老师", "gender": "female", "style": "专业亲和"},
    "zh_female_shuangkuaisisi_uranus_bigtts": {"label": "爽快思思", "gender": "female", "style": "爽快干练"},
    "zh_female_tianmeitaozi_uranus_bigtts":   {"label": "甜美桃子", "gender": "female", "style": "甜美少女"},
    "zh_female_qingxinnvsheng_uranus_bigtts": {"label": "清新女声", "gender": "female", "style": "清新文艺"},
    "zh_female_xiaoxue_uranus_bigtts":        {"label": "儿童绘本", "gender": "female", "style": "童真可爱"},
    "zh_female_tianmeixiaoyuan_uranus_bigtts": {"label": "甜美小源", "gender": "female", "style": "甜美温柔"},
    "zh_female_peiqi_uranus_bigtts":          {"label": "佩奇猪",   "gender": "female", "style": "萝莉可爱"},
    # --- 中文男声 uranus ---
    "zh_male_shaonianzixin_uranus_bigtts":    {"label": "少年梓辛", "gender": "male", "style": "少年清朗"},
    "zh_male_liufei_uranus_bigtts":           {"label": "刘飞",     "gender": "male", "style": "成熟稳重"},
    "zh_male_ruyayichen_uranus_bigtts":       {"label": "儒雅逸辰", "gender": "male", "style": "儒雅磁性"},
    "zh_male_dayi_uranus_bigtts":             {"label": "大壹",     "gender": "male", "style": "沉稳大气"},
    "zh_male_sunwukong_uranus_bigtts":        {"label": "猴哥",     "gender": "male", "style": "霸气张扬"},
    "zh_male_taocheng_uranus_bigtts":         {"label": "陶成",     "gender": "male", "style": "温润如玉"},
    "zh_male_m191_uranus_bigtts":             {"label": "云舟",     "gender": "male", "style": "低沉磁性"},
    "zh_male_sophie_uranus_bigtts":           {"label": "魅力苏菲", "gender": "male", "style": "独特魅力"},
    # --- 英文 ---
    "en_female_stokie_uranus_bigtts":         {"label": "Stokie",  "gender": "female", "style": "英文女声"},
    "en_female_dacey_uranus_bigtts":          {"label": "Dacey",   "gender": "female", "style": "英文女声"},
    "en_male_tim_uranus_bigtts":              {"label": "Tim",     "gender": "male",   "style": "英文男声"},
    # --- Saturn系列 ---
    "zh_female_santongyongns_saturn_bigtts":        {"label": "流畅女声S", "gender": "female", "style": "流畅自然"},
    "zh_female_meilinvyou_saturn_bigtts":           {"label": "魅力女友S", "gender": "female", "style": "温柔魅力"},
    "zh_female_mizai_saturn_bigtts":                {"label": "咪仔S",     "gender": "female", "style": "可爱俏皮"},
    "saturn_zh_female_cancan_tob":                  {"label": "知性灿灿S", "gender": "female", "style": "知性大方"},
    "zh_female_jitangnv_saturn_bigtts":             {"label": "鸡汤女S",   "gender": "female", "style": "治愈温暖"},
    "zh_male_dayi_saturn_bigtts":                   {"label": "大壹S",     "gender": "male",   "style": "沉稳大气"},
    "zh_female_xueayi_saturn_bigtts":               {"label": "儿童绘本S", "gender": "female", "style": "童真可爱"},
    "saturn_zh_female_wenwanshanshan_cs_tob":       {"label": "温婉珊珊",  "gender": "female", "style": "温婉柔和"},
    "saturn_zh_female_reqingaina_cs_tob":           {"label": "热情艾娜",  "gender": "female", "style": "热情开朗"},
    "saturn_zh_female_keainvsheng_tob":             {"label": "可爱女生",  "gender": "female", "style": "可爱甜美"},
    "saturn_zh_male_shuanglangshaonian_tob":        {"label": "爽朗少年",  "gender": "male",   "style": "爽朗阳光"},
    "saturn_zh_female_tiaopigongzhu_tob":           {"label": "调皮公主",  "gender": "female", "style": "调皮活泼"},
    "zh_male_ruyayichen_saturn_bigtts":             {"label": "儒雅逸辰S", "gender": "male",   "style": "儒雅磁性"},
    "saturn_zh_male_tiancaitongzhuo_tob":           {"label": "天才同桌",  "gender": "male",   "style": "聪明活泼"},
    "saturn_zh_female_qingyingduoduo_cs_tob":       {"label": "轻盈朵朵",  "gender": "female", "style": "轻盈灵动"},
}

# ================================================================
# 旧标签 → voice_type 兼容映射（保持GUI和旧代码不炸）
# ================================================================

VOICE_MAP = {
    # 男性角色标签
    "霸总":   "zh_male_ruyayichen_uranus_bigtts",
    "少年":   "zh_male_shaonianzixin_uranus_bigtts",
    "大叔":   "zh_male_dayi_uranus_bigtts",
    "反派":   "zh_male_sunwukong_uranus_bigtts",
    "冷酷":   "zh_male_m191_uranus_bigtts",
    "宫":     "zh_male_dayi_uranus_bigtts",
    "硬汉":   "zh_male_liufei_uranus_bigtts",
    "沉稳男": "zh_male_dayi_uranus_bigtts",
    "温润男": "zh_male_taocheng_uranus_bigtts",
    # 女性角色标签
    "少女":   "zh_female_tianmeixiaoyuan_uranus_bigtts",
    "御姐":   "zh_female_shuangkuaisisi_uranus_bigtts",
    "萝莉":   "zh_female_peiqi_uranus_bigtts",
    "女警":   "zh_female_shuangkuaisisi_uranus_bigtts",
    "温柔":   "zh_female_linjianvhai_uranus_bigtts",
    "干练女": "zh_female_shuangkuaisisi_uranus_bigtts",
    "知性女": "zh_female_cancan_uranus_bigtts",
    "撒娇":   "zh_female_sajiaoxuemei_uranus_bigtts",
    "甜美":   "zh_female_tianmeitaozi_uranus_bigtts",
    # 旁白
    "旁白":   "zh_male_dayi_uranus_bigtts",
    "旁白男": "zh_male_dayi_uranus_bigtts",
    "旁白女": "zh_female_cancan_uranus_bigtts",
    # ★ 用label名也能匹配（Gemini可能输出中文label）
    "小何":     "zh_female_xiaohe_uranus_bigtts",
    "Vivi":     "zh_female_vv_uranus_bigtts",
    "撒娇学妹": "zh_female_sajiaoxuemei_uranus_bigtts",
    "邻家女孩": "zh_female_linjianvhai_uranus_bigtts",
    "暖阳女声": "zh_female_kefunvsheng_uranus_bigtts",
    "知性灿灿": "zh_female_cancan_uranus_bigtts",
    "流畅女声": "zh_female_liuchangnv_uranus_bigtts",
    "魅力女友": "zh_female_meilinvyou_uranus_bigtts",
    "鸡汤女":   "zh_female_jitangnv_uranus_bigtts",
    "咪仔":     "zh_female_mizai_uranus_bigtts",
    "Tina老师": "zh_female_yingyujiaoxue_uranus_bigtts",
    "爽快思思": "zh_female_shuangkuaisisi_uranus_bigtts",
    "甜美桃子": "zh_female_tianmeitaozi_uranus_bigtts",
    "清新女声": "zh_female_qingxinnvsheng_uranus_bigtts",
    "儿童绘本": "zh_female_xiaoxue_uranus_bigtts",
    "甜美小源": "zh_female_tianmeixiaoyuan_uranus_bigtts",
    "佩奇猪":   "zh_female_peiqi_uranus_bigtts",
    "少年梓辛": "zh_male_shaonianzixin_uranus_bigtts",
    "刘飞":     "zh_male_liufei_uranus_bigtts",
    "儒雅逸辰": "zh_male_ruyayichen_uranus_bigtts",
    "大壹":     "zh_male_dayi_uranus_bigtts",
    "猴哥":     "zh_male_sunwukong_uranus_bigtts",
    "陶成":     "zh_male_taocheng_uranus_bigtts",
    "云舟":     "zh_male_m191_uranus_bigtts",
    "魅力苏菲": "zh_male_sophie_uranus_bigtts",
}


# ================================================================
# 情感 → 语音指令映射（V3 API核心）
# ================================================================

EMOTION_TO_INSTRUCTION = {
    "angry":    "请用愤怒、咬牙切齿的语气朗读",
    "shout":    "请用大声怒吼、声嘶力竭的语气朗读",
    "sad":      "请用悲伤、哽咽、快要哭出来的语气朗读",
    "happy":    "请用开心、兴奋、充满喜悦的语气朗读",
    "scared":   "请用恐惧、颤抖、害怕的语气朗读",
    "calm":     "请用平静、沉稳、不带情绪的语气朗读",
    "cold":     "请用冰冷、无情、漠不关心的语气朗读",
    "whisper":  "请用低声耳语、小心翼翼的语气朗读",
    "excited":  "请用极度兴奋、激动万分的语气朗读",
    "nervous":  "请用紧张、不安、语速略快的语气朗读",
    "amazed":   "请用震惊、难以置信、惊讶的语气朗读",
    "dramatic": "请用戏剧化的、充满张力的语气朗读",
    "epic":     "请用庄严、史诗感、气势磅礴的语气朗读",
    "default":  "",
}

EMOTION_ALIAS = {
    "dramatic": "angry", "tense": "scared", "epic": "shout",
    "romantic": "happy", "melancholy": "sad", "anxious": "scared",
    "excited": "excited", "serious": "cold", "gentle": "calm",
    "nervous": "scared", "furious": "angry", "cheerful": "happy",
    "grief": "sad", "panic": "scared", "tender": "calm",
    "mysterious": "whisper", "intense": "shout", "sorrowful": "sad",
    "joyful": "happy", "fearful": "scared", "stern": "cold",
    "playful": "happy", "desperate": "sad", "threatening": "angry",
}

EMOTION_STYLE = {
    "amazed":   {"speed": 1.12, "volume": 1.3},
    "angry":    {"speed": 1.15, "volume": 1.35},
    "sad":      {"speed": 0.85, "volume": 0.75},
    "happy":    {"speed": 1.08, "volume": 1.15},
    "scared":   {"speed": 1.15, "volume": 0.85},
    "calm":     {"speed": 0.92, "volume": 0.9},
    "cold":     {"speed": 0.9,  "volume": 0.85},
    "whisper":  {"speed": 0.85, "volume": 0.6},
    "shout":    {"speed": 1.2,  "volume": 1.4},
    "excited":  {"speed": 1.18, "volume": 1.25},
    "nervous":  {"speed": 1.12, "volume": 0.95},
    "dramatic": {"speed": 1.05, "volume": 1.15},
    "epic":     {"speed": 0.95, "volume": 1.25},
    "default":  {"speed": 1.0,  "volume": 1.0},
}


def infer_emotion_from_text(text: str) -> str:
    if not text:
        return "default"
    rules = [
        ("shout",   ["住手", "滚", "闭嘴", "放开我", "不要！", "快跑", "救命"]),
        ("angry",   ["混蛋", "该死", "岂有此理", "去死", "可恶", "废物", "不可饶恕", "怒"]),
        ("scared",  ["怎么办", "不要", "害怕", "可怕", "糟了", "完了", "救我", "鬼", "恐"]),
        ("amazed",  ["什么？", "竟然", "居然", "没想到", "不可能", "天哪", "我的天", "真的吗"]),
        ("sad",     ["对不起", "难过", "可惜", "遗憾", "伤心", "再见", "永别", "不会再", "眼泪", "哭"]),
        ("happy",   ["太好了", "开心", "真棒", "太棒了", "恭喜", "成功", "终于", "高兴", "哈哈"]),
        ("nervous", ["紧张", "小心", "注意", "别动", "嘘", "有人", "来了"]),
        ("whisper", ["悄悄", "秘密", "别让", "偷偷", "轻声"]),
        ("cold",    ["无所谓", "随便", "与我无关", "不关我事", "哼"]),
        ("excited", ["太厉害了", "不敢相信", "超级", "绝了", "爽"]),
    ]
    for emotion, keywords in rules:
        for kw in keywords:
            if kw in text:
                return emotion
    if text.count("！") >= 2 or text.count("!") >= 2:
        return "excited"
    if text.endswith("？") or text.endswith("?"):
        return "amazed"
    if "..." in text or "……" in text:
        return "sad"
    return "default"


def smart_match_voice(character_name, gender="", personality="", age=""):
    """智能匹配音色（供GUI和外部调用）- 返回旧标签"""
    text = f"{character_name} {personality} {age}".lower()
    is_female = gender in ("female", "女", "woman") or any(w in text for w in ["女", "姐", "妹", "母", "嫂", "婆"])
    is_villain = any(w in text for w in ["反派", "暴君", "邪", "恶", "魔", "冷酷", "阴险"])
    is_young = any(w in text for w in ["少年", "少女", "学生", "年轻", "青春", "小", "young"])
    is_boss = any(w in text for w in ["总裁", "总", "董事", "老板", "霸总"])
    is_tough = any(w in text for w in ["硬汉", "粗犷", "暴躁", "彪悍", "刚猛", "警察", "军人", "将军"])
    
    if is_female:
        if is_tough or any(w in text for w in ["干练", "飒", "利落", "冷静", "警"]):
            return "干练女"
        elif is_young:
            return "少女"
        elif any(w in text for w in ["御姐", "冷艳", "成熟", "妩媚"]):
            return "御姐"
        elif any(w in text for w in ["温柔", "温暖", "柔和"]):
            return "温柔"
        else:
            return "少女"
    else:
        if is_villain:
            return "反派"
        elif is_tough:
            return "硬汉"
        elif is_boss:
            return "霸总"
        elif is_young:
            return "少年"
        else:
            return "旁白男"


def get_voice_options():
    """返回所有可选的音色标签列表（供GUI下拉框使用）"""
    # 先返回常用标签，再返回全部voice_type label
    common = ["旁白男", "旁白女", "霸总", "少年", "少女", "御姐", "反派", 
              "硬汉", "干练女", "温柔", "萝莉", "冷酷", "大叔", "知性女",
              "撒娇", "甜美", "温润男", "沉稳男"]
    # 加上所有label名
    labels = [v["label"] for v in VOICE_LIBRARY.values() 
              if v["label"] not in common and "英文" not in v["style"]]
    return common + sorted(set(labels))


def get_voice_catalog_for_gemini() -> str:
    """★ 生成供Gemini选择音色的文本目录"""
    lines = []
    lines.append("=== 可用音色列表 (voice_type ID) ===")
    lines.append("")
    lines.append("【中文女声】")
    for vid, info in VOICE_LIBRARY.items():
        if info["gender"] == "female" and "英文" not in info["style"] and "saturn" not in vid:
            lines.append(f"  {vid}  →  {info['label']}({info['style']})")
    lines.append("")
    lines.append("【中文男声】")
    for vid, info in VOICE_LIBRARY.items():
        if info["gender"] == "male" and "英文" not in info["style"] and "saturn" not in vid:
            lines.append(f"  {vid}  →  {info['label']}({info['style']})")
    lines.append("")
    lines.append("选择规则：")
    lines.append("- 年轻女性/少女 → zh_female_tianmeixiaoyuan_uranus_bigtts 或 zh_female_vv_uranus_bigtts")
    lines.append("- 干练/御姐/女警 → zh_female_shuangkuaisisi_uranus_bigtts")
    lines.append("- 温柔女性 → zh_female_linjianvhai_uranus_bigtts 或 zh_female_xiaohe_uranus_bigtts")
    lines.append("- 知性女性 → zh_female_cancan_uranus_bigtts")
    lines.append("- 萝莉/儿童 → zh_female_peiqi_uranus_bigtts")
    lines.append("- 少年/阳光男 → zh_male_shaonianzixin_uranus_bigtts")
    lines.append("- 霸总/儒雅男 → zh_male_ruyayichen_uranus_bigtts")
    lines.append("- 沉稳/旁白男 → zh_male_dayi_uranus_bigtts")
    lines.append("- 反派/霸气 → zh_male_sunwukong_uranus_bigtts")
    lines.append("- 冷酷/低沉男 → zh_male_m191_uranus_bigtts")
    lines.append("- 成熟稳重男 → zh_male_liufei_uranus_bigtts")
    lines.append("- 温润斯文男 → zh_male_taocheng_uranus_bigtts")
    return "\n".join(lines)


class TTSEngine:
    def __init__(self):
        from config import VOLC_TTS_APP_ID, VOLC_TTS_TOKEN
        self.app_id = VOLC_TTS_APP_ID
        self.access_token = VOLC_TTS_TOKEN
        self.v3_url = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        self.v3_resource_id = "seed-tts-2.0"
        self.v1_url = "https://openspeech.bytedance.com/api/v1/tts"
        try:
            from config import VOLC_TTS_CLUSTER
            self.cluster = VOLC_TTS_CLUSTER
        except:
            self.cluster = "volcano_tts"
        print(f"🔊 TTS v9.1 (43音色完整版)")

    def synthesize(self, text: str, output_path: str,
                   voice_name: str = None,
                   speed: float = 1.0,
                   volume: float = 1.0,
                   pitch: float = 1.0,
                   emotion: str = "") -> dict:
        voice_type = self._resolve_voice_type(voice_name)
        emotion_key = self._resolve_emotion(emotion, text)
        instruction = EMOTION_TO_INSTRUCTION.get(emotion_key, "")
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        text = text.strip()
        if not text:
            return {"path": None, "duration": 0}
        max_len = 480
        if len(text) > max_len:
            return self._synthesize_long(text, voice_type, output_path, speed, instruction)
        for attempt in range(3):
            try:
                success = self._call_v3_api(text, voice_type, output_path, instruction)
                if success and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                    duration = self._get_audio_duration(output_path)
                    size_kb = os.path.getsize(output_path) / 1024
                    emo_tag = f" emo={emotion_key}" if emotion_key != "default" else ""
                    instr_tag = f" 🎭[{instruction[:15]}...]" if instruction else ""
                    label = VOICE_LIBRARY.get(voice_type, {}).get("label", voice_name)
                    print(f"      🔈 TTS: {os.path.basename(output_path)} "
                          f"({size_kb:.1f}KB, {duration:.1f}s) voice={label}{emo_tag}{instr_tag}")
                    return {"path": output_path, "duration": duration}
                else:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    success = self._call_v1_api(text, voice_type, output_path, speed)
                    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                        duration = self._get_audio_duration(output_path)
                        return {"path": output_path, "duration": duration}
            except Exception as e:
                print(f"      ⚠️TTS 第{attempt+1}次失败: {e}")
            time.sleep(0.5)
        return {"path": None, "duration": 0}

    def _resolve_voice_type(self, voice_name: str) -> str:
        """将任意voice_name解析为实际voice_type ID"""
        if not voice_name or voice_name.strip() == "":
            return "zh_male_dayi_uranus_bigtts"
        vn = voice_name.strip()
        # ★ 直接是voice_type ID（Gemini直接输出的情况）
        if vn in VOICE_LIBRARY:
            return vn
        # 旧标签映射
        if vn in VOICE_MAP:
            return VOICE_MAP[vn]
        # BV格式直通
        if re.match(r"^BV\d+", vn):
            return vn
        # 模糊匹配VOICE_MAP key
        for key in VOICE_MAP:
            if vn in key or key in vn:
                return VOICE_MAP[key]
        # 按label搜索VOICE_LIBRARY
        for vid, info in VOICE_LIBRARY.items():
            if info["label"] == vn:
                return vid
        print(f"    ⚠️ 音色匹配失败[{vn}]，fallback旁白男")
        return "zh_male_dayi_uranus_bigtts"

    def _resolve_emotion(self, emotion: str, text: str) -> str:
        emotion_key = (emotion or "").strip().lower()
        if emotion_key in EMOTION_ALIAS:
            emotion_key = EMOTION_ALIAS[emotion_key]
        if emotion_key and emotion_key in EMOTION_TO_INSTRUCTION:
            return emotion_key
        inferred = infer_emotion_from_text(text)
        if inferred != "default":
            return inferred
        return "default"

    def _call_v3_api(self, text, voice_type, output_path, instruction=""):
        headers = {
            'X-Api-App-Id': self.app_id,
            'X-Api-Access-Key': self.access_token,
            'X-Api-Resource-Id': self.v3_resource_id,
            'Content-Type': 'application/json',
        }
        payload = {
            'user': {'uid': 'novel_to_video'},
            'namespace': 'BidirectionalTTS',
            'req_params': {'text': text, 'speaker': voice_type}
        }
        if instruction:
            payload['additions'] = {'context_texts': [instruction]}
        try:
            resp = requests.post(self.v3_url, headers=headers, json=payload, stream=True, timeout=60)
            data = b''
            for chunk in resp.iter_content(chunk_size=4096):
                data += chunk
            audio = self._parse_v3_response(data)
            if audio and len(audio) > 200:
                with open(output_path, 'wb') as f:
                    f.write(audio)
                return True
            else:
                try:
                    err = json.loads(data.decode('utf-8', errors='ignore'))
                    print(f"      V3 API error: code={err.get('code')}, msg={err.get('message','')[:80]}")
                except:
                    pass
                return False
        except Exception as e:
            print(f"      V3 API exception: {e}")
            return False

    def _parse_v3_response(self, raw_data):
        try:
            text = raw_data.decode('utf-8', errors='ignore')
        except:
            return None
        audio_parts = []
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    json_str = text[start:i+1]
                    try:
                        obj = json.loads(json_str)
                        if obj.get('code') == 0 and 'data' in obj and obj['data']:
                            audio_parts.append(base64.b64decode(obj['data']))
                    except:
                        pass
                    start = -1
        if audio_parts:
            return b''.join(audio_parts)
        try:
            obj = json.loads(text)
            if obj.get('code') == 0 and 'data' in obj and obj['data']:
                return base64.b64decode(obj['data'])
        except:
            pass
        return None

    def _call_v1_api(self, text, voice_type, output_path, speed_ratio=1.0):
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer;{self.access_token}"}
        data = {
            "app": {"appid": self.app_id, "token": self.access_token, "cluster": self.cluster},
            "user": {"uid": "novel_to_video"},
            "audio": {"voice_type": voice_type, "encoding": "mp3", "speed_ratio": speed_ratio},
            "request": {"reqid": str(uuid.uuid4()), "text": text, "operation": "query"}
        }
        try:
            resp = requests.post(self.v1_url, headers=headers, data=json.dumps(data), timeout=30)
            result = resp.json()
            if result.get("code") == 3000 and "data" in result:
                audio_data = base64.b64decode(result["data"])
                with open(output_path, "wb") as f:
                    f.write(audio_data)
                return True
            return False
        except:
            return False

    def _synthesize_long(self, text, voice_type, output_path, speed=1.0, instruction=""):
        sentences = re.split(r'([。！？；\n])', text)
        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) < 460:
                current += s
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = s
        if current.strip():
            chunks.append(current.strip())
        if not chunks:
            return {"path": None, "duration": 0}
        temp_files = []
        for i, chunk in enumerate(chunks):
            temp_path = output_path.replace(".mp3", f"_part{i}.mp3")
            success = self._call_v3_api(chunk, voice_type, temp_path, instruction)
            if not success:
                success = self._call_v1_api(chunk, voice_type, temp_path, speed)
            if success and os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                temp_files.append(temp_path)
            time.sleep(0.15)
        if not temp_files:
            return {"path": None, "duration": 0}
        if len(temp_files) == 1:
            os.replace(temp_files[0], output_path)
        else:
            self._concat_audio_ffmpeg(temp_files, output_path)
        for tf in temp_files:
            try: os.remove(tf)
            except: pass
        duration = self._get_audio_duration(output_path)
        return {"path": output_path, "duration": duration}

    def _concat_audio_ffmpeg(self, audio_files, output_path):
        list_file = output_path + ".list.txt"
        with open(list_file, 'w', encoding='utf-8') as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af).replace(chr(92), '/')}'\n")
        try:
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                           "-i", list_file, "-c:a", "libmp3lame", "-b:a", "128k",
                           output_path], capture_output=True, timeout=30)
        except:
            with open(output_path, "wb") as outf:
                for af in audio_files:
                    with open(af, "rb") as inf:
                        outf.write(inf.read())
        finally:
            try: os.remove(list_file)
            except: pass

    def generate_silence(self, duration, output_path):
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
                 "-t", str(duration), "-c:a", "libmp3lame", "-b:a", "128k", output_path],
                capture_output=True, timeout=30)
            if result.returncode == 0:
                return {"path": output_path, "duration": duration}
        except: pass
        return {"path": None, "duration": duration}

    def _get_audio_duration(self, path):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path], capture_output=True, text=True, timeout=10)
            dur = float(result.stdout.strip())
            if dur > 0: return dur
        except: pass
        try:
            return os.path.getsize(path) / (128 * 1024 / 8)
        except:
            return 3.0


if __name__ == "__main__":
    tts = TTSEngine()
    print("可用音色:", get_voice_options())
    result = tts.synthesize("你怎么能这样对我！", "test_v91.mp3", voice_name="少女", emotion="angry")
    print(f"测试: {result}")
