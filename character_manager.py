"""
==========================================
 Character Manager v8.0 - 服装一致性强化版
- 固定服装DNA：每个角色的服装在第一次出现时锁死
- SD标签优化
- build_scene_prompt 强制携带完整外貌+服装
==========================================
"""
import os
import json
import re
import hashlib
import config as _cfg
import config as _char_cfg
from model_registry import get_registry


class CharacterManager:
    def __init__(self, novel_id: str = "default"):
        self.novel_id = novel_id
        self.profile_path = os.path.join(_cfg.PROFILE_DIR, f"{novel_id}_characters.json")
        self.characters = {}
        self.style = ""
        self.genre = "modern_crime"
        self.visual_prefix = "OC, original character, not from any anime, modern urban setting, cinematic anime style"
        self._sd_cache = {}
        # ★ 新增：固定服装DNA缓存
        self._outfit_dna = {}  # {name: "black leather jacket, white shirt, dark jeans"}
        self._reference_images = {}  # {char_name: {"face_front": path, "half_body": path, "full_body": path}}
        self._load()
        print(f"[CharacterManager] init profile={self.profile_path}")

    def _load(self):
        if os.path.exists(self.profile_path):
            with open(self.profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.characters = data.get("characters", {})
            self.style = data.get("style", "")
            self.genre = data.get("genre", "modern_crime")
            self._sd_cache = data.get("sd_appearance_cache", {})
            self._outfit_dna = data.get("outfit_dna", {})
            self._reference_images = data.get("reference_images", {})
            print(f"    loaded {len(self.characters)} characters, genre={self.genre}")
            if self._outfit_dna:
                print(f"    loaded {len(self._outfit_dna)} outfit DNAs")

    def delete_character(self, name: str):
        import shutil
        self.characters.pop(name, None)
        self._reference_images.pop(name, None)
        self._outfit_dna.pop(name, None)
        self._sd_cache.pop(name, None)
        ref_dir = os.path.join(_char_cfg.CHARACTERS_DIR, name.replace(" ", "_"))
        if os.path.isdir(ref_dir):
            shutil.rmtree(ref_dir)
            print(f"[CharMgr] deleted portrait folder: {ref_dir}")
        self.save()
        print(f"[CharMgr] deleted character: {name}")

    def save(self):
        data = {
            "novel_id": self.novel_id,
            "style": self.style,
            "genre": self.genre,
            "characters": self.characters,
            "sd_appearance_cache": self._sd_cache,
            "outfit_dna": self._outfit_dna,
            "reference_images": self._reference_images,
        }
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        with open(self.profile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def set_style(self, style: str):
        self.style = style
        self.save()

    def set_genre(self, genre: str, visual_prefix: str = ""):
        self.genre = genre
        if visual_prefix:
            self.visual_prefix = visual_prefix
        self.save()

    def update_characters(self, char_list: list):
        new_count = 0
        for char in char_list:
            name = char.get("name", "").strip()
            if not name:
                continue
            
            # 兼容 GUI 的字段名：appearance_cn -> appearance, appearance_en
            # GUI 存的是 appearance_cn 和 appearance_en
            appearance_cn = char.get("appearance_cn", "") or char.get("appearance", "")
            appearance_en = char.get("appearance_en", "")
            
            if name in self.characters:
                existing = self.characters[name]
                # 更新所有有值的字段
                if char.get("personality"):
                    existing["personality"] = char["personality"]
                if char.get("gender"):
                    existing["gender"] = char["gender"]
                if char.get("age"):
                    existing["age"] = char["age"]
                if char.get("voice"):
                    existing["voice"] = char["voice"]
                # 核心修复：更新外貌描述
                if appearance_cn:
                    existing["appearance"] = appearance_cn
                if appearance_en:
                    existing["appearance_en"] = appearance_en
                # 保存后同步到磁盘
                self.save()
            else:
                voice = char.get("voice", "少年")
                if voice in ("旁白男", "旁白女", "旁白"):
                    voice = "少年" if char.get("gender") == "male" else "少女"
                self.characters[name] = {
                    "name": name,
                    "gender": char.get("gender", ""),
                    "age": char.get("age", ""),
                    "appearance": appearance_cn,
                    "appearance_en": appearance_en,
                    "personality": char.get("personality", ""),
                    "voice": voice,
                    "first_episode": char.get("first_episode", 1),
                }
                # ★ 自动提取并锁定服装DNA
                if name not in self._outfit_dna:
                    outfit = self._extract_outfit_from_appearance(appearance_cn or appearance_en)
                    if outfit:
                        self._outfit_dna[name] = outfit
                        print(f"    🔒 锁定服装 {name}: {outfit}")
                new_count += 1
        if new_count > 0:
            print(f"    new {new_count} characters, total {len(self.characters)}")
        self.save()

    def _extract_outfit_from_appearance(self, appearance: str) -> str:
        """从appearance中提取服装描述，锁定为固定DNA"""
        if not appearance:
            return ""
        text = appearance.lower()
        outfit_parts = []
        
        # 服装关键词匹配（尽可能提取完整服装描述）
        outfit_keywords = [
            # 上衣
            (r'(?:wearing |in )?(?:a )?(?:(?:black|white|dark|blue|red|grey|gray|brown|green|navy|beige|khaki)\s+)?(?:leather\s+)?(?:jacket|coat|trench coat|blazer|hoodie|sweater|cardigan)', None),
            (r'(?:a )?(?:(?:black|white|dark|blue|red|grey|gray|brown|crisp|plain)\s+)?(?:dress\s+)?(?:shirt|blouse|t-shirt|polo|tank top|top|turtleneck)', None),
            (r'(?:a )?(?:(?:black|dark|navy|blue|police|military|tactical)\s+)?(?:uniform|vest|bulletproof vest|tactical gear|armor|body armor)', None),
            (r'(?:a )?(?:(?:black|dark|navy|blue|formal|casual|business)\s+)?suit', None),
            # 下装
            (r'(?:(?:black|dark|blue|grey|gray|khaki|brown|fitted)\s+)?(?:pants|trousers|jeans|slacks|skirt|shorts|cargo pants)', None),
            # 外套/大衣
            (r'(?:a )?(?:(?:long|short|black|dark|grey|brown)\s+)?(?:overcoat|trench coat|windbreaker|parka|cape|cloak)', None),
            # 鞋子
            (r'(?:(?:black|brown|dark|leather|combat|military|high-heeled|high heeled)\s+)?(?:boots|shoes|sneakers|heels|loafers)', None),
            # 配饰
            (r'(?:a )?(?:(?:black|dark|red|blue|silk|striped)\s+)?(?:tie|necktie|bow tie|scarf)', None),
            (r'(?:a )?(?:(?:black|dark|leather|brown|silver|gold|metal)\s+)?(?:belt|watch|bracelet|necklace|pendant|badge|holster|gun holster)', None),
            (r'(?:(?:black|dark|leather|fingerless|white|latex)\s+)?gloves', None),
            (r'(?:a )?(?:(?:black|dark|baseball|military)\s+)?(?:cap|hat|beret|helmet)', None),
            # 特殊
            (r'(?:a )?(?:(?:black|white|red|blue)\s+)?(?:mask|bandana|headband|eyepatch)', None),
            (r'(?:a )?(?:(?:lab|white|doctor\'?s?)\s+)?coat', None),
        ]
        
        for pattern, _ in outfit_keywords:
            matches = re.findall(pattern, text)
            for m in matches:
                m_clean = m.strip().lstrip('a ').strip()
                if m_clean and len(m_clean) > 2 and m_clean not in outfit_parts:
                    outfit_parts.append(m_clean)
        
        # 也查找 "wearing ..." 后面的整句
        wearing_match = re.search(r'wearing\s+(.+?)(?:\.|,\s*(?:with|and\s+(?:a\s+)?(?:sharp|focused|tired))|\s*$)', text)
        if wearing_match:
            wearing_desc = wearing_match.group(1).strip()
            # 只取服装相关的部分
            if len(wearing_desc) > 5 and len(wearing_desc) < 120:
                # 用这个作为完整服装描述
                return wearing_desc
        
        if outfit_parts:
            return ", ".join(outfit_parts[:5])
        return ""

    def set_outfit_dna(self, name: str, outfit: str):
        """手动设置角色的固定服装DNA"""
        self._outfit_dna[name] = outfit
        self.save()
        print(f"    🔒 手动锁定服装 {name}: {outfit}")

    def get_outfit_dna(self, name: str) -> str:
        """获取角色的固定服装DNA"""
        return self._outfit_dna.get(name, "")

    def get_all_outfit_dna(self) -> dict:
        """获取所有角色的服装DNA"""
        return dict(self._outfit_dna)

    def get_character(self, name: str) -> dict:
        return self.characters.get(name, {})

    def get_all_names(self) -> list:
        return list(self.characters.keys())

    def get_appearance_prompt(self, name: str) -> str:
        char = self.characters.get(name)
        if not char:
            return ""
        return char.get("appearance", "")

    def get_voice(self, name: str) -> str:
        """获取角色语音类型，兼容旧标签和新voice_type ID"""
        char = self.characters.get(name)
        if not char:
            return "少女"
        v = char.get("voice", "")
        
        # 1. 如果是旁白类
        if v in ("旁白男", "旁白女", "旁白"):
            return v if v else ("少女" if char.get("gender", "") == "male" else "少女")
        
        # 2. 如果已经是合法的 voice_type ID (包含 uranus 或 bigtts)
        if v and ("uranus" in v or "bigtts" in v or v.startswith("zh_")):
            return v  # 直接返回，tts_engine 的 _resolve_voice_type 能处理
        
        # 3. 如果是旧的中文标签（少年/少女/大叔等），直接返回
        VALID_LABELS = {
            "霸总", "少年", "大叔", "沧桑", "小鬼",
            "少女", "御姐", "萝莉", "温柔",
            "暗沉", "小宝", "温柔", "百变",
            "霸气", "心智", "温真", "邻家",
            "旁白", "旁白男", "旁白女",
        }
        if v in VALID_LABELS:
            return v
        
        # 4. 未知值，按性别默认
        gender = char.get("gender", "")
        if "female" in gender or gender in ("女", "female"):
            return "少女"
        else:
            return "少年"
    def get_character_visual_dna(self, name: str) -> str:
        """★ 核心方法：获取角色的完整视觉DNA（外貌+固定服装）
        
        这个方法返回的字符串，在每一张图片prompt中都必须完整包含，
        保证角色在所有场景中外貌+服装100%一致。
        """
        char = self.characters.get(name, {})
        if not char:
            return ""
        
        appearance = char.get("appearance", "") or char.get("appearance_cn", "")
        outfit = self._outfit_dna.get(name, "")
        
        # 如果有SD缓存的标签，优先用
        sd_tags = self._sd_cache.get(name, "")
        
        if sd_tags and outfit:
            # 检查SD标签里是否已经包含服装
            if not any(kw in sd_tags.lower() for kw in ['jacket', 'shirt', 'suit', 'uniform', 'coat', 'dress', 'pants', 'vest', 'gear']):
                return f"{sd_tags}, wearing {outfit}"
            return sd_tags
        elif sd_tags:
            return sd_tags
        elif appearance and outfit:
            # 用原始appearance + 固定outfit
            # 截取appearance到合理长度
            short_app = appearance[:150] if len(appearance) > 150 else appearance
            return f"{short_app}, ALWAYS wearing {outfit}"
        elif appearance:
            return appearance[:150]
        return ""

    def _compress_appearance_to_sd_tags(self, name: str, appearance: str) -> str:
        """把appearance描述压缩成SD友好的短标签格式，★ 包含固定服装"""
        if name in self._sd_cache and self._sd_cache[name]:
            return self._sd_cache[name]

        if not appearance:
            return ""

        tags = []
        text = appearance.lower()

        # --- 发型/发色 ---
        hair_match = re.search(
            r'((?:perpetually |very )?(?:messy|unkempt|neat|neatly[- ](?:styled|trimmed|combed)|slicked[- ]back|spiky|curly|wavy|straight|cropped|military[- ]style|practical|flowing|tousled|bob|ponytail|braid|bun|shoulder[- ]length|medium[- ]length|medium|short|long)\s+(?:(?:messy|unkempt|neat|styled|trimmed|cropped|flowing)\s+)?(?:black|brown|blonde|red|white|grey|gray|silver|blue|dark|light)\s+hair)',
            text
        )
        if hair_match:
            tags.append(hair_match.group(1).strip())
        else:
            hair_len = ""
            for hl in ["short", "long", "medium-length", "medium", "shoulder-length"]:
                if re.search(r'\b' + hl.replace('-', '[- ]') + r'\b.*hair', text):
                    hair_len = hl
                    break
            hair_style = ""
            for hs in ["messy", "unkempt", "neat", "neatly styled", "neatly trimmed", "slicked back", "flowing", "cropped", "military-style", "practical", "curly", "wavy", "straight", "spiky"]:
                if hs in text:
                    hair_style = hs
                    break
            hair_color = ""
            for hc in ["black", "brown", "blonde", "red", "white", "grey", "silver", "dark"]:
                if hc + " hair" in text:
                    hair_color = hc
                    break
            hair_desc = " ".join(filter(None, [hair_style, hair_len, hair_color]))
            if hair_desc:
                tags.append(hair_desc + " hair")

        # --- 面部特征 ---
        if any(w in text for w in ["beard", "stubbly", "stubble", "facial hair"]):
            tags.append("short beard" if any(w in text for w in ["stubbly", "stubble", "short beard"]) else "beard")
        if "clean-shaven" in text or "clean shaven" in text:
            tags.append("clean-shaven face")
        if any(w in text for w in ["scar ", "scars"]):
            tags.append("facial scar")
        if "wrinkle" in text or "weathered" in text:
            tags.append("weathered face")
        if "tired" in text or "eye bag" in text:
            tags.append("tired eyes with eye bags")
        if "glasses" in text or "spectacles" in text:
            tags.append("glasses")
        if "mask" in text:
            tags.append("black mask over eyes")
        if "pale" in text or "fair skin" in text:
            tags.append("pale fair skin")
        if "handsome" in text:
            tags.append("handsome face")
        if "alluring" in text or "graceful" in text:
            tags.append("alluring graceful")
        if "smooth" in text and "skin" in text:
            tags.append("smooth skin")

        # --- 眼睛 ---
        eye_desc = []
        for adj in ["sharp", "narrow", "large", "expressive", "intelligent", "focused", "alert"]:
            if adj in text and "eye" in text:
                eye_desc.append(adj)
                break
        for ec in ["blue", "brown", "green", "red", "golden", "amber", "dark", "black"]:
            if ec + " eye" in text:
                eye_desc.append(ec)
                break
        if eye_desc:
            tags.append(" ".join(eye_desc) + " eyes")
        if "long eyelashes" in text or "eyelashes" in text:
            tags.append("long eyelashes")

        # --- ★ 服装：使用固定outfit DNA ---
        outfit = self._outfit_dna.get(name, "")
        if outfit:
            tags.append(f"wearing {outfit}")
        else:
            # 回退：从appearance里提取
            if "trench coat" in text:
                color = "black" if "black trench" in text else "dark"
                tags.append(f"{color} trench coat")
            if "suit" in text:
                tags.append("black suit")
            if "white shirt" in text or "dress shirt" in text:
                tags.append("white dress shirt")
            if "black tie" in text or ("tie" in text and "suit" in text):
                tags.append("black tie")
            if "uniform" in text:
                if "police" in text:
                    tags.append("dark blue police uniform")
                else:
                    tags.append("uniform")
            if "tactical" in text:
                tags.append("tactical gear")
            if "bulletproof" in text:
                tags.append("bulletproof vest")
            if "helmet" in text:
                tags.append("tactical helmet")
            if "polo" in text:
                tags.append("polo shirt")
            if "t-shirt" in text:
                tags.append("plain t-shirt")
            if "jacket" in text and "trench" not in text:
                tags.append("dark jacket")
            if "skirt" in text:
                for c in ["yellow", "black", "white", "red", "blue", "light yellow"]:
                    if c in text:
                        tags.append(f"{c} short skirt")
                        break
                else:
                    tags.append("short skirt")
            if "blouse" in text:
                tags.append("white blouse")
            if "glove" in text:
                tags.append("white gloves")

        if "cigarette" in text or "smoking" in text:
            tags.append("cigarette in mouth")
        if "makeup" in text or "lightly made up" in text:
            tags.append("light makeup")

        # --- 体型 ---
        build_parts = []
        if "tall" in text:
            build_parts.append("tall")
        if "slender" in text:
            build_parts.append("slender")
        elif "muscular" in text:
            build_parts.append("muscular")
        elif "athletic" in text:
            build_parts.append("athletic")
        elif "lean" in text:
            build_parts.append("lean")
        if build_parts:
            tags.append(" ".join(build_parts) + " build")

        # --- 年龄感 ---
        if "middle-aged" in text or "40s" in text or "mid-40" in text:
            tags.append("middle-aged man" if "male" in self.characters.get(name, {}).get("gender", "") else "middle-aged")
        elif "young" in text or "early 20" in text:
            tags.append("young")

        # 去重
        seen = set()
        unique_tags = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique_tags.append(t)

        result = ", ".join(unique_tags) if unique_tags else appearance[:80]
        
        self._sd_cache[name] = result
        self.save()
        
        print(f"    [SD Tags] {name}: {result}")
        return result

    def build_scene_prompt(self, scene, style=""):
        visual = scene.get("visual_description", "")
        if not visual:
            visual = "dramatic scene, cinematic lighting"

        characters_in_scene = scene.get("characters", [])
        char_parts = []
        gender_tags = []

        for cname in characters_in_scene[:2]:
            char_info = self.characters.get(cname, {})
            gender = char_info.get("gender", "")
            appearance_en = char_info.get("appearance_en", "") or char_info.get("appearance", "")

            if gender == "male":
                gender_tags.append("1boy")
            elif gender == "female":
                gender_tags.append("1girl")

            if appearance_en:
                char_parts.append(appearance_en)

        parts = [self.visual_prefix]
        if gender_tags:
            parts.append(", ".join(gender_tags))
        if char_parts:
            parts.append(", ".join(char_parts))

        for old in [
            self.visual_prefix + ", ",
            "OC, original character, not from any anime, Chinese ancient wuxia, Tang Dynasty era, anime style, ",
            "OC, original character, not from any anime, modern urban setting, cinematic anime style, ",
            "OC, original character, not from any anime, ",
        ]:
            visual = visual.replace(old, "")

        parts.append(visual)
        parts.append("cinematic lighting, masterpiece, best quality, vertical composition 9:16")

        prompt = ", ".join(parts)
        prompt = self._safety_filter(prompt)

        if len(prompt) > 800:
            prompt = prompt[:800]
            last_comma = prompt.rfind(",")
            if last_comma > 600:
                prompt = prompt[:last_comma]
            prompt += ", vertical composition 9:16"

        for cname in characters_in_scene[:2]:
            char_info = self.characters.get(cname, {})
            gender = char_info.get('gender', '')
            if gender == 'male':
                replacement = 'the man'
            elif gender == 'female':
                replacement = 'the woman'
            else:
                replacement = 'the person'
            prompt = prompt.replace(cname, replacement)

        prompt = re.sub(r'[\u4e00-\u9fff]+', '', prompt)
        prompt = re.sub(r',\s*,', ',', prompt)
        prompt = re.sub(r'\s+', ' ', prompt)
        return prompt.strip()

    def build_negative_prompt(self, scene=None):
        return (
            "lowres, bad anatomy, bad hands, text, watermark, blurry, "
            "deformed, ugly, duplicate, extra limbs, missing limbs, "
            "disfigured, gross proportions, malformed, mutated, "
            "existing anime character, copyrighted character, "
            "Naruto, Dragon Ball, One Piece, Demon Slayer"
        )

    def build_characters_summary(self) -> str:
        if not self.characters:
            return ""
        lines = []
        for name, char in self.characters.items():
            line = f"- {name}({char.get('gender','')}, {char.get('age','')}):"
            line += char.get('appearance', 'no description')
            # ★ 附加固定服装
            outfit = self._outfit_dna.get(name, "")
            if outfit:
                line += f" [FIXED OUTFIT: {outfit}]"
            lines.append(line)
        return "\n".join(lines)

    def _safety_filter(self, prompt: str) -> str:
        remove_words = [
            "blood", "gore", "death", "dead", "corpse", "murder",
            "naked", "nude", "sexy", "erotic", "nsfw",
            "血", "裸",
        ]
        for word in remove_words:
            prompt = prompt.replace(word, "")
            prompt = prompt.replace(word.capitalize(), "")
        prompt = re.sub(r',\s*,', ',', prompt)
        prompt = re.sub(r'\s+', ' ', prompt)
        return prompt

    def set_core_feature(self, char_name: str, feature: str):
        """手动标记角色核心视觉符号（如龙面具/叼烟）"""
        if char_name not in self._core_features:
            self._core_features = getattr(self, '_core_features', {})
        self._core_features[char_name] = feature
        print(f"[CharMgr] 🔒 {char_name} 核心特征锁定: {feature}")
    
    def get_core_feature(self, char_name: str) -> str:
        """获取角色核心视觉符号"""
        features = getattr(self, '_core_features', {})
        return features.get(char_name, "")
    
    def get_character_full_visual(self, char_name: str) -> str:
        """获取角色完整视觉描述 = 外貌 + 服装DNA + 核心特征"""
        dna = self.get_character_visual_dna(char_name) if hasattr(self, 'get_character_visual_dna') else ""
        core = self.get_core_feature(char_name)
        if core:
            dna = dna + f", MUST include: {core}"
        return dna

    # ==================== 定妆照管理 ====================

    def set_reference_image(self, char_name, image_type, image_path):
        """设置角色定妆照
        char_name: 角色名
        image_type: 'face_front' | 'half_body' | 'full_body'
        image_path: 图片路径
        """
        import shutil, os
        if char_name not in self._reference_images:
            self._reference_images[char_name] = {}

        # 复制图片到 characters/ 目录
        ref_dir = _char_cfg.CHARACTERS_DIR
        os.makedirs(ref_dir, exist_ok=True)

        ext = os.path.splitext(image_path)[1] or '.png'
        safe_name = char_name.replace(' ', '_')
        dest_path = os.path.join(ref_dir, f"{safe_name}_{image_type}{ext}")
        shutil.copy2(image_path, dest_path)

        self._reference_images[char_name][image_type] = dest_path
        self.save()
        print(f"[CharMgr] Set reference image: {char_name} / {image_type} -> {dest_path}")
        return dest_path

    def get_reference_image(self, char_name, image_type=None):
        """获取角色定妆照路径
        如果指定 image_type，返回该类型；否则按优先级返回最佳的一张
        优先级：half_body > face_front > full_body
        """
        refs = self._reference_images.get(char_name, {})
        if not refs:
            return None

        if image_type:
            path = refs.get(image_type)
            if path and os.path.exists(path):
                return path
            return None

        # 自动选最佳
        for t in ['half_body', 'face_front', 'full_body']:
            path = refs.get(t)
            if path and os.path.exists(path):
                return path
        return None

    def get_best_reference_for_scene(self, char_name, scene_type='dialogue'):
        """根据场景类型选最合适的定妆照
        dialogue/emotional -> half_body 或 face_front（特写）
        action/wide        -> full_body
        """
        refs = self._reference_images.get(char_name, {})
        if not refs:
            return None

        if scene_type in ('dialogue', 'emotional'):
            priority = ['half_body', 'face_front', 'full_body']
        else:
            priority = ['full_body', 'half_body', 'face_front']

        for t in priority:
            path = refs.get(t)
            if path and os.path.exists(path):
                return path
        return None

    def get_all_reference_images(self, char_name):
        """获取角色所有定妆照 {type: path}"""
        refs = self._reference_images.get(char_name, {})
        result = {}
        for t, path in refs.items():
            if path and os.path.exists(path):
                result[t] = path
        return result

    def has_reference_image(self, char_name):
        """检查角色是否有定妆照"""
        refs = self._reference_images.get(char_name, {})
        return any(os.path.exists(p) for p in refs.values() if p)

    def get_characters_with_references(self):
        """获取所有有定妆照的角色列表"""
        result = []
        for name in self._reference_images:
            if self.has_reference_image(name):
                result.append(name)
        return result

    def get_characters_without_references(self):
        """获取所有没有定妆照的角色列表"""
        all_chars = [c.get('name', '') for c in self.characters]
        with_refs = self.get_characters_with_references()
        return [n for n in all_chars if n and n not in with_refs]

    # ==================== 定妆照生成 ====================

    def generate_portrait(self, char_name, image_type, gemini_engine, style_prefix=""):
        """为角色生成定妆照
        char_name: 角色名
        image_type: 'face_front' | 'half_body' | 'full_body' | 'face_side' | 'face_back'
        gemini_engine: GeminiEngine实例
        style_prefix: 风格前缀
        返回: 保存路径 或 None
        """
        char = self.characters.get(char_name)
        if not char:
            print(f"[CharMgr] 角色不存在: {char_name}")
            return None

        appearance = char.get("appearance", "") or char.get("appearance_cn", "")
        # ★ 如果appearance是中文，先翻译成英文
        appearance_en = char.get("appearance_en", "")
        if appearance_en:
            appearance = appearance_en
        elif appearance and any('\u4e00' <= c <= '\u9fff' for c in appearance):
            # 有中文但没有英文版本，用Gemini翻译
            try:
                translated = gemini_engine.translate_cn_to_en(appearance)
                if translated and len(translated) > 10:
                    appearance = translated.strip()
                    # 缓存翻译结果
                    if char_name in self.characters:
                        self.characters[char_name]["appearance_en"] = appearance
                        self.save()
                    print(f"    [翻译] {char_name} 外貌已翻译为英文: {appearance[:100]}...")
            except Exception as e:
                print(f"    [翻译失败] {char_name}: {e}")
        outfit = self._outfit_dna.get(char_name, "")
        gender = char.get("gender", "male")

        # 根据类型构建prompt
        type_prompts = {
            "face_front": {
                "view": "front view portrait, face and upper shoulders visible",
                "shot": "CLOSE UP portrait shot",
                "bg": "plain solid white background",
            },
            "face_side": {
                "view": "side view portrait, 3/4 angle, face clearly visible",
                "shot": "CLOSE UP portrait shot from 3/4 angle",
                "bg": "plain solid white background",
            },
            "face_back": {
                "view": "back view, showing hair and back of head",
                "shot": "CLOSE UP back view",
                "bg": "plain solid white background",
            },
            "half_body": {
                "view": "half body shot from waist up, front facing, arms visible",
                "shot": "MEDIUM SHOT half body",
                "bg": "plain solid light gray background",
            },
            "full_body": {
                "view": "full body shot, entire body from head to feet visible, standing pose",
                "shot": "FULL BODY shot",
                "bg": "plain solid light gray background",
            },
        "tri_front": {
            "view": "front view, full body, standing pose, entire body from head to feet visible, facing the camera directly",
            "shot": "FULL BODY front view shot",
            "bg": "plain solid white background",
        },
        "tri_side": {
            "view": "side view, 3/4 angle, full body, standing pose, entire body from head to feet visible, face clearly visible",
            "shot": "FULL BODY 3/4 angle shot",
            "bg": "plain solid white background",
        },
        "tri_back": {
            "view": "back view, full body, standing pose, entire body from head to feet visible, showing hair and back of body",
            "shot": "FULL BODY back view shot",
            "bg": "plain solid white background",
        },
        }

        tp = type_prompts.get(image_type, type_prompts["half_body"])

        # 组装prompt
        outfit_str = f", wearing {outfit}" if outfit else ""
        # 使用style_prefix，如果没有则用默认风格
        style_desc = style_prefix if style_prefix else "anime style"
        prompt = (
            f"Single character portrait. {tp['shot']}. "
            f"{tp['view']}. "
            f"{'1 male' if gender == 'male' else '1 female'}, {appearance}{outfit_str}. "
            f"Aspect ratio: 9:16 vertical (1088x1920). "
            f"Content: {tp['shot']}. "
            f"{tp['bg']}. "
            f"Clean lines, no extra characters, single character only, "
            f"high detail, professional character design sheet, "
            f"OC, original character, not from any anime, modern urban setting, "
            f"{style_desc}, masterpiece, best quality. "
            f"Requirements: No text, no watermarks, no letters, no words on image. "
            f"High detail, professional quality, consistent character design."
        )

        # 角色名可能是中文，不需要替换了（已在prompt中用 1 male/1 female 标注）

        # 去中文
        import re as _re
        prompt = _re.sub(r'[\u4e00-\u9fff]+', '', prompt)

        # 保存路径
        ref_dir = os.path.join(_char_cfg.CHARACTERS_DIR, char_name.replace(" ", "_"))
        os.makedirs(ref_dir, exist_ok=True)
        save_path = os.path.join(ref_dir, f"{image_type}.png")

        print(f"[CharMgr] 生成定妆照: {char_name} / {image_type}")
        print(f"    prompt: {prompt[:200]}...")


        # 收集已有的定妆照作为参考图，保证一致性
        ref_paths = []
        existing_refs = self._reference_images.get(char_name, {})
        for _t, _p in existing_refs.items():
            if _t != image_type and _p and os.path.exists(_p):
                ref_paths.append(_p)
        
        # 如果有参考图，在prompt前加强调
        if ref_paths:
            ref_note = "IMPORTANT: I am providing reference image(s) of the character(s). You MUST maintain the EXACT same character appearance, face features, hairstyle, hair color, eye color, and clothing/outfit as shown in the reference image(s). The character in the generated image must look like the SAME person as in the reference. "
            prompt = ref_note + "Generate a high-quality illustration. Style: OC, original character, not from any anime, modern urban setting, cinematic anime style. " + prompt
        result = (get_registry().get_image_engine() or gemini_engine).generate_image(prompt, save_path, style_prefix=style_prefix, reference_image_paths=ref_paths if ref_paths else None)
        if result:
            # 保存到引用表
            if char_name not in self._reference_images:
                self._reference_images[char_name] = {}
            self._reference_images[char_name][image_type] = result["path"] if isinstance(result, dict) and "path" in result else result
            self.save()
            print(f"[CharMgr] ✅ 定妆照已保存: {result}")
            return result
        else:
            print(f"[CharMgr] ❌ 定妆照生成失败: {char_name}/{image_type}")
            return None

    def generate_all_portraits(self, char_name, gemini_engine, style_prefix="", types=None):
        """为角色生成全套定妆照（正面/半身/全身）"""
        if types is None:
            types = ["face_front", "half_body", "full_body"]
        
        results = {}
        for t in types:
            import time
            path = self.generate_portrait(char_name, t, gemini_engine, style_prefix)
            results[t] = path
            if path:
                time.sleep(3)  # API限速
        return results

    def get_scene_reference_images(self, character_names, scene_type="dialogue"):
        """根据场景中的角色列表，返回所有需要的参考图路径列表"""
        ref_paths = []
        for name in character_names[:2]:  # 最多2个角色的参考图
            path = self.get_best_reference_for_scene(name, scene_type)
            if path:
                ref_paths.append(path)
        return ref_paths

    # ==================== 场景背景库 ====================

    def _get_bg_dir(self):
        """获取场景背景存储目录"""
        bg_dir = _char_cfg.BACKGROUNDS_DIR
        os.makedirs(bg_dir, exist_ok=True)
        return bg_dir

    def save_background(self, location_name, image_path):
        """保存场景背景图"""
        import shutil
        bg_dir = self._get_bg_dir()
        safe_name = location_name.replace(" ", "_").replace("/", "_")
        ext = os.path.splitext(image_path)[1] or ".png"
        dest = os.path.join(bg_dir, f"bg_{safe_name}{ext}")
        shutil.copy2(image_path, dest)
        
        # 保存到JSON
        data_path = os.path.join(bg_dir, "backgrounds.json")
        bg_data = {}
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                bg_data = json.load(f)
        bg_data[location_name] = dest
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(bg_data, f, ensure_ascii=False, indent=2)
        
        print(f"[CharMgr] 场景背景已保存: {location_name} -> {dest}")
        return dest

    def get_background(self, location_name):
        """获取场景背景图路径"""
        bg_dir = self._get_bg_dir()
        data_path = os.path.join(bg_dir, "backgrounds.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                bg_data = json.load(f)
            path = bg_data.get(location_name)
            if path and os.path.exists(path):
                return path
        return None

    def get_all_backgrounds(self):
        """获取所有场景背景 {name: path}"""
        bg_dir = self._get_bg_dir()
        data_path = os.path.join(bg_dir, "backgrounds.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                bg_data = json.load(f)
            return {k: v for k, v in bg_data.items() if os.path.exists(v)}
        return {}

    def generate_background(self, location_name, description, gemini_engine, style_prefix=""):
        """生成场景背景图（无人物）"""
        prompt = (
            f"BACKGROUND SCENE, NO CHARACTERS, NO PEOPLE, empty scene. "
            f"{description}. "
            f"Wide establishing shot, detailed environment, "
            f"atmospheric lighting, cinematic composition, "
            f"anime style background art, masterpiece, best quality, "
            f"vertical composition 9:16"
        )
        
        bg_dir = self._get_bg_dir()
        safe_name = location_name.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(bg_dir, f"bg_{safe_name}.png")
        
        print(f"[CharMgr] 生成场景背景: {location_name}")
        result = (get_registry().get_image_engine() or gemini_engine).generate_image(prompt, save_path, style_prefix=style_prefix)
        if result:
            self.save_background(location_name, result)
            return result
        return None

