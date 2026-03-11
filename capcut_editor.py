# =============================================
# 🎬 视频合成器  v8.0 - 音效系统+多角色字幕
# =============================================
# - 新增：SFX音效系统（根据场景关键词自动匹配音效）
# - 新增：多角色字幕颜色（不同speaker不同颜色）
# - 保留：BGM自动选曲（根据场景情绪匹配）
# - 保留：crossfade 过渡效果
# - 修复：图片模式 lavfi 静音轨正确
import os
import json
import uuid
import time
import shutil
import subprocess
import random
from config import CAPCUT_DRAFT_DIR, FPS, VIDEO_WIDTH, VIDEO_HEIGHT
import config as _cfg

# 音效引擎
try:
    from sound_effect_engine import SoundEffectEngine
    SFX_AVAILABLE = True
except ImportError:
    SFX_AVAILABLE = False
    print("⚠️ sound_effect_engine 未找到,音效功能禁用")

# 多角色字幕颜色配置
SPEAKER_COLORS = {
    "default": "white",
    "narrator": "#CCCCCC",
    "旁白": "#CCCCCC",
}

# 预设颜色池 - 自动分配给不同角色
COLOR_POOL = [
    "#FFD700",  # 金色 - 主角1
    "#87CEEB",  # 天蓝 - 主角2
    "#FF69B4",  # 粉色 - 女性角色
    "#98FB98",  # 浅绿 - 配角1
    "#DDA0DD",  # 梅红 - 配角2
    "#F0E68C",  # 卡其 - 配角3
    "#FF8C00",  # 暗橙 - 配角4
    "#00CED1",  # 暗青 - 配角5
    "#BA55D3",  # 中紫 - 配角6
    "#F4A460",  # 沙棕 - 配角7
]


class CapcutEditor:
    """视频合成器 v8.0 - 音效系统+多角色字幕+crossfade过渡"""

    def __init__(self):
        self.clips = []
        self.project_name = ""
        self.bgm_path = None
        self.crossfade_duration = 0.5  # 默认crossfade时长(秒)
        print(f"🎬 编辑器 v8.0 (音效+多角色字幕+crossfade)")
        # 音效引擎
        self.sfx_engine = None
        if SFX_AVAILABLE:
            try:
                self.sfx_engine = SoundEffectEngine()
                print(f"  🔊 音效引擎已加载")
            except Exception as e:
                print(f"  ⚠️ 音效引擎加载失败: {e}")
        # 角色颜色映射 (自动分配)
        self._speaker_color_map = dict(SPEAKER_COLORS)
        self._color_index = 0


    def _get_speaker_color(self, speaker: str) -> str:
        """根据说话人返回对应字幕颜色"""
        if not speaker:
            return SPEAKER_COLORS.get("default", "white")
        # 先查预设颜色
        if speaker in self._speaker_color_map:
            return self._speaker_color_map[speaker]
        # 自动从颜色池分配
        color = COLOR_POOL[self._color_index % len(COLOR_POOL)]
        self._color_index += 1
        self._speaker_color_map[speaker] = color
        return color
    def set_bgm(self, bgm_path: str):
        if bgm_path and os.path.exists(bgm_path):
            self.bgm_path = bgm_path
            print(f"🎵 BGM: {bgm_path}")

    def add_clip(self, scene_data: dict):
        self.clips.append(scene_data)

    def build(self, project_name: str = "novel_video"):
        self.project_name = project_name
        total = len(self.clips)
        total_dur = sum(c.get("actual_duration", c.get("duration", 3)) for c in self.clips)
        print(f"\n📋 编排完成！共 {total} 个片段")
        print(f"⏱️ 预计总时长: {total_dur:.0f}秒 ({total_dur/60:.1f}分钟)")

    # ================================================================
    #  视觉变化检测 — 判断相邻场景是否需要过渡及过渡时长
    # ================================================================

    def _assess_visual_change(self, clip_a: dict, clip_b: dict) -> dict:
        """评估两个相邻片段的视觉差异程度
        
        Returns:
            {
                "need_transition": bool,    # 是否需要过渡
                "crossfade_dur": float,     # crossfade时长(秒)
                "reason": str,              # 原因
            }
        """
        # 场景类型
        type_a = clip_a.get("scene_type", "action")
        type_b = clip_b.get("scene_type", "action")
        speaker_a = clip_a.get("speaker", "")
        speaker_b = clip_b.get("speaker", "")

        # 规则1: 同一说话人的连续对话 → 硬切(不需要过渡)
        if type_a == "dialogue" and type_b == "dialogue" and speaker_a == speaker_b and speaker_a:
            return {"need_transition": False, "crossfade_dur": 0, "reason": "同一角色连续对话"}

        # 规则2: 对话↔对话(不同说话人) → 短过渡
        if type_a == "dialogue" and type_b == "dialogue" and speaker_a != speaker_b:
            return {"need_transition": True, "crossfade_dur": 0.3, "reason": "对话切换说话人"}

        # 规则3: 动作→对话 或 对话→动作 → 中等过渡
        if type_a != type_b:
            return {"need_transition": True, "crossfade_dur": 0.5, "reason": "场景类型切换"}

        # 规则4: 都有视频 → 检查是否有共享帧(链式帧机制下理论上视频尾帧=下段首帧)
        video_a = clip_a.get("video_path")
        video_b = clip_b.get("video_path")
        if video_a and video_b:
            # 链式帧生成的视频,理论上视频A尾帧≈视频B首帧,但API可能有偏差
            # 加一个短crossfade来平滑
            return {"need_transition": True, "crossfade_dur": 0.4, "reason": "视频段间平滑"}

        # 规则5: 一个有视频一个没有(Ken Burns回退) → 较长过渡
        if bool(video_a) != bool(video_b):
            return {"need_transition": True, "crossfade_dur": 0.6, "reason": "视频/图片混合过渡"}

        # 规则6: 都是图片(Ken Burns) → 中等过渡
        return {"need_transition": True, "crossfade_dur": 0.5, "reason": "图片场景过渡"}

    # ================================================================
    #  核心导出：支持crossfade
    # ================================================================

    def export_video_ffmpeg(self, output_name: str = "final_video.mp4") -> str:
        output_path = os.path.join(_cfg.FINAL_DIR, output_name)
        os.makedirs(_cfg.FINAL_DIR, exist_ok=True)

        print(f"\n{'='*50}")
        print(f"🎬 v6.0 合成开始 (crossfade过渡)")
        print(f"{'='*50}")

        temp_parts = []
        for i, clip in enumerate(self.clips):
            print(f"\n🔧 片段 {i+1}/{len(self.clips)}: {clip.get('scene_title', '')}")

            video_src = clip.get("video_path")
            image_src = clip.get("image_path")
            audio_src = clip.get("audio_path")
            subtitle = clip.get("narrative", "")
            speaker = clip.get("speaker", "")
            scene_type = clip.get("scene_type", "action")

            # 【关键修复】时长以音频为准
            actual_dur = clip.get("actual_duration", 0)
            if actual_dur <= 0:
                actual_dur = clip.get("duration", 3)
            # 确保最少2秒
            actual_dur = max(2.0, actual_dur)
            # 对话场景额外加0.5秒呼吸间隔
            if scene_type == "dialogue" and actual_dur < 10:
                actual_dur += 0.5

            temp_file = os.path.join(_cfg.FINAL_DIR, f"_temp_part_{i:03d}.mp4")
            success = False

            # 优先使用视频
            if video_src and os.path.exists(video_src):
                success = self._compose_with_video(
                    video_path=video_src,
                    audio_path=audio_src,
                    subtitle_text=subtitle,
                    speaker=speaker,
                    duration=actual_dur,
                    output_path=temp_file,
                    is_first=(i == 0),
                    is_last=(i == len(self.clips) - 1)
                )

            # 回退到图片 Ken Burns
            if not success and image_src and os.path.exists(image_src):
                success = self._compose_with_image(
                    image_path=image_src,
                    audio_path=audio_src,
                    subtitle_text=subtitle,
                    speaker=speaker,
                    duration=actual_dur,
                    output_path=temp_file,
                    scene_index=i,
                    is_first=(i == 0),
                    is_last=(i == len(self.clips) - 1)
                )

            if success and os.path.exists(temp_file):
                dur_check = self._get_duration(temp_file)
                print(f"   📏 实际时长: {dur_check:.1f}s (目标: {actual_dur:.1f}s)")
                # 🔊 添加音效
                if self.sfx_engine:
                    sfx_out = os.path.join(_cfg.FINAL_DIR, f"_sfx_part_{i:03d}.mp4")
                    scene_data = {
                        "visual_description": clip.get("visual_description", clip.get("narrative", "")),
                        "dialogue": subtitle,
                        "scene_type": scene_type
                    }
                    sfx_result = self._add_sfx(temp_file, sfx_out, scene_data)
                    if sfx_result != temp_file and os.path.exists(sfx_result):
                        # 音效版替换原文件
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                        temp_file = sfx_result
                temp_parts.append(temp_file)
            else:
                print(f"   ⚠️ 片段{i+1}合成失败,跳过")

        if not temp_parts:
            print("❌ 没有可用片段！")
            return None

        # ★ 使用crossfade合并代替硬切
        final = self._concat_with_crossfade(temp_parts, output_path)


        # ★ P5: 自动BGM选曲（如果没有手动设置bgm_path）
        if final and not self.bgm_path:
            try:
                from bgm_manager import BGMManager
                bgm_mgr = BGMManager()
                all_text = ' '.join(c.get('narrative','') + ' ' + c.get('scene_type','') for c in self.clips)
                auto_bgm = bgm_mgr.select_bgm(scene_text=all_text)
                if auto_bgm:
                    self.bgm_path = auto_bgm
                    print(f"  🎵 自动选曲: {os.path.basename(auto_bgm)} (情绪: {bgm_mgr.current_mood})")
            except Exception as e:
                print(f"  ⚠️ 自动选曲失败: {e}")

        if final and self.bgm_path:
            final = self._add_bgm(final, output_path)

        for f in temp_parts:
            try:
                os.remove(f)
            except:
                pass

        if final and os.path.exists(final):
            size_mb = os.path.getsize(final) / (1024 * 1024)
            dur = self._get_duration(final)
            print(f"\n🎉 最终视频: {final}")
            print(f"   📊 {size_mb:.1f}MB | {dur:.0f}秒 | {dur/60:.1f}分钟")
        return final

    # ================================================================
    #  crossfade 合并
    # ================================================================

    def _concat_with_crossfade(self, parts, output_path):
        """用 xfade 滤镜合并所有片段,相邻片段间加crossfade过渡"""
        if len(parts) == 1:
            shutil.copy2(parts[0], output_path)
            return output_path

        if len(parts) == 0:
            return None

        # 获取每个片段的时长
        durations = []
        for p in parts:
            d = self._get_duration(p)
            durations.append(d if d > 0 else 3.0)

        # 计算每对片段之间的过渡参数
        transitions = []
        for i in range(len(parts) - 1):
            if i < len(self.clips) - 1:
                assessment = self._assess_visual_change(
                    self.clips[i] if i < len(self.clips) else {},
                    self.clips[i + 1] if i + 1 < len(self.clips) else {}
                )
            else:
                assessment = {"need_transition": True, "crossfade_dur": 0.5, "reason": "默认"}

            xf_dur = assessment["crossfade_dur"] if assessment["need_transition"] else 0
            # 确保crossfade不超过任一片段时长的一半
            xf_dur = min(xf_dur, durations[i] / 2, durations[i + 1] / 2)
            transitions.append(xf_dur)

            if xf_dur > 0:
                print(f"   🔀 过渡 {i+1}→{i+2}: {xf_dur:.1f}s crossfade ({assessment['reason']})")
            else:
                print(f"   ✂️ 硬切 {i+1}→{i+2} ({assessment['reason']})")

        # 如果所有过渡都是0(全硬切),用简单concat
        if all(t == 0 for t in transitions):
            print("   📎 全部硬切,使用简单concat")
            return self._concat_all(parts, output_path)

        # 使用 xfade 滤镜逐步合并
        # FFmpeg xfade 一次只能处理两个输入,所以需要级联
        current = parts[0]
        for i in range(len(parts) - 1):
            next_part = parts[i + 1]
            xf_dur = transitions[i]

            if xf_dur <= 0:
                # 硬切：用concat
                temp_out = os.path.join(_cfg.FINAL_DIR, f"_xfade_step_{i:03d}.mp4")
                self._concat_two(current, next_part, temp_out)
            else:
                # crossfade
                temp_out = os.path.join(_cfg.FINAL_DIR, f"_xfade_step_{i:03d}.mp4")
                offset = durations[i] - xf_dur
                # 累计前面crossfade消耗的时间
                for j in range(i):
                    if transitions[j] > 0:
                        offset -= transitions[j]
                offset = max(0.1, offset)

                success = self._xfade_two(current, next_part, temp_out, offset, xf_dur)
                if not success:
                    # xfade失败,回退到concat
                    self._concat_two(current, next_part, temp_out)

            # 清理上一步的中间文件(不清理原始parts)
            if current not in parts:
                try:
                    os.remove(current)
                except:
                    pass

            if os.path.exists(temp_out):
                current = temp_out
                # 更新当前合并结果的时长
                durations[i + 1] = self._get_duration(temp_out)
            else:
                print(f"   ❌ 合并步骤{i}失败")
                return self._concat_all(parts, output_path)

        # 最终结果移动到输出路径
        if current != output_path:
            shutil.copy2(current, output_path)
            if current not in parts:
                try:
                    os.remove(current)
                except:
                    pass

        return output_path

    def _xfade_two(self, input_a, input_b, output_path, offset, xfade_dur):
        """用 xfade 合并两个视频片段"""
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_a,
                "-i", input_b,
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={xfade_dur}:offset={offset}[vout];"
                f"[0:a][1:a]acrossfade=d={xfade_dur}[aout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[-300:]
                print(f"   ⚠️ xfade失败: {stderr}")
                return False
        except Exception as e:
            print(f"   ⚠️ xfade异常: {e}")
            return False

    def _concat_two(self, input_a, input_b, output_path):
        """简单concat合并两个视频"""
        list_file = output_path + ".list.txt"
        with open(list_file, 'w', encoding='utf-8') as f:
            f.write(f"file '{os.path.abspath(input_a).replace(chr(92), '/')}'\n")
            f.write(f"file '{os.path.abspath(input_b).replace(chr(92), '/')}'\n")
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=120)
        finally:
            try:
                os.remove(list_file)
            except:
                pass

    # ================================================================
    #  以下方法与 v5.0 完全相同,保持不变
    # ================================================================

    def _compose_with_video(self, video_path, audio_path, subtitle_text, speaker,
                            duration, output_path, is_first=False, is_last=False):
        """动态视频 + 音频 + 字幕"""
        try:
            has_audio = audio_path and os.path.exists(audio_path)

            cmd = ["ffmpeg", "-y"]
            cmd += ["-stream_loop", "-1", "-i", video_path]

            if has_audio:
                cmd += ["-i", audio_path]
            else:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

            vfilters = []
            vfilters.append(f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease")
            vfilters.append(f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black")

            if is_first:
                vfilters.append("fade=t=in:st=0:d=0.8")
            if is_last:
                vfilters.append(f"fade=t=out:st={max(0, duration-0.8)}:d=0.8")
                vfilters.append(
                    f"drawtext=text='未完待续...'"
                    f":fontsize=42"
                    f":fontcolor=white@0.9"
                    f":borderw=3:bordercolor=black@0.8"
                    f":x=(w-text_w)/2:y=h/2-th/2"
                    f":font=Microsoft YaHei"
                    f":enable='between(t,{max(0, duration-2.5)},{duration})'"
                )

            if subtitle_text:
                vfilters.append(self._build_subtitle_filter(subtitle_text, speaker, duration))

            vf = ",".join(vfilters)

            cmd += ["-vf", vf]
            cmd += ["-t", str(duration)]
            cmd += ["-map", "0:v", "-map", "1:a"]

            if has_audio:
                af = "afade=t=in:st=0:d=0.3"
                if duration > 1:
                    af += f",afade=t=out:st={max(0, duration-0.5)}:d=0.5"
                cmd += ["-af", af]

            cmd += [
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-r", str(FPS),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0:
                print(f"   ✅ 视频片段完成 ({duration:.1f}s)")
                return True
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[-500:]
                print(f"   ❌ FFmpeg错误: {stderr}")
                return False

        except Exception as e:
            print(f"   ❌ 异常: {e}")
            return False

    def _compose_with_image(self, image_path, audio_path, subtitle_text, speaker,
                            duration, output_path, scene_index=0,
                            is_first=False, is_last=False):
        """图片Ken Burns + 音频"""
        try:
            has_audio = audio_path and os.path.exists(audio_path)
            total_frames = int(duration * FPS)

            scene_type = "action"
            if subtitle_text and speaker:
                scene_type = "dialogue"
            if scene_type == "dialogue":
                mode = 4 + (scene_index % 2)
            else:
                mode = scene_index % 4

            if mode == 0:
                zoompan = (
                    f"zoompan=z='min(zoom+0.0003,1.12)'"
                    f":x='iw/2-(iw/zoom/2)+on/{total_frames}*40'"
                    f":y='ih/2-(ih/zoom/2)'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )
            elif mode == 1:
                zoompan = (
                    f"zoompan=z='if(eq(on,0),1.15,max(zoom-0.0003,1.0))'"
                    f":x='iw/2-(iw/zoom/2)-on/{total_frames}*30'"
                    f":y='ih/2-(ih/zoom/2)'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )
            elif mode == 2:
                zoompan = (
                    f"zoompan=z='1.10'"
                    f":x='iw/2-(iw/zoom/2)'"
                    f":y='on/{total_frames}*(ih-ih/zoom)'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )
            elif mode == 3:
                zoompan = (
                    f"zoompan=z='min(zoom+0.0002,1.08)'"
                    f":x='on/{total_frames}*(iw-iw/zoom)'"
                    f":y='on/{total_frames}*(ih-ih/zoom)/2'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )
            elif mode == 4:
                zoompan = (
                    f"zoompan=z='min(zoom+0.0004,1.18)'"
                    f":x='iw/2-(iw/zoom/2)'"
                    f":y='ih*0.15'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )
            else:
                zoompan = (
                    f"zoompan=z='min(zoom+0.0002,1.10)'"
                    f":x='iw/2-(iw/zoom/2)+sin(on/{total_frames}*3.14)*15'"
                    f":y='ih*0.12'"
                    f":d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
                )

            vfilters = [zoompan]

            if is_first:
                vfilters.append("fade=t=in:st=0:d=0.8")
            if is_last:
                vfilters.append(f"fade=t=out:st={max(0, duration-0.8)}:d=0.8")

            if subtitle_text:
                vfilters.append(self._build_subtitle_filter(subtitle_text, speaker, duration))

            vf = ",".join(vfilters)

            cmd = ["ffmpeg", "-y"]
            cmd += ["-loop", "1", "-i", image_path]

            if has_audio:
                cmd += ["-i", audio_path]
            else:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

            cmd += ["-vf", vf]
            cmd += ["-t", str(duration)]
            cmd += ["-map", "0:v", "-map", "1:a"]

            if has_audio:
                af = "afade=t=in:st=0:d=0.3"
                if duration > 1:
                    af += f",afade=t=out:st={max(0, duration-0.5)}:d=0.5"
                cmd += ["-af", af]

            cmd += [
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-r", str(FPS),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0:
                print(f"   ✅ Ken Burns片段完成 (模式{mode}, {duration:.1f}s)")
                return True
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[-500:]
                print(f"   ❌ FFmpeg错误: {stderr}")
                return False

        except Exception as e:
            print(f"   ❌ 异常: {e}")
            return False

    def _build_subtitle_filter(self, text: str, speaker: str, duration: float) -> str:
        if speaker:
            display_text = f"【{speaker}】{text}"
        else:
            display_text = text

        safe_text = display_text.replace("'", "\u2019").replace(":", "\\:").replace("\\", "\\\\")

        lines = []
        for k in range(0, len(safe_text), 16):
            lines.append(safe_text[k:k + 16])
        safe_text = "\\n".join(lines[:3])
        # 根据角色获取颜色
        font_color = self._get_speaker_color(speaker)
        
        # 旁白用稍小字体, 角色对话用大字体
        if speaker and speaker.lower() not in ("narrator", "旁白", "narration", ""):
            font_size = 30
            border_w = 3
        else:
            font_size = 26
            border_w = 2
        
        return (
            f"drawtext=text='{safe_text}'"
            f":fontsize={font_size}"
            f":fontcolor={font_color}"
            f":borderw={border_w}"
            f":bordercolor=black@0.8"
            f":shadowcolor=black@0.5:shadowx=2:shadowy=2"
            f":x=(w-text_w)/2"
            f":y=h-th-130"
            f":font=Microsoft YaHei"
            f":enable='between(t,0.3,{duration - 0.2})'"
        )

    def _concat_all(self, parts, output_path):
        """简单合并所有片段(无过渡,作为fallback)"""
        if len(parts) == 1:
            shutil.copy2(parts[0], output_path)
            return output_path

        list_file = os.path.join(_cfg.FINAL_DIR, "_concat_list.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for p in parts:
                abs_path = os.path.abspath(p).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            try:
                os.remove(list_file)
            except:
                pass

            if result.returncode == 0:
                return output_path
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[-500:]
                print(f"❌ 合并失败: {stderr}")
                return None
        except Exception as e:
            print(f"❌ 合并异常: {e}")
            return None

    def _add_sfx(self, video_path: str, output_path: str, scene_data: dict) -> str:
        """为单个片段添加音效"""
        if not self.sfx_engine:
            return video_path
        
        try:
            # 匹配音效
            visual_desc = scene_data.get("visual_description", "")
            dialogue = scene_data.get("dialogue", "")
            scene_type = scene_data.get("scene_type", "action")
            matched = self.sfx_engine.match_scene_effects(visual_desc, dialogue, scene_type)
            
            # 只选有文件的音效
            available = [m for m in matched if m.get("available")]
            if not available:
                return video_path
            
            # 最多叠加2个音效
            available = available[:2]
            duration = self._get_duration(video_path)
            if duration <= 0:
                return video_path
            
            print(f"    🔊 音效: {[a['name'] for a in available]}")
            
            # 构建ffmpeg滤镜
            temp = video_path + ".sfx_temp.mp4"
            cmd = ["ffmpeg", "-y", "-i", video_path]
            
            filter_parts = []
            for idx, sfx in enumerate(available):
                cmd += ["-i", sfx["path"]]
                vol = sfx.get("volume", 0.3)
                # 音效循环并截断到视频时长, 加淡入淡出
                filter_parts.append(
                    f"[{idx+1}:a]aloop=loop=-1:size=2e+09,atrim=0:{duration},"
                    f"volume={vol},afade=t=in:st=0:d=0.5,"
                    f"afade=t=out:st={max(0, duration-0.5)}:d=0.5[sfx{idx}]"
                )
            
            # 混音: 原音频 + 所有音效
            mix_inputs = "[0:a]" + "".join(f"[sfx{i}]" for i in range(len(available)))
            mix_count = 1 + len(available)
            filter_parts.append(
                f"{mix_inputs}amix=inputs={mix_count}:duration=first:dropout_transition=3[aout]"
            )
            
            filter_str = ";".join(filter_parts)
            cmd += [
                "-filter_complex", filter_str,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(duration),
                "-movflags", "+faststart",
                temp
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                os.replace(temp, output_path)
                return output_path
            else:
                stderr = result.stderr.decode("utf-8", errors="ignore")[-300:]
                print(f"    ⚠️ 音效混音失败: {stderr[:100]}")
                try:
                    os.remove(temp)
                except:
                    pass
                return video_path
        except Exception as e:
            print(f"    ⚠️ 音效异常: {e}")
            return video_path
    
    def _add_bgm(self, video_path, output_path):
        if not self.bgm_path or not os.path.exists(self.bgm_path):
            return video_path

        temp = video_path + ".bgm_temp.mp4"
        try:
            duration = self._get_duration(video_path)
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-stream_loop", "-1", "-i", self.bgm_path,
                "-filter_complex",
                f"[1:a]volume=0.12,afade=t=in:st=0:d=2,afade=t=out:st={max(0, duration - 3)}:d=3[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(duration),
                "-movflags", "+faststart",
                temp
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                os.replace(temp, output_path)
                print(f"   🎵 BGM叠加完成")
                return output_path
            else:
                try:
                    os.remove(temp)
                except:
                    pass
                return video_path
        except Exception as e:
            print(f"   ⚠️ BGM异常: {e}")
            return video_path

    def _get_duration(self, path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=10
            )
            return float(result.stdout.strip())
        except:
            return 0
