# gemini_engine.py - Gemini 文本分析 + 图片生成引擎 v4.0
# 核心改进：角色一致性、中英文对照、首尾帧支持

import requests
import json
import base64
import time
import os
import re
from config import (
    METACHAT_API_KEY, GEMINI_BASE_URL,
    GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL,
    IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
)


def _auto_match_voice(gender: str, personality: str) -> str:
    from tts_engine import VOICE_MAP
    text = (personality or "").lower()
    is_female = "female" in (gender or "").lower()
    if is_female:
        if any(w in text for w in ["干练","飒","利落","冷静"]): label="干练女"
        elif any(w in text for w in ["御姐","冷艳","成熟","高冷"]): label="御姐"
        elif any(w in text for w in ["萝莉","幼","童"]): label="萝莉"
        elif any(w in text for w in ["甜美","甜","可爱"]): label="甜美"
        elif any(w in text for w in ["温柔","温暖","柔和"]): label="温柔"
        else: label="少女"
    else:
        if any(w in text for w in ["反派","霸君","邪恶","狂"]): label="反派"
        elif any(w in text for w in ["冷酷","冰冷","无情"]): label="冷酷"
        elif any(w in text for w in ["霸总","总裁","霸气"]): label="霸总"
        elif any(w in text for w in ["硬汉","粗犷","刚猛"]): label="硬汉"
        elif any(w in text for w in ["大叔","中年","沉稳"]): label="大叔"
        elif any(w in text for w in ["温润","斯文","文雅"]): label="温润男"
        elif any(w in text for w in ["少年","年轻","青春"]): label="少年"
        else: label="少年"
    return VOICE_MAP.get(label, "zh_male_dayi_uranus_bigtts")

# 类型风格模板
GENRE_STYLES = {
    "modern_crime": {
        "visual_prefix": "OC, original character, not from any anime, modern urban setting, cinematic anime style",
        "setting_tags": "modern city, night scene, neon lights, police cars, skyscrapers",
        "clothing_guide": "modern clothes: suits, police uniforms, tactical gear, casual wear, leather jackets",
        "cn_name": "现代都市犯罪",
    },
    "scifi": {
        "visual_prefix": "OC, original character, not from any anime, sci-fi futuristic setting, cinematic anime style",
        "setting_tags": "futuristic city, spaceship interior, holographic displays",
        "clothing_guide": "futuristic clothes: space suits, cyberpunk outfits, tech armor",
        "cn_name": "科幻",
    },
    "wuxia": {
        "visual_prefix": "OC, original character, not from any anime, Chinese ancient wuxia, anime style",
        "setting_tags": "ancient Chinese city, temples, mountains, bamboo forest",
        "clothing_guide": "ancient Chinese: hanfu, martial arts robes, leather armor",
        "cn_name": "古风武侠",
    },
    "xianxia": {
        "visual_prefix": "OC, original character, not from any anime, Chinese xianxia immortal cultivation, ethereal anime style",
        "setting_tags": "celestial palace, floating mountains, spiritual realm, clouds and mist, immortal sect, sacred peaks",
        "clothing_guide": "flowing immortal robes, daoist cultivation robes, spiritual armor, jade ornaments, luminous accessories",
        "cn_name": "仙侠修仙",
    },
    "xuanhuan": {
        "visual_prefix": "OC, original character, not from any anime, Chinese xuanhuan fantasy world, epic anime style",
        "setting_tags": "vast continent, ancient ruins, mystical realms, divine mountains, battle arenas",
        "clothing_guide": "ornate battle robes, ancient armor with magical runes, clan emblems, mystical cloaks",
        "cn_name": "玄幻",
    },
    "fantasy": {
        "visual_prefix": "OC, original character, not from any anime, western fantasy world, epic anime style",
        "setting_tags": "magical kingdom, enchanted forest, crystal towers, medieval castle, dragon lair",
        "clothing_guide": "fantasy robes, enchanted armor, magical accessories, medieval clothing",
        "cn_name": "西方奇幻",
    },
    "urban": {
        "visual_prefix": "OC, original character, not from any anime, modern urban setting, anime style",
        "setting_tags": "modern city streets, apartments, offices, cafes",
        "clothing_guide": "modern casual: T-shirts, jeans, hoodies, dresses",
        "cn_name": "现代都市",
    },
    "romance": {
        "visual_prefix": "OC, original character, not from any anime, modern romantic setting, soft anime style, warm lighting",
        "setting_tags": "cozy cafes, beautiful gardens, sunset beach, elegant restaurants, cherry blossom streets",
        "clothing_guide": "fashionable modern clothes: elegant dresses, stylish casual wear, formal date outfits",
        "cn_name": "现代言情",
    },
    "historical_romance": {
        "visual_prefix": "OC, original character, not from any anime, ancient Chinese palace setting, elegant anime style",
        "setting_tags": "imperial palace, ancient gardens, royal court, silk curtains, moonlit pavilion",
        "clothing_guide": "ancient Chinese palace dress, royal hanfu, embroidered robes, golden hairpins, jade jewelry",
        "cn_name": "古代言情宫斗",
    },
    "military": {
        "visual_prefix": "OC, original character, not from any anime, military battlefield setting, cinematic anime style",
        "setting_tags": "battlefield, military base, war trenches, command center, tanks and helicopters",
        "clothing_guide": "military uniforms, combat fatigues, tactical vests, officer dress uniforms, army boots",
        "cn_name": "军事战争",
    },
    "horror": {
        "visual_prefix": "OC, original character, not from any anime, dark horror setting, atmospheric anime style, eerie lighting",
        "setting_tags": "haunted mansion, dark forest, abandoned hospital, foggy graveyard, cursed village",
        "clothing_guide": "dark casual clothes, tattered outfits, gothic clothing, occult accessories",
        "cn_name": "恐怖悬疑",
    },
    "apocalypse": {
        "visual_prefix": "OC, original character, not from any anime, post-apocalyptic wasteland, gritty anime style",
        "setting_tags": "ruined city, wasteland, abandoned buildings, survivor camps, overgrown highways",
        "clothing_guide": "survival gear: torn clothes, makeshift armor, gas masks, scavenged military gear, weathered coats",
        "cn_name": "末日废土",
    },
    "game_world": {
        "visual_prefix": "OC, original character, not from any anime, RPG game world, vibrant anime style",
        "setting_tags": "game interface, fantasy dungeon, guild hall, boss arena, respawn point, NPC village",
        "clothing_guide": "RPG class outfits: mage robes, knight armor, ranger leather, healer vestments, with game-like UI elements",
        "cn_name": "游戏异界",
    },
    "system_cheat": {
        "visual_prefix": "OC, original character, not from any anime, modern or mixed setting, dynamic anime style",
        "setting_tags": "modern city with holographic system panels, virtual interface overlays, mixed reality",
        "clothing_guide": "modern clothes or setting-appropriate outfits, with subtle tech/system visual effects",
        "cn_name": "系统流",
    },
    "sports": {
        "visual_prefix": "OC, original character, not from any anime, sports anime setting, energetic anime style",
        "setting_tags": "stadium, training ground, locker room, competition arena, school gym",
        "clothing_guide": "sports uniforms, team jerseys, training wear, sports shoes, competition outfits",
        "cn_name": "体育竞技",
    },
    "school": {
        "visual_prefix": "OC, original character, not from any anime, Japanese/Chinese school setting, slice-of-life anime style",
        "setting_tags": "school campus, classroom, school rooftop, library, cherry blossom path, school festival",
        "clothing_guide": "school uniforms, casual student clothes, club activity outfits",
        "cn_name": "校园青春",
    },
    "historical": {
        "visual_prefix": "OC, original character, not from any anime, Chinese historical dynasty setting, cinematic anime style",
        "setting_tags": "ancient capital city, imperial court, battlefields, ancient markets, Great Wall",
        "clothing_guide": "dynasty-accurate hanfu, official court robes, general armor, scholar garments",
        "cn_name": "历史架空",
    },
    "steampunk": {
        "visual_prefix": "OC, original character, not from any anime, steampunk Victorian setting, detailed anime style",
        "setting_tags": "steam-powered city, clockwork towers, airship docks, Victorian streets, gear-filled workshops",
        "clothing_guide": "Victorian era clothes with steampunk elements: goggles, brass accessories, corsets, top hats, mechanical limbs",
        "cn_name": "蒸汽朋克",
    },
    "cyberpunk": {
        "visual_prefix": "OC, original character, not from any anime, cyberpunk neon-lit dystopia, cinematic anime style",
        "setting_tags": "neon-lit megacity, rain-soaked streets, corporate towers, underground hacker dens, holographic ads",
        "clothing_guide": "cyberpunk fashion: neon-accent jackets, augmented body parts, tech visors, LED clothing, black leather",
        "cn_name": "赛博朋克",
    },
    "mecha": {
        "visual_prefix": "OC, original character, not from any anime, mecha sci-fi setting, dynamic anime style",
        "setting_tags": "mecha hangar, space colony, command bridge, devastated battlefield, giant robot cockpit",
        "clothing_guide": "pilot suits, military uniforms, technician overalls, futuristic officer uniforms",
        "cn_name": "机甲机战",
    },
    "mythology": {
        "visual_prefix": "OC, original character, not from any anime, Chinese mythology setting, majestic anime style",
        "setting_tags": "heavenly court, underworld, divine mountains, dragon palace under sea, mythical realms",
        "clothing_guide": "divine robes, celestial armor, deity ornaments, mythological creature motifs, sacred jewelry",
        "cn_name": "神话传说",
    },
    "detective": {
        "visual_prefix": "OC, original character, not from any anime, detective mystery setting, atmospheric anime style",
        "setting_tags": "crime scene, detective office, interrogation room, dark alley, mansion murder scene",
        "clothing_guide": "detective coats, formal suits, forensic gear, classic trench coats, smart casual",
        "cn_name": "推理探案",
    },
    "survival": {
        "visual_prefix": "OC, original character, not from any anime, wilderness survival setting, realistic anime style",
        "setting_tags": "dense jungle, deserted island, frozen tundra, deep cave, treacherous mountains",
        "clothing_guide": "survival outdoor gear: hiking boots, weatherproof jackets, cargo pants, makeshift tools",
        "cn_name": "荒野求生",
    },
    "danmei_ancient": {
        "visual_prefix": "OC, original character, not from any anime, ancient Chinese BL setting, beautiful anime style, bishounen",
        "setting_tags": "ancient Chinese palace, mountain sect, bamboo forest, moonlit lake, elegant study room",
        "clothing_guide": "elegant ancient Chinese male clothing: flowing hanfu, scholarly robes, warrior outfits, hair ornaments",
        "cn_name": "古代耽美",
    },
    "danmei_modern": {
        "visual_prefix": "OC, original character, not from any anime, modern BL setting, stylish anime style, bishounen",
        "setting_tags": "modern luxury apartments, office buildings, university campus, upscale restaurants",
        "clothing_guide": "modern stylish male clothing: designer suits, trendy casual wear, fashionable streetwear",
        "cn_name": "现代耽美",
    },
    "farming_slice": {
        "visual_prefix": "OC, original character, not from any anime, pastoral countryside setting, cozy anime style, warm colors",
        "setting_tags": "farmland, village market, rustic cottage, herb garden, peaceful riverside, ancient small town",
        "clothing_guide": "simple rural clothes: linen shirts, straw hats, aprons, plain robes, farming tools",
        "cn_name": "种田经营",
    },
    "transmigration": {
        "visual_prefix": "OC, original character, not from any anime, isekai mixed-era setting, anime style",
        "setting_tags": "contrast of modern and ancient, culture clash scenes, new world discovery",
        "clothing_guide": "mix of modern and historical clothing depending on setting, initially modern then adapting",
        "cn_name": "穿越重生",
    },
    "zombie": {
        "visual_prefix": "OC, original character, not from any anime, zombie apocalypse setting, dark cinematic anime style",
        "setting_tags": "overrun city, barricaded safe house, abandoned mall, blood-stained streets, military quarantine zone",
        "clothing_guide": "survival gear: reinforced clothing, improvised armor, blood-stained clothes, military surplus",
        "cn_name": "丧尸末日",
    },
    "infinite_stream": {
        "visual_prefix": "OC, original character, not from any anime, multi-dimensional horror game setting, intense anime style",
        "setting_tags": "white void lobby, horror movie scenes, survival game arenas, shifting dimensions, point exchange shop",
        "clothing_guide": "versatile dark clothing, adaptable outfits, tactical casual, dimension-traveler gear",
        "cn_name": "无限流",
    },
}





class GeminiEngine:
    """Gemini 文本分析 + 图片生成引擎 (通过 MetaChat 中转) """

    def __init__(self):
        self.api_key = METACHAT_API_KEY
        self.base_url = GEMINI_BASE_URL
        self.text_model = GEMINI_TEXT_MODEL
        self.image_model = GEMINI_IMAGE_MODEL
        self.genre = None
        self.genre_style = GENRE_STYLES["modern_crime"]
        # 角色外貌缓存（核心：保证一致性）
        self.character_profiles = {}  # {name: "英文完整外貌描述"}
        print(f"[GeminiEngine] init text={self.text_model} image={self.image_model}")

    # ==================== 基础调用 ====================

    def _call_gemini(self, model, contents, temperature=0.7, max_tokens=16384):
        """调用 Gemini API（Google 原生格式）"""
        url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        result = response.json()
        # 检查是否被安全过滤
        if "candidates" not in result:
            block_reason = result.get("promptFeedback", {}).get("blockReason", "未知")
            print(f"  ⚠️ API返回无candidates, 原因: {block_reason}")
            print(f"  完整返回: {str(result)[:500]}")
            raise Exception(f"API返回无candidates: {block_reason}")
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text


    def _call_text(self, system_prompt, user_prompt, temperature=0.7, max_retries=6, max_tokens=16384):
        """封装调用：system + user 格式，增强重试 + PROHIBITED_CONTENT自动摘要化"""
        combined = f"{system_prompt}\n\n{user_prompt}"
        contents = [{"role": "user", "parts": [{"text": combined}]}]
        
        sanitize_level = 0  # 0=原文, 1=轻度净化, 2=摘要化
        
        for attempt in range(max_retries):
            try:
                return self._call_gemini(self.text_model, contents, temperature, max_tokens)
            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ['ssl', 'connection', 'timeout', 'eof', 'reset', 'broken pipe']):
                    wait = min(5 + attempt * 3, 20)
                    print(f"   ⚠ 网络错误 (第{attempt+1}次), {wait}秒后重试: {str(e)[:80]}")
                    time.sleep(wait)
                elif 'prohibited' in err_str or 'block' in err_str:
                    sanitize_level += 1
                    print(f"   🛡️ 内容安全拦截 (第{attempt+1}次), 净化等级提升到 {sanitize_level}")
                    if sanitize_level == 1:
                        # 轻度净化：替换敏感词
                        new_combined = self._sanitize_light(combined)
                        contents = [{"role": "user", "parts": [{"text": new_combined}]}]
                        print(f"   📝 轻度净化完成，重试中...")
                    elif sanitize_level == 2:
                        # 中度净化：删除小说原文，只保留摘要指令
                        new_combined = self._sanitize_medium(system_prompt, user_prompt)
                        contents = [{"role": "user", "parts": [{"text": new_combined}]}]
                        print(f"   📝 摘要化处理完成，重试中...")
                    else:
                        # 重度：极简prompt
                        new_combined = self._sanitize_heavy(system_prompt, user_prompt)
                        contents = [{"role": "user", "parts": [{"text": new_combined}]}]
                        print(f"   📝 极简化处理完成，重试中...")
                    time.sleep(2)
                else:
                    wait = 2
                    print(f"    ⚠️API错误（第{attempt+1}次）: {e}")
                    time.sleep(wait)
        print(f"   ❌ {max_retries}次重试均失败")
        return None

    def _sanitize_light(self, text):
        """轻度净化：替换高频敏感词为委婉表达"""
        import re
        replacements = {
            '杀': '击败', '杀死': '击倒', '杀了': '击倒了', '杀掉': '消灭',
            '死': '倒下', '死了': '倒下了', '死亡': '陨落',
            '血': '痕迹', '鲜血': '红色痕迹', '血迹': '痕迹', '血液': '液体',
            '尸体': '倒地的人', '尸': '遗体',
            '毒': '药', '毒药': '迷药', '下毒': '下药',
            '强奸': '伤害', '强暴': '伤害', '侵犯': '欺负',
            '炸弹': '装置', '爆炸': '冲击', '炸': '冲击',
            '枪': '武器', '开枪': '攻击', '子弹': '弹丸', '手枪': '武器',
            '刀': '利器', '捅': '刺', '砍': '击',
            '自杀': '离去', '上吊': '出事',
            '裸': '单薄衣着', '脱光': '衣衫不整',
        }
        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result

    def _sanitize_medium(self, system_prompt, user_prompt):
        """中度净化：将小说原文替换为简短梗概"""
        import re
        # 从user_prompt中提取小说文本部分，替换为梗概请求
        # 找到 [小说文本]: 后面的内容
        novel_match = re.search(r'\[小说文本\]:\s*\n(.+?)(\n\n(?:输出|必须|严格))', user_prompt, re.DOTALL)
        if novel_match:
            novel_text = novel_match.group(1)
            # 提取对话（保留对话，删除描述性暴力内容）
            dialogues = re.findall(r'[""「」『』]([^""「」『』]{2,50})[""「」『』]', novel_text)
            # 提取人名（常见中文名模式）
            names = re.findall(r'[\u4e00-\u9fff]{2,4}(?=说|道|喊|叫|笑|问|答|看|想)', novel_text)
            names = list(set(names))[:10]
            
            summary = f"【本段梗概】角色：{'、'.join(names[:5]) if names else '主角们'}。"
            if dialogues:
                safe_dialogues = [d for d in dialogues[:8] if not any(w in d for w in ['杀','死','血','毒','枪','炸'])]
                if safe_dialogues:
                    summary += "主要对话：" + "；".join(safe_dialogues[:5]) + "。"
            summary += "请根据以上信息完成任务，场景应体现紧张氛围和戏剧冲突，但避免直接暴力描写。"
            
            cleaned_prompt = user_prompt[:novel_match.start(1)] + summary + user_prompt[novel_match.end(1):]
            return f"{system_prompt}\n\n{cleaned_prompt}"
        
        # 如果没找到标记，直接截短
        if len(user_prompt) > 2000:
            user_prompt = user_prompt[:1000] + "\n...(内容已精简)...\n" + user_prompt[-500:]
        return f"{system_prompt}\n\n{user_prompt}"

    def _sanitize_heavy(self, system_prompt, user_prompt):
        """重度净化：只保留核心指令，去掉所有原文"""
        import re
        # 只保留system_prompt + 结构化指令部分
        # 去掉所有 [小说文本] 内容
        cleaned = re.sub(r'\[小说文本\]:\s*\n.*?(\n\n(?:输出|必须|严格))', 
                        r'\n[小说文本已省略，请生成一个通用的精彩场景]\n\1', 
                        user_prompt, flags=re.DOTALL)
        if cleaned == user_prompt:
            # 如果没匹配到，暴力截短
            cleaned = user_prompt[:800] + "\n...\n请根据以上要求生成内容。"
        return f"{system_prompt}\n\n{cleaned}"


    def _extract_json(self, text):
        """从文本中提取JSON - 增强版"""
        if not text:
            return None
        
        
        cleaned = text.strip()
        
        # 去掉markdown代码块: ```json ... ``` 或 ``` ... ```
        while cleaned.startswith('```'):
            # 去掉开头的 ```json 或 ```
            first_newline = cleaned.find('\n')
            if first_newline > 0:
                cleaned = cleaned[first_newline+1:]
            else:
                cleaned = cleaned[3:]
            # 去掉结尾的 ```
            if cleaned.rstrip().endswith('```'):
                cleaned = cleaned.rstrip()[:-3].rstrip()
            break
        
        # 尝试1: 直接解析
        try:
            return json.loads(cleaned)
        except:
            pass
        
        # 尝试2: 找第一个 { 或 [ 到最后一个 } 或 ]
        first_brace = -1
        last_brace = -1
        for i, c in enumerate(cleaned):
            if c in '{[':
                first_brace = i
                break
        
        if first_brace >= 0:
            open_char = cleaned[first_brace]
            close_char = '}' if open_char == '{' else ']'
            
            # 从后往前找对应的闭合
            for i in range(len(cleaned)-1, first_brace, -1):
                if cleaned[i] == close_char:
                    last_brace = i
                    break
            
            if last_brace > first_brace:
                json_str = cleaned[first_brace:last_brace+1]
                
                # 直接解析
                try:
                    result = json.loads(json_str)
                    if isinstance(result, list):
                        return result 
                    return result
                except:
                    pass
                
                # 修复常见错误: 尾部逗号
                fixed = re.sub(r',\s*}', '}', json_str)
                fixed = re.sub(r',\s*]', ']', fixed)
                try:
                    result = json.loads(fixed)
                    if isinstance(result, list):
                        return result
                    return result
                except:
                    pass
                
                # 如果JSON被截断（没有正确闭合），尝试补全
                try:
                    # 数一下未闭合的括号
                    open_braces = json_str.count('{') - json_str.count('}')
                    open_brackets = json_str.count('[') - json_str.count(']')
                    patched = json_str + '}' * open_braces + ']' * open_brackets
                    # 去掉最后一个不完整的对象（可能截断在中间）
                    patched = re.sub(r',\s*\{[^}]*$', '', patched)
                    patched = patched.rstrip().rstrip(',')
                    # 重新补全
                    open_braces = patched.count('{') - patched.count('}')
                    open_brackets = patched.count('[') - patched.count(']')
                    patched = patched + '}' * open_braces + ']' * open_brackets
                    result = json.loads(patched)
                    if isinstance(result, list):
                        return result 
                    return result
                except:
                    pass
        
        return None


    def detect_genre(self, text_sample):
        """用Gemini动态检测小说类型"""
        sample = text_sample[:1500]
        
        system_prompt = (
            "你是小说类型分析专家。分析给定的小说文本，判断其类型。\n"
            "输出JSON：\n"
            "{\n"
            '  "genre": "类型key",\n'
            '  "cn_name": "中文类型名",\n'
            '  "visual_prefix": "OC, original character, not from any anime, [风格描述], epic anime style",\n'
            '  "setting_tags": "场景标签1, 场景标签2, 场景标签3",\n'
            '  "clothing_guide": "服装描述1, 服装描述2"\n'
            "}\n"
            "genre可选值: modern_crime, scifi, wuxia, xianxia, xuanhuan, fantasy, urban, romance, "
            "historical_romance, military, horror, apocalypse, game_world, system_cheat, sports, "
            "school, historical, steampunk, cyberpunk, mecha, mythology, detective, survival, "
            "danmei_ancient, danmei_modern, farming_slice, transmigration, zombie, infinite_stream\n"
            "visual_prefix和setting_tags、clothing_guide必须是英文SD提示词风格的标签。"
        )
        
        user_prompt = f"小说文本：\n{episode_text}"
        result = self._call_text(system_prompt, user_prompt, temperature=0.3)
        data = self._extract_json(result)
        
        if data and "genre" in data:
            self.genre = data["genre"]
            self.genre_style = data
            print(f"  检测到类型: {data.get('cn_name', self.genre)}")
            return data["genre"]
        
        # fallback
        self.genre = "urban"
        self.genre_style = {
            "genre": "urban",
            "cn_name": "都市",
            "visual_prefix": "OC, original character, not from any anime, modern urban setting, anime style",
            "setting_tags": "modern city, apartments, offices, cafes",
            "clothing_guide": "modern casual: T-shirts, jeans, hoodies, dresses"
        }
        return "urban"


    # ==================== 角色提取 ====================

    def extract_characters(self, episode_text, existing_characters="", episode_num=1):
        """提取角色信息 - 带详细中英文外貌"""
        gs = self.genre_style

        system_prompt = (
            "你是Stable Diffusion提示词工程师，同时是角色设计师。\n"
            "任务：从小说文本中提取出场角色，为每个角色生成可直接用于SD出图的提示词。\n"
            "要求：\n"
            "1. 提示词必须是英文SD标签格式，用逗号分隔\n"
            "2. 性别必须明确：女性用1girl，男性用1boy，不得混淆\n"
            "3. 服装必须具体描述，不得裸体或暴露\n"
            "4. 提示词适合公开平台发布，不含任何NSFW内容\n"
            "5. appearance_en字段直接填写完整SD正向提示词标签\n"
            "6. 负向提示词sd_negative必须包含性别保护词\n\n"
            f"当前小说类型：{gs.get('cn_name', '都市')}\n"
            f"推荐服装风格：{gs.get('clothing_guide', 'modern casual clothing')}\n\n"
            "输出JSON格式：\n"
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "name": "角色姓名",\n'
            '      "gender": "male/female",\n'
            '      "age": "年龄描述",\n'
            '      "appearance_en": "1girl, long black hair, sharp brown eyes, white shirt, jeans, slim build, young woman",\n'
            '      "appearance_cn": "角色外貌中文描述",\n'
            '      "sd_negative": "male, 1boy, nude, nsfw, bad anatomy, extra limbs, watermark",\n'
            '      "personality": "性格描述",\n'
            '      "voice": "voice_type ID"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "5. voice须从以下选择（严格根据角色性别、年龄、性格气质匹配）：\n"
            "【中文女声】\n"
            "zh_female_tianmeixiaoyuan_uranus_bigtts（甜美小源-甜美温柔少女）\n"
            "zh_female_vv_uranus_bigtts（Vivi-活泼甜美）\n"
            "zh_female_sajiaoxuemei_uranus_bigtts（撒娇学妹-撒娇可爱）\n"
            "zh_female_linjianvhai_uranus_bigtts（邻家女孩-清新自然温柔）\n"
            "zh_female_xiaohe_uranus_bigtts（小何-温柔知性）\n"
            "zh_female_cancan_uranus_bigtts（知性灿灿-知性大方成熟女性）\n"
            "zh_female_shuangkuaisisi_uranus_bigtts（爽快思思-爽快干练御姐）\n"
            "zh_female_kefunvsheng_uranus_bigtts（暖阳女声-温暖阳光）\n"
            "zh_female_meilinvyou_uranus_bigtts（魅力女友-温柔魅力）\n"
            "zh_female_jitangnv_uranus_bigtts（鸡汤女-治愈温暖）\n"
            "zh_female_mizai_uranus_bigtts（咪仔-可爱俏皮）\n"
            "zh_female_tianmeitaozi_uranus_bigtts（甜美桃子-甜美少女）\n"
            "zh_female_qingxinnvsheng_uranus_bigtts（清新女声-清新文艺）\n"
            "zh_female_peiqi_uranus_bigtts（佩奇猪-梦莉童声）\n"
            "zh_female_xiaoxue_uranus_bigtts（儿童绘本-童真可爱）\n"
            "zh_female_liuchangnv_uranus_bigtts（流畅女声-流畅自然旁白）\n"
            "zh_female_yingyujiaoxue_uranus_bigtts（Tina老师-专业亲和）\n"
            "【中文男声】\n"
            "zh_male_shaonianzixin_uranus_bigtts（少年梓辛-少年清朗阳光）\n"
            "zh_male_ruyayichen_uranus_bigtts（儒雅逸辰-儒雅磁性霸总）\n"
            "zh_male_dayi_uranus_bigtts（大壹-沉稳大气旁白）\n"
            "zh_male_liufei_uranus_bigtts（刘飞-成熟稳重）\n"
            "zh_male_sunwukong_uranus_bigtts（猴哥-霸气张扬反派）\n"
            "zh_male_m191_uranus_bigtts（云舟-低沉磁性冷酷）\n"
            "zh_male_taocheng_uranus_bigtts（陶成-温润如玉斯文）\n"
            "zh_male_sophie_uranus_bigtts（魅力苏菲-独特魅力）\n"
            "6. name必须是小说中使用的原名\n"
            "7. 严格输出JSON格式"
        )


        user_prompt = f"小说文本：\n{episode_text}"
        print(f"   提取角色 (ep{episode_num})...")
        result = self._call_text(system_prompt, user_prompt, temperature=0.3)
        data = self._extract_json(result)

        if data:
            chars = data if isinstance(data, list) else data.get("items", [])
            # 兼容旧格式：如果只有appearance没有appearance_en
            for c in chars:
                if "appearance_en" not in c and "appearance" in c:
                    c["appearance_en"] = c["appearance"]
                    c["appearance_cn"] = c.get("appearance_cn", "")
                if not c.get("appearance_cn"):
                    c["appearance_cn"] = f"{c.get('name', '')}，{c.get('gender', '')}，{c.get('age', '')}岁"

                # 缓存角色外貌（用于图片生成时保持一致）
                name = c.get("name", "")
                if name and c.get("appearance_en"):
                    self.character_profiles[name] = c["appearance_en"]

            # ★ 验证Gemini输出的voice_type ID
                _voice = c.get("voice", "")
                from tts_engine import VOICE_LIBRARY, VOICE_MAP
                if _voice in VOICE_LIBRARY:
                    _label = VOICE_LIBRARY[_voice].get("label", _voice)
                    print(f"        🎤 {c.get('name','')} AI选音色：{_label} ({_voice})")
                elif _voice in VOICE_MAP:
                    c["voice"] = VOICE_MAP[_voice]
                    _label = VOICE_LIBRARY.get(VOICE_MAP[_voice], {}).get("label", _voice)
                    print(f"        🎤 {c.get('name','')} 标签映射：{_label} ({VOICE_MAP[_voice]})")
                else:
                    _p = c.get("personality", "")
                    _g = c.get("gender", "")
                    _av = _auto_match_voice(_g, _p)
                    c["voice"] = _av
            for c in chars:
                print(f"      {c.get('name')} ({c.get('gender')}) voice={c.get('voice')}")
            return chars
        else:
            print(f"   角色提取失败")
            return []

    def set_character_profiles(self, characters):
        """从角色列表设置外貌缓存（GUI调用）"""
        self.character_profiles = {}
        for c in characters:
            name = c.get("name", "")
            app_en = c.get("appearance_en", c.get("appearance", ""))
            if name and app_en:
                self.character_profiles[name] = app_en

    # ==================== 分镜生成 ====================


    # ==================== 分镜生成 v2.0 (分隔符+细粒度+上下文) ====================

    def generate_storyboard(self, episode_text, characters_summary="",
                            style="动漫风", episode_num=1, target_duration=90):
        gs = self.genre_style
        text_len = len(episode_text)
        target_scenes = max(8, int(text_len / 1000 * 14))
        target_scenes = min(target_scenes, 50)
        print(f"   文本={text_len}字 -> 目标{target_scenes}个分镜 (v2.0)")
        char_names = list(self.character_profiles.keys())
        if not char_names and characters_summary:
            import re as _re
            for line in characters_summary.split("\n"):
                match = _re.match(r"- (.+?)\(", line)
                if match:
                    char_names.append(match.group(1).strip())
        char_names_str = "、".join(char_names) if char_names else "主角"
        char_appearance_ref = ""
        outfit_dna = getattr(self, "_outfit_dna_cache", {})
        for name, app in self.character_profiles.items():
            outfit = outfit_dna.get(name, '')
            outfit_str = f' [固定服装: {outfit}]' if outfit else ''
            char_appearance_ref += f"  {name}: {app}{outfit_str}\n"
        appearance_ref = char_appearance_ref

        system_prompt = (
            "你是专业的分镜脚本作家兼Stable Diffusion提示词工程师。\n"
            "任务：将小说文本转化为分镜脚本，每个分镜必须包含完整的SD出图提示词。\n\n"
            "每个分镜必须包含以下字段：\n"
            "scene_type: dialogue/action/narration\n"
            "speaker: 说话角色名（旁白填narrator）\n"
            "dialogue: 台词或旁白内容（中文）\n"
            "emotion: angry/happy/sad/scared/calm/cold/whisper/shout/default\n"
            "camera: 镜头描述（如CLOSE UP/MEDIUM SHOT/WIDE SHOT）\n"
            "visual_description_en: 完整SD正向提示词，英文标签格式，必须包含：\n"
            "  - 人物：1girl/1boy + 外貌标签\n"
            "  - 场景：具体环境标签\n"
            "  - 情绪：对应表情标签\n"
            "  - 质量：masterpiece, best quality, vertical composition 9:16\n"
            "visual_description_cn: 场景的中文描述\n"
            "start_frame_description_en: 镜头起始画面SD提示词（英文标签）\n"
            "end_frame_description_en: 镜头结束画面SD提示词（英文标签）\n"
            "duration: 时长（秒，对话约3秒，动作场景约5秒）\n\n"
            f"当前类型：{gs.get('cn_name','都市')}\n"
            f"视觉风格：{gs.get('visual_prefix','anime style')}\n"
            f"场景标签参考：{gs.get('setting_tags','modern city')}\n\n"
            "角色外貌资料（直接复制标签到visual_description_en）：\n"
            f"{appearance_ref}\n\n"
            "严格输出分隔格式，每个分镜用===分隔，结尾加::OUTPUT_END::。\n"
            "不要用JSON！"
        )

        user_prompt = (
            f"[角色档案]\n{characters_summary}\n\n"
            f"[小说文本]:\n{episode_text[:10000]}\n\n"
            f"请生成{target_scenes}个分镜，每个分镜的visual_description_en必须是完整的SD提示词标签，覆盖全部内容！"
        )

        print(f"   生成分镜 v2.0 (ep{episode_num}, 目标{target_scenes}个)...")
        result = self._call_text(system_prompt, user_prompt, temperature=0.7, max_tokens=32768)
        if result:
            scenes = self._parse_storyboard_v2(result, gs)
            if scenes and len(scenes) >= 3:
                print(f"   ✅ 分隔符解析成功: {len(scenes)}个分镜")
                for s in scenes:
                     if not s.get("visual_description_en"):
                        s["visual_description_en"] = s.get("visual_description", "")
                s["visual_description"] = s.get("visual_description_en", "")
                data = {"episode": episode_num, "episode_title": f"Episode {episode_num}", "scenes": scenes}
                d = sum(1 for s in scenes if s.get("scene_type") == "dialogue")
                a = sum(1 for s in scenes if s.get("scene_type") == "action")
                n = sum(1 for s in scenes if s.get("scene_type") == "narration")
                print(f"   结果: {len(scenes)}分镜 ({d}对话+{a}动作+{n}旁白)")
                data = self.expand_storyboard_with_transitions(data)
                return data
        print(f"   ⚠ 分隔符失败，回退JSON...")
        return self._generate_storyboard_json_fallback(episode_text, characters_summary, style, episode_num, target_duration)

    def _parse_storyboard_v2(self, raw_text, gs):
        import re as _re
        content = raw_text
        if "_::~OUTPUT_START::~_" in content:
            content = content.split("_::~OUTPUT_START::~_", 1)[1]
        if "_::~OUTPUT_END::~_" in content:
            content = content.split("_::~OUTPUT_END::~_", 1)[0]
        content = content.strip()
        if not content:
            return []
        records = _re.split(r'\+\+\+', content)
        records = [r.strip() for r in records if r.strip()]
        valid_emotions = {"angry","happy","sad","scared","calm","cold","whisper","shout","default","excited","nervous","amazed","dramatic","epic"}
        scenes = []
        for record in records:
            fields = record.split("===")
            fields = [f.strip() for f in fields]
            if len(fields) < 8:
                continue
            try:
                scene_id = int(fields[0]) if fields[0].isdigit() else len(scenes)+1
            except:
                scene_id = len(scenes)+1
            scene_type = fields[1].strip().lower()
            if scene_type not in ("dialogue","action","narration"):
                scene_type = "action"
            speaker = fields[2].strip()
            dialogue = fields[3].strip()
            emotion = fields[4].strip().lower() if len(fields)>4 else "default"
            if emotion not in valid_emotions:
                emotion = "default"
            camera = fields[5].strip() if len(fields)>5 else "固定镜头"
            vis_cn = fields[6].strip() if len(fields)>6 else ""
            vis_en = fields[7].strip() if len(fields)>7 else ""
            start_en = fields[8].strip() if len(fields)>8 else vis_en
            end_en = fields[9].strip() if len(fields)>9 else vis_en
            dur = 3.0
            if len(fields)>10:
                try: dur = float(fields[10])
                except: pass
            if scene_type=="dialogue" and dialogue:
                dur = max(3.0, len(dialogue)/10*3)
            characters = []
            if speaker and speaker not in ("旁白","narrator"):
                characters.append(speaker)
            for name in self.character_profiles.keys():
                if name in (vis_cn or "") or name in (dialogue or ""):
                    if name not in characters:
                        characters.append(name)
            scenes.append({"scene_id":scene_id,"scene_type":scene_type,"speaker":speaker,"dialogue":dialogue,"emotion":emotion,"camera_movement":camera,"visual_description_cn":vis_cn,"visual_description_en":vis_en,"visual_description":vis_en,"start_frame_description_en":start_en,"end_frame_description_en":end_en,"characters":characters[:3],"duration":dur,"estimated_duration":dur})
        for idx,s in enumerate(scenes):
            s["scene_id"]=idx+1
        return scenes

    def _generate_storyboard_json_fallback(self, episode_text, characters_summary, style, episode_num, target_duration):
        gs = self.genre_style
        text_len = len(episode_text)
        min_s = max(5, text_len//500)
        max_s = min(max(8, text_len//200), 35)
        num_scenes = f"{min_s}~{max_s}"
        char_names = list(self.character_profiles.keys())
        if not char_names and characters_summary:
            import re as _re
            for line in characters_summary.split("\n"):
                match = _re.match(r"- (.+?)\(", line)
                if match:
                    char_names.append(match.group(1).strip())
        char_names_str = "、".join(char_names) if char_names else "主角"
        char_ref = ""
        outfit_dna = getattr(self, "_outfit_dna_cache", {})
        for name, app in self.character_profiles.items():
            outfit = outfit_dna.get(name, '')
            o = f' [OUTFIT: {outfit}]' if outfit else ''
            char_ref += f"  {name}: {app}{o}\n"
        system_prompt = (
            f"你是{gs['cn_name']}分镜导演兼SD提示词工程师。\n"
            f"角色资料：\n{char_ref}\n\n"
            f"speaker必须是：{char_names_str}\n旁白最多15%\n\n"
            "每个分镜必须包含：scene_id, scene_type, speaker, dialogue, emotion, "
            "camera_movement, visual_description_cn, visual_description_en(完整SD标签), "
            "start_frame_description_en, end_frame_description_en, duration\n"
            "visual_description_en必须是英文SD标签格式，包含1girl/1boy+外貌+场景+质量标签。\n"
            f"生成{num_scenes}个场景JSON。"
        )

        user_prompt = (
            f"第{episode_num}集->{num_scenes}个场景。\n"
            f"[角色]\n{characters_summary}\n"
            f"[文本]:\n{episode_text[:8000]}\n覆盖整章！输出JSON。"
        )

        print(f"   [JSON回退] ep{episode_num}, {num_scenes}场景...")
        result = self._call_text(system_prompt, user_prompt, temperature=0.7)
        data = self._extract_json(result)
        if data and isinstance(data, list):
            data = {"scenes": data}
        if data and "scenes" in data:
            scenes = data["scenes"]
            for idx,s in enumerate(scenes):
                if "scene_id" not in s: s["scene_id"]=idx+1
                s['duration']=3.0
                if "visual_description_en" not in s:
                    s["visual_description_en"]=s.get("visual_description",f"{gs['visual_prefix']},dramatic scene,{gs['setting_tags']},masterpiece,best quality,vertical composition 9:16")
                if "visual_description_cn" not in s: s["visual_description_cn"]=""
          # 直接使用Gemini生成的SD提示词
                s["visual_description"]=s["visual_description_en"]
                if "camera_movement" not in s: s["camera_movement"]="固定镜头"
                for fld in ["start_frame_description_en","end_frame_description_en"]:
                    if fld not in s: s[fld]=s.get("visual_description_en","")
            data["scenes"]=scenes
            data["episode"]=episode_num
            data["episode_title"]=f"Episode {episode_num}"
            data=self.expand_storyboard_with_transitions(data)
            return data
        return self._fallback_storyboard(episode_text, episode_num, char_names)

    def _enrich_prompt_with_characters(self, prompt, character_names):
        if not character_names or not self.character_profiles:
            return prompt
        outfit_dna = getattr(self, '_outfit_dna_cache', {})
        parts_list = []
        for name in character_names[:2]:
            parts = []
            profile = self.character_profiles.get(name, "")
            if profile:
                w = profile.split()
                parts.append(" ".join(w[:50]) if len(w)>50 else profile)
            outfit = outfit_dna.get(name, "")
            if outfit:
                parts.append(f"wearing {outfit}")
            if parts:
                parts_list.append(", ".join(parts))
        if not parts_list:
            return prompt
        char_desc = " ; ".join(parts_list)
        ins = None
        for mk in ['. ', ', ']:
            idx = prompt.find(mk)
            if idx > 10:
                ins = idx + len(mk)
                break
        if ins and ins < len(prompt)-20:
            prompt = prompt[:ins] + f"[CHARACTER: {char_desc}] " + prompt[ins:]
        else:
            prompt = prompt.rstrip(". ,") + f", {char_desc}"
        w = prompt.split()
        if len(w)>200: prompt=" ".join(w[:190])
        if "masterpiece" not in prompt.lower():
            prompt += ", masterpiece, best quality, vertical composition 9:16"
        return prompt

    def _extract_key_features(self, full_profile):
        if not full_profile:
            return ""
        import re as _re
        text = full_profile.lower()
        parts = []
        am = _re.search(r'(young|middle-aged|old|elderly|teenage)\s+(man|woman|male|female)', text)
        if am: parts.append(am.group(0))
        elif 'male' in text or 'man' in text: parts.append('a man')
        elif 'female' in text or 'woman' in text: parts.append('a woman')
        hm = _re.search(r'(?:with\s+)?(?:(?:short|long|medium|shoulder-length|messy|neat|spiky|slicked-back|flowing|cropped)\s+)?(?:(?:black|brown|blonde|red|white|grey|silver|dark|light)\s+)?hair', text)
        if hm: parts.append(hm.group(0).strip())
        for feat in ['mask','glasses','scar','eyepatch','tattoo','beard','cigarette']:
            if feat in text:
                fm = _re.search(r'[\w\s-]*'+feat+r'[\w\s]*', text)
                if fm: parts.append(fm.group(0).strip()[:25])
                break
        for b in ['tall','slender','muscular','athletic','petite','slim']:
            if b in text: parts.append(b); break
        return ", ".join(parts) if parts else full_profile[:60]

    def set_outfit_dna_cache(self, outfit_dna: dict):
        self._outfit_dna_cache = outfit_dna
        if outfit_dna:
            print(f"[GeminiEngine] 已加载 {len(outfit_dna)} 个角色固定服装DNA")

    def _fallback_storyboard(self, text, episode_num, char_names):
        import re as _re
        gs = self.genre_style
        dc = char_names[0] if char_names else "主角"
        dp = self.character_profiles.get(dc, "a person")
        scenes = []
        sid = 1
        dlgs = _re.findall(r'\u201c([^\u201d]{2,50})\u201d', text)
        if not dlgs: dlgs = _re.findall(r'"([^"]{2,50})"', text)
        ci = 0
        for dlg in dlgs[:20]:
            sp = char_names[ci%len(char_names)] if char_names else dc
            sp_p = self.character_profiles.get(sp, dp)
            ci += 1
            v = f"{gs['visual_prefix']}, MEDIUM SHOT, {sp_p}, talking, {gs['setting_tags']}, dramatic lighting, masterpiece, best quality, vertical composition 9:16"
            scenes.append({"scene_id":sid,"scene_type":"dialogue","speaker":sp,"dialogue":dlg[:25],"visual_description_en":v,"visual_description_cn":f"中景，{sp}说话","visual_description":v,"start_frame_description_en":v,"end_frame_description_en":v,"characters":[sp],"emotion":"default","camera_movement":"固定镜头","duration":3.0,"estimated_duration":3.0})
            sid += 1
            if sid%3==0:
                v2 = f"{gs['visual_prefix']}, WIDE SHOT, {dp}, {gs['setting_tags']}, masterpiece, best quality, vertical composition 9:16"
                scenes.append({"scene_id":sid,"scene_type":"action","speaker":"","dialogue":"","visual_description_en":v2,"visual_description_cn":f"远景，{dc}动作","visual_description":v2,"start_frame_description_en":v2,"end_frame_description_en":v2,"characters":[dc],"emotion":"default","camera_movement":"镜头拉远","duration":3.0,"estimated_duration":3.0})
                sid += 1
        if not scenes:
            v3 = f"{gs['visual_prefix']}, establishing shot, {gs['setting_tags']}, masterpiece, vertical composition 9:16"
            scenes = [{"scene_id":1,"scene_type":"action","speaker":"","dialogue":"","visual_description_en":v3,"visual_description_cn":"建立镜头","visual_description":v3,"start_frame_description_en":v3,"end_frame_description_en":v3,"characters":[dc],"camera_movement":"镜头拉远","duration":3.0,"estimated_duration":3.0}]
        return {"episode":episode_num,"episode_title":f"Episode {episode_num}","scenes":scenes}


    # ==================== 中英文翻译 ====================

    def translate_cn_to_en(self, chinese_text):
        """中文描述翻译为英文prompt"""
        gs = self.genre_style
        system_prompt = (
            f"你是AI绘图提示词翻译专家。\n"
            f"将中文图片描述翻译为英文AI绘图prompt。\n"
            f"要求：\n"
            f"1. 保持所有外貌细节\n"
            f"2. 以 '{gs['visual_prefix']}' 开头\n"
            f"3. 以 'masterpiece, best quality, vertical composition 9:16' 结尾\n"
            f"4. 只输出翻译结果，不要其他内容\n"
            f"5. 控制在100词以内"
        )
        result = self._call_text(system_prompt, chinese_text, temperature=0.3)
        if result:
            clean = result.strip().strip('"').strip("'")
            if "original character" not in clean.lower():
                clean = gs["visual_prefix"] + ", " + clean
            if "masterpiece" not in clean.lower():
                clean += ", masterpiece, best quality, vertical composition 9:16"
            return clean
        return None

    def translate_en_to_cn(self, english_text):
        """英文prompt翻译为中文描述"""
        system_prompt = (
            f"将以下英文AI绘图提示词翻译为中文。\n"
            f"要求：简洁明了，保留关键信息（角色外貌、动作、场景、光影）。\n"
            f"只输出翻译结果。"
        )
        result = self._call_text(system_prompt, english_text, temperature=0.3)
        if result:
            return result.strip().strip('"').strip("'")
        return ""

    # ==================== 图片生成（Nano Banana 2）====================


    # ================================================================
    #  链式帧生成：基于上一帧图片 + 下一场景描述 → 生成下一帧
    # ================================================================
    def generate_next_frame(self, prev_frame_path, next_scene_prompt, save_path,
                            style_prefix="", character_ref_paths=None):
        """链式帧生成：基于上一帧图片 + 下一场景描述 → 生成下一帧
        
        核心方案：帧序列 A→B→C→D 链式生成
        每张图基于上一张图+新prompt生成，保证像素级场景连续性
        """
        full_prompt = (
            f"You are generating the NEXT FRAME in a cinematic sequence. "
            f"Style: {style_prefix if style_prefix else 'cinematic, detailed, dramatic lighting'}. "
            f"Aspect ratio: 9:16 vertical (1080x1920). "
            f"The provided image is the CURRENT frame. Generate the NEXT frame showing: "
            f"{next_scene_prompt}. "
            f"CRITICAL: Maintain VISUAL CONTINUITY with the provided image - "
            f"same art style, consistent lighting, same color palette, same character designs. "
            f"The output should look like a natural cinematic progression from the input image. "
            f"Requirements: No text, no watermarks, no letters, no words on image. "
            f"High detail, professional quality, consistent character design."
        )
        
        # 构建 parts
        import base64 as _b64
        parts = []
        
        # 1. 上一帧图片（作为当前帧参考）
        try:
            with open(prev_frame_path, "rb") as _f:
                _img_bytes = _f.read()
            _ext = os.path.splitext(prev_frame_path)[1].lower()
            _mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "webp": "image/webp"}.get(_ext.lstrip("."), "image/png")
            _b64_data = _b64.b64encode(_img_bytes).decode("utf-8")
            parts.append({"inlineData": {"mimeType": _mime, "data": _b64_data}})
            print(f"  [REF] 上一帧: {prev_frame_path} ({_mime}, {len(_img_bytes)//1024}KB)")
        except Exception as _e:
            print(f"  [X] 读取上一帧失败: {prev_frame_path} - {_e}")
            return None
        
        # 2. 角色参考图（可选，保持角色一致性）
        if character_ref_paths:
            for _ref_path in character_ref_paths[:2]:
                try:
                    if os.path.exists(_ref_path):
                        with open(_ref_path, "rb") as _f:
                            _ref_bytes = _f.read()
                        _ref_ext = os.path.splitext(_ref_path)[1].lower()
                        _ref_mime = {"png": "image/png", "jpg": "image/jpeg",
                                     "jpeg": "image/jpeg", "webp": "image/webp"}.get(
                                     _ref_ext.lstrip("."), "image/png")
                        _ref_b64 = _b64.b64encode(_ref_bytes).decode("utf-8")
                        parts.append({"inlineData": {"mimeType": _ref_mime, "data": _ref_b64}})
                except Exception:
                    pass
        
        # 3. 文字prompt
        parts.append({"text": full_prompt})
        
        # 调用 Gemini API
        url = f"{self.base_url}/v1beta/models/{self.image_model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        headers = {"Content-Type": "application/json"}
        
        for attempt in range(5):
            try:
                import datetime
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔗 链式帧生成请求... (attempt {attempt+1}/5)")
                print(f"  prompt长度: {len(full_prompt)} 字符")
                response = requests.post(url, headers=headers, json=payload, timeout=(30, 600))
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ 收到响应 status={response.status_code}")
                response.raise_for_status()
                result = response.json()
                # 检查是否被安全过滤
                if "candidates" not in result:
                    block_reason = result.get("promptFeedback", {}).get("blockReason", "未知")
                    print(f"  ⚠️ API返回无candidates, 原因: {block_reason}")
                    print(f"  完整返回: {str(result)[:500]}")
                    raise Exception(f"API返回无candidates: {block_reason}")
                
                for part in result["candidates"][0]["content"]["parts"]:
                    if "inlineData" in part:
                        image_data = part["inlineData"]["data"]
                        import base64
                        image_bytes = base64.b64decode(image_data)
                        
                        mime_type = part["inlineData"]["mimeType"]
                        ext = ".png"
                        if "jpeg" in mime_type or "jpg" in mime_type:
                            ext = ".jpg"
                        elif "webp" in mime_type:
                            ext = ".webp"
                        
                        if not save_path.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            save_path = save_path + ext
                        
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(image_bytes)
                        
                        print(f"  [✓] 链式帧已保存: {save_path}")
                        return save_path
                
                print(f"  [X] 响应中未找到图片数据")
                return None
                
            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ['ssl', 'connection', 'timeout', 'eof', 'reset']):
                    wait = 5 * attempt + 3
                    print(f"  [⚠] 链式帧生成网络错误（第{attempt+1}次），{wait}秒后重试...")
                    time.sleep(wait)
                else:
                    print(f"  [X] 链式帧生成失败: {e}")
                    if attempt < 4:
                        time.sleep(2)
        
        print(f"  [X] 链式帧5次重试均失败")
        return None


    def generate_image(self, prompt, save_path, style_prefix="", reference_image_paths=None):
        """使用 Gemini 3.1 Flash Image 生成图片，带重试"""
        # ★ 精简prompt，避免过长导致模型注意力分散
        style = style_prefix if style_prefix else 'cinematic anime style'
        
        # prompt超过120词则截断核心部分
        words = prompt.split()
        if len(words) > 200:
            prompt = " ".join(words[:180])
        
        full_prompt = (
            f"{prompt}. "
            f"Style: {style}. Vertical 9:16. "
            f"No text, no watermarks, no words on image."
        )

        # 参考图：简短指令，避免冗长描述分散注意力
        if reference_image_paths:
            ref_instruction = (
                "CRITICAL: The character must look EXACTLY like the reference image - "
                "same face, same hair, same clothing. "
            )
            full_prompt = ref_instruction + full_prompt

        url = f"{self.base_url}/v1beta/models/{self.image_model}:generateContent?key={self.api_key}"
        # 构建 parts (支持参考图)
        parts = [{"text": full_prompt}]
        if reference_image_paths:
            import base64 as _b64
            for _ref_path in reference_image_paths:
                try:
                    import os as _os
                    if _os.path.exists(_ref_path):
                        with open(_ref_path, "rb") as _f:
                            _img_bytes = _f.read()
                        _ext = _os.path.splitext(_ref_path)[1].lower()
                        _mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(_ext.lstrip("."), "image/png")
                        _b64_data = _b64.b64encode(_img_bytes).decode("utf-8")
                        parts.append({"inlineData": {"mimeType": _mime, "data": _b64_data}})
                        print(f"  [REF] 已附加参考图：{_ref_path} ({_mime}, {len(_img_bytes)//1024}KB)")
                except Exception as _e:
                    print(f"  [REF] 读取参考图失败：{_ref_path} — {_e}")

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        headers = {"Content-Type": "application/json"}

        for attempt in range(5):
            try:
                import datetime
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🌐 发送图片生成请求... (attempt {attempt+1}/5)")
                print(f"    prompt长度: {len(full_prompt)} 字符")
                print(f"    prompt内容：{full_prompt}")
                print(f"    URL: {url[:80]}...")
                response = requests.post(url, headers=headers, json=payload, timeout=(30, 600))
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ 收到响应 status={response.status_code}, len={len(response.content)}")
                response.raise_for_status()
                result = response.json()
                # 检查是否被安全过滤
                if "candidates" not in result:
                    block_reason = result.get("promptFeedback", {}).get("blockReason", "未知")
                    print(f"  ⚠️ API返回无candidates, 原因: {block_reason}")
                    print(f"  完整返回: {str(result)[:500]}")
                    raise Exception(f"API返回无candidates: {block_reason}")

                for part in result["candidates"][0]["content"]["parts"]:
                    if "inlineData" in part:
                        image_data = part["inlineData"]["data"]
                        mime_type = part["inlineData"]["mimeType"]

                        ext = ".png"
                        if "jpeg" in mime_type or "jpg" in mime_type:
                            ext = ".jpg"
                        elif "webp" in mime_type:
                            ext = ".webp"

                        if not save_path.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            save_path = save_path + ext

                        image_bytes = base64.b64decode(image_data)
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        with open(save_path, "wb") as f:
                            f.write(image_bytes)

                        print(f"[✓] 图片已保存: {save_path}")
                        return save_path

                print(f"[✗] 响应中未找到图片数据")
                return None

            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ['ssl', 'connection', 'timeout', 'eof', 'reset']):
                    wait = 5 + attempt * 3
                    print(f"[⚠] 图片生成网络错误 (第{attempt+1}次), {wait}秒后重试...")
                    time.sleep(wait)
                else:
                    print(f"[✗] 图片生成失败: {e}")
                    if attempt < 4:
                        time.sleep(2)

        print(f"[✗] 图片生成5次重试均失败")
        return None


    def generate_image_candidates(self, prompt, save_dir, base_name, count=3, style_prefix='', reference_image_paths=None):
        """生成多张候选图片，返回路径列表"""
        import time
        candidates = []
        for i in range(count):
            save_path = os.path.join(save_dir, f"{base_name}_candidate_{i+1}")
            print(f"  生成候选图 {i+1}/{count} ...")
            result_path = self.generate_image(prompt, save_path, style_prefix, reference_image_paths=reference_image_paths)
            if result_path:
                candidates.append(result_path)
            time.sleep(2)
        return candidates


    # === 运镜中文→英文映射 (供视频prompt使用) ===
    CAMERA_MOVEMENT_MAP = {
        "固定镜头": "static camera, locked shot",
        "缓慢推进": "camera slowly pushes in, dolly in",
        "缓慢拉远": "camera slowly pulls back, dolly out",
        "镜头拉近": "camera zooms in, push in",
        "镜头拉远": "camera zooms out, pull out",
        "向左平移": "camera pans left, lateral pan",
        "向右平移": "camera pans right, lateral pan",
        "向上平移": "camera tilts up, tilt up",
        "向下平移": "camera tilts down, tilt down",
        "跟随镜头": "camera follows subject, tracking shot",
        "环绕镜头": "camera orbits around subject, orbital shot",
        "航拍镜头": "aerial shot, drone shot, bird eye view",
        "航拍俯冲": "aerial dive, drone descending",
        "手持镜头": "handheld camera, slight shake",
        "镜头摇晃": "camera shake, shaky cam",
        "旋转镜头": "camera rotates, spinning shot",
        "特写推进": "extreme close-up push in, macro dolly",
        "升降镜头": "crane shot, camera rises",
    }

    def _get_camera_en(self, camera_cn):
        """将中文运镜转为英文prompt片段"""
        if not camera_cn:
            return "smooth camera movement"
        # 精确匹配
        if camera_cn in self.CAMERA_MOVEMENT_MAP:
            return self.CAMERA_MOVEMENT_MAP[camera_cn]
        # 模糊匹配
        for key, val in self.CAMERA_MOVEMENT_MAP.items():
            if key in camera_cn or camera_cn in key:
                return val
        # 如果是英文直接返回
        if any(c.isascii() and c.isalpha() for c in camera_cn):
            return camera_cn
        return "smooth camera movement"

    def generate_single_video_prompt(self, scene):
        """为单个场景生成视频运动prompt"""
        desc_cn = scene.get("visual_description_cn", "")
        dialogue = scene.get("dialogue", "")
        emotion = scene.get("emotion", "default")
        scene_type = scene.get("scene_type", "")
        speaker = scene.get("speaker", "")
        camera_movement = scene.get("camera_movement", "固定镜头")

        scene_text = (
            f"[{scene_type}]: {desc_cn[:60]}"
            f" | speaker={speaker} dialogue={dialogue[:20]}"
            f" | emotion={emotion}"
        )

        system_prompt = """你是AI视频运动描述专家。为一个场景生成即梦AI视频prompt（英文）。

要求：
1. 人物动作：walking, turning head, speaking with subtle lip movement, gesturing等
2. 镜头运动：Camera slowly pushes in / pans left / tracking shot等
3. 环境动态：wind in hair, light shifting, rain drops等
4. 质量词：Cinematic, shallow depth of field, film grain, 8K
5. 每个prompt 40-60个英文单词
6. 安全规则：禁止暴力/血腥/死亡/武器/色情词汇，用委婉词替代
7. 情绪匹配：sad→slow camera / angry→quick movement / calm→static

直接输出prompt文本，不要JSON格式，不要换行。"""

        user_prompt = f"场景信息：\n{scene_text}\n\n为这个场景生成视频运动prompt，直接输出英文prompt文本。"

        print(f"\n 🎬 [Gemini] 为场景生成视频运动prompt...")

        result = self._call_text(system_prompt, user_prompt, temperature=0.7)

        if result:
            # 清理结果，去掉可能的引号和多余格式
            prompt = result.strip().strip('"').strip("'").strip()
            # 如果返回了多行，只取第一行有效内容
            lines_result = [l.strip() for l in prompt.split("\n") if l.strip()]
            if lines_result:
                prompt = lines_result[0]
            print(f"  ✅ prompt: {prompt[:60]}...")
            return prompt
        else:
            # fallback
            desc = scene.get("start_frame_description_en", "") or scene.get("visual_description_en", "") or desc_cn
            return f"Cinematic shot, {desc[:200]}, {self._get_camera_en(camera_movement)}, professional lighting, 8K quality, shallow depth of field"

    def generate_video_prompts(self, script):
        """为每个场景生成即梦专用的视频运动prompt（修复版：使用REST API）"""
        scenes = script.get("scenes", [])
        if not scenes:
            return []

        # 构建场景信息（精简版，减少token消耗）
        scene_texts = []
        for i, s in enumerate(scenes):
            desc_cn = s.get("visual_description_cn", "")
            dialogue = s.get("dialogue", "")
            emotion = s.get("emotion", "default")
            scene_type = s.get("scene_type", "")
            speaker = s.get("speaker", "")
            camera_movement = s.get("camera_movement", "固定镜头")
            scene_texts.append(
                f"Scene {i+1} [{scene_type}]: {desc_cn[:60]}"
                f" | speaker={speaker} dialogue={dialogue[:20]}"
                f" | emotion={emotion}"
                f" | camera={camera_movement}"
            )

        all_scenes = "\n".join(scene_texts)

        system_prompt = """你是AI视频运动描述专家。为每个场景生成即梦AI视频prompt（英文）。

要求：
1. 人物动作：walking, turning head, speaking with subtle lip movement, gesturing等
2. 镜头运动：Camera slowly pushes in / pans left / tracking shot等
3. 环境动态：wind in hair, light shifting, rain drops等
4. 质量词：Cinematic, shallow depth of field, film grain, 8K
5. 每个prompt 40-60个英文单词
6. 安全规则：禁止暴力/血腥/死亡/武器/色情词汇，用委婉词替代
7. 情绪匹配：sad→slow camera / angry→quick movement / calm→static

严格输出JSON数组：
[{"scene_id": 1, "video_prompt": "..."}, ...]"""

        user_prompt = f"场景列表:\n{all_scenes}\n\n为每个场景生成视频运动prompt，输出JSON。"

        print(f"\n🎬 [Gemini] 为 {len(scenes)} 个场景生成视频运动prompt...")

        result = self._call_text(system_prompt, user_prompt, temperature=0.7)
        data = self._extract_json(result)

        if data:
            items = data if isinstance(data, list) else data.get("items", [])
            prompt_map = {}
            for item in items:
                sid = item.get("scene_id", 0)
                vp = item.get("video_prompt", "")
                prompt_map[sid] = vp

            video_prompts = []
            for i, s in enumerate(scenes):
                sid = s.get("scene_id", i + 1)
                vp = prompt_map.get(sid, "")
                if not vp:
                    desc = s.get("visual_description_en", "dramatic scene")[:80]
                    vp = f"Cinematic shot, {desc}, {self._get_camera_en(s.get('camera_movement', '固定镜头'))}, professional lighting, 8K quality, shallow depth of field"
                video_prompts.append(vp)
                print(f"  场景{sid}: {vp[:60]}...")

            print(f"✅ 视频prompt生成完成：{len(video_prompts)} 个")
            return video_prompts
        else:
            print(f"❌ JSON解析失败，使用fallback")
            return self._fallback_video_prompts(scenes)

    def _fallback_video_prompts(self, scenes):
        """视频prompt的fallback方案"""
        prompts = []
        for s in scenes:
            desc = s.get("visual_description_en", "dramatic scene")[:80]
            emotion = s.get("emotion", "default")
            scene_type = s.get("scene_type", "action")

            # 根据场景类型和情绪选择镜头运动
            if scene_type == "dialogue":
                camera = "Camera slowly pushes in on the character, subtle facial expressions"
            elif emotion in ("angry", "shout"):
                camera = "Quick camera movement, dynamic angle, intense atmosphere"
            elif emotion in ("sad", "calm"):
                camera = "Slow dolly shot, gentle camera drift, melancholic atmosphere"
            else:
                camera = "Smooth tracking shot, cinematic camera movement"

            vp = f"{camera}, {desc}, shallow depth of field, film grain, cinematic lighting, 8K photorealistic quality"
            prompts.append(vp)
        return prompts


    def generate_scene_images(self, script, style_prefix=""):
        """批量生成一集的所有场景图片"""
        episode_num = script.get("episode", 0)
        scenes = script.get("scenes", [])
        results = []
        
        # P2: 场景库 - 相同location复用首张生成图作为参考
        _location_cache = {}  # {location_name: image_path}

        for scene in scenes:
            scene_id = scene.get("scene_id", 0)
            # 优先用英文prompt
            image_prompt = scene.get("visual_description_en",
                                     scene.get("visual_description",
                                               scene.get("image_prompt", "")))

            save_path = os.path.join(IMAGES_DIR, f"ep{episode_num:03d}_scene{scene_id:03d}")

            print(f"\n[生成] 第{episode_num}集 场景{scene_id}...")
            # === 自动查找角色定妆照作为参考图 ===
            _ref_paths = []
            if hasattr(self, "character_profiles") and self.character_profiles:
                _char_names = scene.get("characters", [])
                _char_mgr = self.character_profiles
                if hasattr(_char_mgr, "get_scene_reference_images"):
                    _ref_paths = _char_mgr.get_scene_reference_images(_char_names)
                    if _ref_paths:
                        print(f"    📎 附加 {len(_ref_paths)} 张角色参考图")
                # 查找场景背景参考图
                if hasattr(_char_mgr, "get_background"):
                    _location = scene.get("location", "")
                    if _location:
                        _bg = _char_mgr.get_background(_location)
                        if _bg:
                            _ref_paths.append(_bg)
                            print(f"    🏞️ 附加场景背景参考图: {_location}")

            # P2: 场景库 - 从缓存中获取同场景已生成的图作为额外参考
            _loc = scene.get("location", "")
            if _loc and _loc in _location_cache:
                _cached_img = _location_cache[_loc]
                if _cached_img and os.path.exists(_cached_img):
                    if _ref_paths is None:
                        _ref_paths = []
                    if _cached_img not in _ref_paths:
                        _ref_paths.append(_cached_img)
                        print(f"    🔄 P2场景复用: {_loc} -> {os.path.basename(_cached_img)}")

            result = self.generate_image(image_prompt, save_path, style_prefix, reference_image_paths=_ref_paths if _ref_paths else None)
            results.append({
                "scene_id": scene_id,
                "image_path": result,
                "success": result is not None
            })
            
            # P2: 场景库 - 缓存成功生成的图到location
            if result and _location and _location not in _location_cache:
                _location_cache[_location] = result
                print(f"    📌 P2场景缓存: {_location}")
            
            time.sleep(2)

        success_count = sum(1 for r in results if r["success"])
        print(f"\n[统计] 第{episode_num}集: {success_count}/{len(scenes)} 张图片生成成功")
        return results

    def generate_single_image(self, prompt_en, save_path, style_prefix="", reference_image_paths=None):
        """单张图片生成（GUI用）"""
        return self.generate_image(prompt_en, save_path, style_prefix, reference_image_paths=reference_image_paths)



    # ================================================================
    #  链式帧序列生成（核心方案）
    # ================================================================
    def generate_scene_frames_chain(self, script, save_dir, style_prefix="",
                                     char_mgr=None, progress_callback=None):
        """链式帧序列生成：为整集生成 N+1 张帧图
        
        核心方案提醒：
        N个场景 → N+1张帧图 → N段视频
        帧1 = 场景1 visual_description_en（纯prompt生成首帧）
        帧k+1 = 帧k + 场景k end_frame_description_en → 链式生成
        视频k = 帧k → 帧k+1（首尾帧视频）
        
        Returns: list of frame paths, length = len(scenes) + 1
        """
        episode_num = script.get("episode", 0)
        scenes = script.get("scenes", [])
        if not scenes:
            return []
        
        os.makedirs(save_dir, exist_ok=True)
        frame_sequence = []
        total_frames = len(scenes) + 1
        
        # P3: 链式生成也使用场景缓存
        _chain_location_cache = {}
        
        def _progress(msg):
            if progress_callback:
                progress_callback(msg)
            print(msg)
        
        def _get_ref_paths(scene):
            """获取角色参考图"""
            ref_paths = []
            if char_mgr and hasattr(char_mgr, 'get_scene_reference_images'):
                try:
                    char_names = scene.get("characters", [])
                    ref_paths = char_mgr.get_scene_reference_images(char_names)
                except:
                    pass
            return ref_paths
        
        # === 帧1：纯prompt生成（场景1的起始画面）===
        scene_0 = scenes[0]
        prompt_0 = scene_0.get("visual_description_en",
                               scene_0.get("visual_description",
                               scene_0.get("image_prompt", "")))
        save_path_0 = os.path.join(save_dir, f"ep{episode_num:03d}_frame001")
        
        # 检查是否已存在
        existing_0 = None
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            p = save_path_0 + ext
            if os.path.exists(p):
                existing_0 = p
                break
        
        if existing_0:
            _progress(f"[帧1/{total_frames}] ⏭ 已存在: {os.path.basename(existing_0)}")
            frame_sequence.append(existing_0)
        else:
            _progress(f"[帧1/{total_frames}] 🎨 首帧生成（纯prompt）...")
            ref_paths_0 = _get_ref_paths(scene_0)
            result_0 = self.generate_image(prompt_0, save_path_0, style_prefix,
                                           reference_image_paths=ref_paths_0 if ref_paths_0 else None)
            if result_0:
                frame_sequence.append(result_0)
                _progress(f"[帧1/{total_frames}] ✅ {os.path.basename(result_0)}")
            else:
                _progress(f"[帧1/{total_frames}] ❌ 首帧生成失败")
                frame_sequence.append(None)
                return frame_sequence  # 首帧都失败了，后续无法链式生成
        
        # === 帧2 到 帧N+1：链式生成 ===
        for i, scene in enumerate(scenes):
            frame_idx = i + 2  # 帧编号从1开始
            save_path_i = os.path.join(save_dir, f"ep{episode_num:03d}_frame{frame_idx:03d}")
            
            # 检查是否已存在
            existing_i = None
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                p = save_path_i + ext
                if os.path.exists(p):
                    existing_i = p
                    break
            
            if existing_i:
                _progress(f"[帧{frame_idx}/{total_frames}] ⏭ 已存在: {os.path.basename(existing_i)}")
                frame_sequence.append(existing_i)
                continue
            
            # 使用该场景的 end_frame_description_en
            end_desc = scene.get("end_frame_description_en", "")
            if not end_desc:
                end_desc = scene.get("visual_description_en",
                                     scene.get("visual_description", ""))
            
            prev_frame = frame_sequence[-1]
            if prev_frame is None:
                _progress(f"[帧{frame_idx}/{total_frames}] ⚠ 上一帧为空，尝试纯prompt生成...")
                ref_paths_i = _get_ref_paths(scene)
                result_i = self.generate_image(end_desc, save_path_i, style_prefix,
                                               reference_image_paths=ref_paths_i if ref_paths_i else None)
            else:
                _progress(f"[帧{frame_idx}/{total_frames}] 🔗 链式生成（基于帧{frame_idx-1}）...")
                ref_paths_i = _get_ref_paths(scene)
                
                # P3: 场景缓存 - 同location复用参考图
                _loc_i = scene.get("location", "")
                if _loc_i and _loc_i in _chain_location_cache:
                    _cached = _chain_location_cache[_loc_i]
                    if _cached and os.path.exists(_cached):
                        if ref_paths_i is None:
                            ref_paths_i = []
                        if _cached not in ref_paths_i:
                            ref_paths_i.append(_cached)
                
                result_i = self.generate_next_frame(prev_frame, end_desc, save_path_i,
                                                     style_prefix, character_ref_paths=ref_paths_i)
            
            if result_i:
                frame_sequence.append(result_i)
                _progress(f"[帧{frame_idx}/{total_frames}] ✅ {os.path.basename(result_i)}")
                # P3: 缓存到场景库
                _loc_cache = scene.get("location", "")
                if _loc_cache and _loc_cache not in _chain_location_cache:
                    _chain_location_cache[_loc_cache] = result_i
            else:
                _progress(f"[帧{frame_idx}/{total_frames}] ❌ 生成失败，尝试纯prompt回退...")
                fallback = self.generate_image(end_desc, save_path_i, style_prefix)
                if fallback:
                    frame_sequence.append(fallback)
                    _progress(f"[帧{frame_idx}/{total_frames}] ⚠ 回退成功: {os.path.basename(fallback)}")
                else:
                    frame_sequence.append(None)
                    _progress(f"[帧{frame_idx}/{total_frames}] ❌ 完全失败")
            
            time.sleep(2)  # API限速
        
        success = sum(1 for f in frame_sequence if f is not None)
        _progress(f"\n[统计] 帧序列生成完成: {success}/{total_frames} 张成功")
        return frame_sequence


# ==================== 测试 ====================


    # ==================== 分镜后处理：视觉跳跃检测 + 过渡场景插入 ====================

    def expand_storyboard_with_transitions(self, storyboard):
        scenes = storyboard.get('scenes', [])
        if len(scenes) < 2:
            return storyboard

        expanded = [scenes[0]]
        transition_count = 0

        for i in range(1, len(scenes)):
            prev = scenes[i - 1]
            curr = scenes[i]

            gap = self._detect_visual_gap(prev, curr)
            level = gap.get('level', 'small')

            if level == 'large':
                print(f'   \U0001f534 场景{prev.get("scene_id")}→{curr.get("scene_id")} 大跳跃: {gap.get("reason","")}')
                transitions = self._generate_transition_scenes(prev, curr, gap, max_transitions=2)
                for t in transitions:
                    expanded.append(t)
                    transition_count += 1

            elif level == 'medium':
                print(f'   \U0001f7e1 场景{prev.get("scene_id")}→{curr.get("scene_id")} 中跳跃: {gap.get("reason","")}')
                transitions = self._generate_transition_scenes(prev, curr, gap, max_transitions=1)
                for t in transitions:
                    expanded.append(t)
                    transition_count += 1

            expanded.append(curr)

        for idx, s in enumerate(expanded):
            s['scene_id'] = idx + 1

        storyboard['scenes'] = expanded

        if transition_count > 0:
            t_count = sum(1 for s in expanded if s.get('is_transition'))
            d_count = sum(1 for s in expanded if s.get('scene_type') == 'dialogue')
            a_count = sum(1 for s in expanded if s.get('scene_type') == 'action')
            print(f'\n   \U0001f4ca 过渡场景插入完成: 插入了 {transition_count} 个过渡场景')
            print(f'   \U0001f4ca 场景总数: {len(scenes)} -> {len(expanded)} ({d_count}对话 + {a_count}动作 + {t_count}过渡)')
        else:
            print(f'   \u2705 所有相邻场景视觉连续，无需插入过渡')

        return storyboard

    def _detect_visual_gap(self, scene_a, scene_b):
        end_desc = scene_a.get('end_frame_description_en',
                               scene_a.get('visual_description_en', ''))
        start_desc = scene_b.get('start_frame_description_en',
                                 scene_b.get('visual_description_en', ''))

        if not end_desc or not start_desc:
            return {'level': 'small', 'reason': '描述缺失跳过'}

        prompt = (
            'You are a film continuity supervisor. Analyze these two CONSECUTIVE frames:\n\n'
            f'FRAME A (end of previous shot):\n{end_desc}\n\n'
            f'FRAME B (start of next shot):\n{start_desc}\n\n'
            'Question: Can a 5-second video naturally transition from Frame A to Frame B?\n'
            'Consider:\n'
            '- Location change (same room? different building? different city?)\n'
            '- Character position change (slight move? teleportation?)\n'
            '- Time jump (continuous? hours later? days later?)\n'
            '- Lighting/atmosphere change\n\n'
            'Answer with JSON:\n'
            '{"level": "small/medium/large", '
            '"reason": "brief explanation in Chinese", '
            '"transition_needed": "what should happen between these frames (English, 1-2 sentences)"}\n\n'
            'Rules:\n'
            '- small: Same location, minor position/expression change. No transition needed.\n'
            '- medium: Same general area but different spot. Need 1 brief transition.\n'
            '- large: Different location/time entirely. Need 1-2 transition scenes.\n'
        )

        result = self._call_text(
            'You are a professional film continuity supervisor. Output ONLY valid JSON.',
            prompt, temperature=0.2
        )
        data = self._extract_json(result)

        if data and isinstance(data, dict) and 'level' in data:
            valid_levels = ['small', 'medium', 'large']
            if data['level'] not in valid_levels:
                data['level'] = 'small'
            return data

        return self._heuristic_gap_check(end_desc, start_desc)

    def _heuristic_gap_check(self, desc_a, desc_b):
        a = desc_a.lower()
        b = desc_b.lower()

        location_words = [
            'classroom', 'office', 'street', 'park', 'bedroom', 'kitchen',
            'hospital', 'school', 'playground', 'rooftop', 'forest', 'car',
            'restaurant', 'temple', 'mountain', 'river', 'palace', 'cave',
            'library', 'hallway', 'garden', 'market', 'beach', 'bar',
            'living room', 'bathroom', 'balcony', 'basement', 'corridor',
        ]

        loc_a = set(w for w in location_words if w in a)
        loc_b = set(w for w in location_words if w in b)

        if loc_a and loc_b and not loc_a.intersection(loc_b):
            return {'level': 'large',
                    'reason': '场景完全不同',
                    'transition_needed': 'Need location transition'}

        indoor_kw = ['indoor', 'interior', 'inside', 'room', 'classroom', 'office', 'bedroom', 'kitchen']
        outdoor_kw = ['outdoor', 'exterior', 'outside', 'street', 'park', 'playground', 'garden']

        a_in = any(w in a for w in indoor_kw)
        a_out = any(w in a for w in outdoor_kw)
        b_in = any(w in b for w in indoor_kw)
        b_out = any(w in b for w in outdoor_kw)

        if (a_in and b_out) or (a_out and b_in):
            return {'level': 'medium',
                    'reason': '室内外切换',
                    'transition_needed': 'Character moving between indoor and outdoor'}

        return {'level': 'small', 'reason': '场景相似', 'transition_needed': ''}

    def _generate_transition_scenes(self, scene_a, scene_b, gap_info, max_transitions=2):
        gs = self.genre_style

        end_desc_a = scene_a.get('end_frame_description_en',
                                 scene_a.get('visual_description_en', ''))
        start_desc_b = scene_b.get('start_frame_description_en',
                                   scene_b.get('visual_description_en', ''))
        transition_hint = gap_info.get('transition_needed', 'smooth visual transition')

        chars_a = scene_a.get('characters', [])
        chars_b = scene_b.get('characters', [])
        all_chars = list(set(chars_a + chars_b))

        char_ref = ''
        for name in all_chars[:3]:
            profile = self.character_profiles.get(name, '')
            if profile:
                char_ref += '  ' + name + ': ' + profile + '\n'

        prompt = (
            f'You are a film director. Create {max_transitions} TRANSITION scene(s) '
            'to smoothly connect two shots.\n\n'
            f'SHOT A ends with:\n{end_desc_a}\n\n'
            f'SHOT B starts with:\n{start_desc_b}\n\n'
            f'What needs to happen between them:\n{transition_hint}\n\n'
            f'Characters involved:\n{char_ref if char_ref else "Same characters"}\n\n'
            f'Visual style: {gs.get("visual_prefix", "cinematic")}\n\n'
            f'Generate EXACTLY {max_transitions} transition scene(s). Each is a 3-5 second shot with NO dialogue.\n'
            'Output JSON array:\n'
            '[{\n'
            '  "visual_description_en": "full English prompt, 30-50 words",\n'
            '  "visual_description_cn": "Chinese summary under 30 chars",\n'
            '  "start_frame_description_en": "first frame, 30-50 words",\n'
            '  "end_frame_description_en": "last frame, 30-50 words",\n'
            '  "camera_movement": "Chinese camera movement",\n'
            '  "characters": ["names"],\n'
            '  "emotion": "calm"\n'
            '}]\n\n'
            'CRITICAL RULES:\n'
            '- Transition 1 start_frame MUST be VERY SIMILAR to Shot A end frame\n'
            '- Last transition end_frame MUST be VERY SIMILAR to Shot B start frame\n'
            '- Each must be achievable in ONE 5-second video clip\n'
            '- Include FULL character appearance details\n'
            '- NO dialogue, pure visual storytelling\n'
            '- Show realistic physical movement\n'
        )

        result = self._call_text(
            'You are a film director specializing in scene transitions. Output ONLY valid JSON array.',
            prompt, temperature=0.5
        )
        data = self._extract_json(result)

        transitions = []
        if data:
            items = data if isinstance(data, list) else [data]
            for item in items[:max_transitions]:
                if not isinstance(item, dict):
                    continue

                t = {
                    'scene_id': 0,
                    'scene_type': 'transition',
                    'speaker': '',
                    'dialogue': '',
                    'characters': item.get('characters', all_chars[:2]),
                    'emotion': item.get('emotion', 'calm'),
                    'duration': 1.5,
                    'camera_movement': item.get('camera_movement', '镜头缓缓移动'),
                    'visual_description_en': '',
                    'visual_description_cn': item.get('visual_description_cn', '过渡场景'),
                    'visual_description': '',
                    'start_frame_description_en': item.get('start_frame_description_en', ''),
                    'end_frame_description_en': item.get('end_frame_description_en', ''),
                    'is_transition': True,
                }

                vd = item.get('visual_description_en', '')
                if vd:
                    # 直接使用SD提示词，不再硬拼
                    t['visual_description_en'] = vd
                    t['visual_description'] = vd

        # start_frame直接使用已有SD提示词

        # end_frame直接使用已有SD提示词


                transitions.append(t)
                print(f'      \U0001f517 过渡场景: {t["visual_description_cn"]}')

        if not transitions:
            print('      \u26a0 过渡场景生成失败，使用fallback')
            setting = gs.get('setting_tags', 'cinematic environment')
            t = {
                'scene_id': 0,
                'scene_type': 'transition',
                'speaker': '',
                'dialogue': '',
                'characters': all_chars[:2],
                'emotion': 'calm',
                'duration': 1.5,
                'camera_movement': '镜头缓缓移动',
                'visual_description_en': f'MEDIUM SHOT, smooth transition scene, {setting}, cinematic lighting, masterpiece, best quality, vertical composition 9:16',
                'visual_description_cn': '过渡场景',
                'visual_description': '',
                'start_frame_description_en': end_desc_a,
                'end_frame_description_en': start_desc_b,
                'is_transition': True,
            }
            t['visual_description'] = t['visual_description_en']
            transitions.append(t)

        return transitions

if __name__ == "__main__":
    engine = GeminiEngine()

    print("=" * 50)
    print("测试1: Gemini 文本能力")
    print("=" * 50)
    try:
        contents = [{"role": "user", "parts": [{"text": "你好，请用一句话介绍自己"}]}]
        result = engine._call_gemini(engine.text_model, contents)
        print(f"[✓] 文本回复: {result}")
    except Exception as e:
        print(f"[✗] 文本测试失败: {e}")

    print("\n" + "=" * 50)
    print("测试2: Nano Banana 2 图片生成")
    print("=" * 50)
    try:
        test_path = os.path.join(IMAGES_DIR, "test_image")
        result = engine.generate_image(
            "A young Chinese warrior with long black hair, wearing golden armor, "
            "standing on a mountain peak at sunset, dramatic lighting, epic fantasy style",
            test_path,
            "cinematic, anime style, detailed"
        )
        if result:
            print(f"[✓] 测试图片: {result}")
        else:
            print("[✗] 图片生成无结果")
    except Exception as e:
        print(f"[✗] 图片测试失败: {e}")

