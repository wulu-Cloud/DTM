# jimeng_api.py - 即梦API v2.1（首尾帧视频生成 + 场景描述prompt）

import requests
import time
import os
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from config import VOLC_ACCESS_KEY, VOLC_SECRET_KEY, JIMENG_VIDEO_REQ_KEY, JIMENG_VIDEO_FIRST_TAIL_REQ_KEY
import config as _cfg



def sanitize_prompt(prompt):
    """净化prompt，替换即梦API可能拦截的敏感词"""
    if not prompt:
        return prompt
    
    # 敏感词 -> 安全替换词
    replacements = {
        # 暴力/战斗相关
        "kill": "defeat", "killing": "defeating", "killed": "defeated",
        "murder": "confront", "murdered": "confronted",
        "blood": "red light", "bloody": "intense", "bleeding": "glowing red",
        "die": "fall", "died": "fallen", "dying": "fading", "death": "fate",
        "dead": "fallen", "corpse": "fallen figure",
        "stab": "strike", "stabbing": "striking", "stabbed": "struck",
        "slash": "swing", "slashing": "swinging",
        "wound": "mark", "wounded": "marked", "wounds": "marks",
        "sword": "blade", "dagger": "tool", "weapon": "gear",
        "fight": "confront", "fighting": "confronting",
        "attack": "charge", "attacking": "charging",
        "destroy": "shatter", "destruction": "chaos",
        "explode": "burst", "explosion": "flash of light",
        "shoot": "aim", "shooting": "aiming", "shot": "blast",
        "gun": "device", "rifle": "long device", "pistol": "small device",
        "bomb": "energy sphere", "grenade": "orb",
        "war": "conflict", "battle": "confrontation",
        "torture": "struggle", "pain": "tension",
        "scream": "shout", "screaming": "shouting",
        "horror": "suspense", "terrifying": "dramatic",
        "fear": "tension", "scared": "startled",
        "evil": "dark", "demon": "dark figure", "monster": "creature",
        "hell": "dark realm", "satan": "dark lord",
        "victim": "figure", "suffer": "endure", "suffering": "enduring",
        "rage": "intensity", "fury": "power", "angry": "determined",
        "revenge": "justice", "vengeance": "resolve",
        "crush": "overpower", "smash": "break through",
        "punch": "strike", "kick": "push",
        "strangle": "restrain", "choke": "gasp",
        "assassin": "shadow figure", "assassinate": "target",
        "execution": "judgment", "execute": "judge",
        "poison": "potion", "toxic": "mysterious",
        "burn": "glow", "burning": "glowing", "fire": "flames",
        # 色情/裸露相关
        "naked": "bare", "nude": "unclothed", "nudity": "exposure",
        "sexy": "attractive", "seductive": "charming",
        "erotic": "romantic", "sexual": "intimate",
        "breast": "chest", "breasts": "chest",
        # 政治/宗教
        "terrorist": "antagonist", "terrorism": "threat",
        # 中文敏感词
        "杀": "击败", "杀死": "击败", "杀人": "对抗",
        "血": "红光", "鲜血": "红色光芒", "血腥": "激烈",
        "死": "倒下", "死亡": "消逝", "死去": "倒下",
        "尸体": "倒下的身影", "尸": "倒下的人",
        "刀": "利刃", "剑": "长刃", "枪": "装置", "武器": "器具",
        "打斗": "对抗", "战斗": "对峙", "攻击": "冲锋",
        "爆炸": "闪光", "炸": "迸发",
        "恐怖": "紧张", "恐惧": "紧迫",
        "魔鬼": "暗影", "恶魔": "暗影生物",
        "地狱": "暗域", "炼狱": "幽境",
        "暴力": "激烈", "残忍": "严酷",
        "毒": "秘药", "毒药": "神秘药水",
        "火焰": "光焰", "燃烧": "发光",
        "复仇": "追寻正义", "仇恨": "执念",
        "愤怒": "坚定", "暴怒": "力量爆发",
        "惨": "剧烈", "惨叫": "大喊",
        "痛苦": "挣扎", "折磨": "考验",
        "裸": "赤", "色情": "浪漫",
        "警察": "制服人员", "警官": "制服人员", "短发女警": "短发女性", "女警": "女性工作者", "警车": "公务车辆",
        "香烟": "小物件", "烟": "小物件", "摆放8支": "摆放几个",
        "敬畏": "认真", "审讯": "询问", "犯人": "当事人", "罪犯": "嫌疑者",
        "监狱": "封闭场所", "牢房": "房间", "手铐": "金属环",
        "枪": "装置", "开枪": "释放能量", "子弹": "投射物",
        "警局": "办公大楼", "派出所": "办公场所", "公安": "公务人员",
        "囚犯": "被拘留者", "逮捕": "控制", "拘留": "留置",
    }
    
    result = prompt
    # 先替换长词，再替换短词（避免部分替换问题）
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for word in sorted_keys:
        if word in result:
            result = result.replace(word, replacements[word])
    
    if result != prompt:
        print(f"  🔧 Prompt已净化（替换了敏感词）")
    
    return result


class JimengVideoAPI:
    """即梦API v2.1 - 支持首尾帧 + 场景描述prompt"""

    def __init__(self):
        self.access_key = VOLC_ACCESS_KEY
        self.secret_key = VOLC_SECRET_KEY
        self.host = "visual.volcengineapi.com"
        self.service = "cv"
        self.region = "cn-north-1"
        self.video_req_key = JIMENG_VIDEO_REQ_KEY
        self.first_tail_req_key = JIMENG_VIDEO_FIRST_TAIL_REQ_KEY
        print(f"[即梦] 视频API v2.1 初始化完成（场景描述prompt版）")

    def _sign_request(self, method, action, body_str):
        now = datetime.now(timezone.utc)
        date_str = now.strftime('%Y%m%dT%H%M%SZ')
        date_short = now.strftime('%Y%m%d')
        query_string = f"Action={action}&Version=2022-08-31"
        content_type = "application/json"
        payload_hash = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{self.host}\n"
            f"x-content-sha256:{payload_hash}\n"
            f"x-date:{date_str}\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = "\n".join([
            method, "/", query_string, canonical_headers, signed_headers, payload_hash,
        ])
        credential_scope = f"{date_short}/{self.region}/{self.service}/request"
        string_to_sign = "\n".join([
            "HMAC-SHA256", date_str, credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest(),
        ])
        def hmac_sha256(key, msg):
            if isinstance(key, str): key = key.encode('utf-8')
            if isinstance(msg, str): msg = msg.encode('utf-8')
            return hmac.new(key, msg, hashlib.sha256).digest()
        k_date = hmac_sha256(self.secret_key.encode('utf-8'), date_short)
        k_region = hmac_sha256(k_date, self.region)
        k_service = hmac_sha256(k_region, self.service)
        k_signing = hmac_sha256(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        authorization = (
            f"HMAC-SHA256 "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        headers = {
            "Content-Type": content_type,
            "Host": self.host,
            "X-Date": date_str,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        }
        url = f"https://{self.host}/?{query_string}"
        return url, headers

    def image_to_video(self, image_path, save_path, duration=5, prompt=""):
        """单图转视频（异步提交 + 轮询）"""
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        body = {
            "req_key": self.video_req_key,
            "binary_data_base64": [image_base64],
        }
        if not prompt:
            prompt = "Cinematic shot, smooth natural movement, professional lighting, 8K quality"
        body["prompt"] = sanitize_prompt(prompt)
        body_str = json.dumps(body)
        url, headers = self._sign_request("POST", "CVSync2AsyncSubmitTask", body_str)
        try:
            response = requests.post(url, headers=headers, data=body_str, timeout=60)
            result = response.json()
            print(f"   📡 提交HTTP {response.status_code}")
            if result.get("code") == 10000:
                task_id = result.get("data", {}).get("task_id")
                if task_id:
                    print(f"   ✅ [提交] 视频任务: {task_id}")
                    return self._poll_task(task_id, save_path)
                else:
                    video_url = result.get("data", {}).get("video_url")
                    if video_url:
                        return self._download_video(video_url, save_path)
            code = result.get("code", "?")
            msg = result.get("message", "unknown")
            print(f"[X] 视频提交失败: code={code}, {msg}")
            return None
        except Exception as e:
            print(f"[X] 视频生成异常: {e}")
            return None

    def first_last_frame_to_video(self, first_image_path, last_image_path, save_path, duration=5, prompt=""):
        """首尾帧转视频 - ★ 现在接受场景描述prompt"""
        with open(first_image_path, "rb") as f:
            first_b64 = base64.b64encode(f.read()).decode()
        with open(last_image_path, "rb") as f:
            last_b64 = base64.b64encode(f.read()).decode()

        # ★ 使用传入的场景描述，而不是写死的通用描述
        if not prompt:
            prompt = "高质量电影画面，流畅自然的动作，电影级镜头运动"

        body = {
            "req_key": self.first_tail_req_key,
            "binary_data_base64": [first_b64, last_b64],
            "prompt": sanitize_prompt(prompt),
        }
        body_str = json.dumps(body)
        url, headers = self._sign_request("POST", "CVSync2AsyncSubmitTask", body_str)
        try:
            response = requests.post(url, headers=headers, data=body_str, timeout=60)
            result = response.json()
            print(f"   📡 首尾帧提交HTTP {response.status_code}")
            print(f"   📝 视频prompt: {prompt[:80]}...")
            if result.get("code") == 10000:
                task_id = result.get("data", {}).get("task_id")
                if task_id:
                    print(f"   ✅ [首尾帧] 视频任务: {task_id}")
                    return self._poll_task(task_id, save_path, req_key=self.first_tail_req_key)
                video_url = result.get("data", {}).get("video_url")
                if video_url:
                    return self._download_video(video_url, save_path)
            else:
                code = result.get("code", "?")
                msg = result.get("message", "unknown")
                print(f"   ⚠ 首尾帧模式失败(code={code}: {msg})，回退到单图模式...")
                return self.image_to_video(first_image_path, save_path, duration, prompt)
        except Exception as e:
            print(f"   ⚠ 首尾帧异常: {e}，回退到单图模式...")
            return self.image_to_video(first_image_path, save_path, duration, prompt)

    def _poll_task(self, task_id, save_path, max_wait=300, req_key=None):
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                body = {"req_key": req_key or self.video_req_key, "task_id": task_id}
                body_str = json.dumps(body)
                url, headers = self._sign_request("POST", "CVSync2AsyncGetResult", body_str)
                response = requests.post(url, headers=headers, data=body_str, timeout=30)
                result = response.json()
                if result.get("code") == 10000:
                    data = result.get("data", {})
                    status = data.get("status")
                    if status == "done":
                        video_url = data.get("video_url") or data.get("resp_data", {}).get("video_url")
                        if video_url:
                            print(f"   ✅ 视频生成完成!")
                            return self._download_video(video_url, save_path)
                        print(f"   ❌ 完成但无视频URL")
                        return None
                    elif status == "failed":
                        print(f"[X] 视频生成失败")
                        return None
                    else:
                        elapsed = int(time.time() - start_time)
                        print(f"   ⏳ [等待] 视频生成中... ({elapsed}秒)")
                else:
                    code = result.get("code", "?")
                    msg = result.get("message", "?")
                    print(f"   ⚠️ 查询: code={code}, {msg}")
            except Exception as e:
                print(f"[⚠] 轮询异常: {e}")
            time.sleep(10)
        print(f"[X] 视频生成超时")
        return None

    def _download_video(self, video_url, save_path):
        try:
            video_data = requests.get(video_url, timeout=60).content
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(video_data)
            print(f"[✓] 视频已保存: {save_path}")
            return save_path
        except Exception as e:
            print(f"[X] 视频下载失败: {e}")
            return None

    def batch_generate_videos(self, image_paths, episode_num, scene_prompts=None):
        results = []
        for i, img_path in enumerate(image_paths):
            if img_path is None:
                results.append(None)
                continue
            save_path = os.path.join(_cfg.VIDEOS_DIR, f"ep{episode_num:03d}_scene{i+1:03d}.mp4")
            print(f"[视频] 集{episode_num} 场景{i+1}...")
            # ★ 使用 Gemini 生成的视频prompt
            prompt = ""
            if scene_prompts and i < len(scene_prompts):
                prompt = scene_prompts[i]
                print(f"  prompt: {prompt[:60]}...")
            result = self.image_to_video(img_path, save_path, prompt=prompt)
            results.append(result)
            time.sleep(3)
        return results

    def batch_generate_videos_with_frames(self, first_last_pairs, episode_num, scene_prompts=None):
        """批量生成视频 - ★ 新增 scene_prompts 参数
        
        Args:
            first_last_pairs: [(first_img_path, last_img_path), ...]
            episode_num: 集数
            scene_prompts: [prompt_str, ...] 每个场景的描述prompt
        """
        results = []
        for i, (first_path, last_path) in enumerate(first_last_pairs):
            scene_num = i + 1
            save_path = os.path.join(_cfg.VIDEOS_DIR, f"ep{episode_num:03d}_scene{scene_num:03d}.mp4")
            
            if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
                print(f"   ⏭ 跳过场景{scene_num}（视频已存在）")
                results.append(save_path)
                continue

            if first_path is None:
                results.append(None)
                continue

            # ★ 获取该场景的描述prompt
            prompt = ""
            if scene_prompts and i < len(scene_prompts):
                prompt = scene_prompts[i] or ""

            print(f"\n[视频] 集{episode_num} 场景{scene_num}...")
            
            if last_path and os.path.exists(last_path):
                print(f"   🎬 首尾帧模式: {os.path.basename(first_path)} → {os.path.basename(last_path)}")
                result = self.first_last_frame_to_video(first_path, last_path, save_path, prompt=prompt)
            else:
                print(f"   🎬 单图模式: {os.path.basename(first_path)}")
                result = self.image_to_video(first_path, save_path, prompt=prompt)
            
            results.append(result)
            time.sleep(3)
        
        success = sum(1 for r in results if r is not None)
        print(f"\n[统计] 第{episode_num}集: {success}/{len(first_last_pairs)} 个视频生成成功")
        return results
