"""
========================================
📖 长篇小说智能分集器
========================================
"""
import re
from config import EPISODE_MIN_CHARS, EPISODE_MAX_CHARS


class NovelSplitter:
    """长篇小说分集"""

    CHAPTER_PATTERNS = [
        r'^第[一二三四五六七八九十百千\d]+[章节回卷]',
        r'^Chapter\s*\d+',
        r'^\d+[\.、]\s*\S+',
        r'^【.+】',
    ]

    def __init__(self, novel_text: str = ""):
        self.full_text = novel_text
        self.total_chars = len(novel_text)
        if novel_text:
            print(f"📖 小说加载: {self.total_chars}字")

    def load(self, novel_text: str):
        """后续加载文本"""
        self.full_text = novel_text
        self.total_chars = len(novel_text)
        print(f"📖 小说加载: {self.total_chars}字")

    def split(self, novel_text: str = None) -> list:
        """智能分集"""
        if novel_text:
            self.full_text = novel_text
            self.total_chars = len(novel_text)

        chapters = self._split_by_chapters()
        if chapters and len(chapters) >= 2:
            print(f"   📚 检测到 {len(chapters)} 个章节")
            episodes = self._merge_chapters_to_episodes(chapters)
        else:
            print(f"   📚 未检测到章节，按字数分集")
            episodes = self._split_by_length()

        print(f"   📺 分为 {len(episodes)} 集")
        for ep in episodes:
            print(f"      第{ep['episode']}集: {ep['title']} ({len(ep['text'])}字)")

        return episodes

    def _split_by_chapters(self) -> list:
        combined_pattern = '|'.join(f'({p})' for p in self.CHAPTER_PATTERNS)
        chapters = []
        positions = []

        for m in re.finditer(combined_pattern, self.full_text, re.MULTILINE):
            positions.append(m.start())

        if not positions:
            return []

        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(self.full_text)
            text = self.full_text[pos:end].strip()
            first_line = text.split('\n')[0].strip()
            title = first_line[:30]
            chapters.append({"title": title, "text": text, "start": pos, "end": end})

        return chapters

    def _merge_chapters_to_episodes(self, chapters: list) -> list:
        episodes = []
        current_text = ""
        current_title = ""
        ep_num = 1

        for ch in chapters:
            if current_text and len(current_text) + len(ch["text"]) > EPISODE_MAX_CHARS:
                episodes.append({
                    "episode": ep_num,
                    "title": current_title or f"第{ep_num}集",
                    "text": current_text.strip(),
                    "char_start": 0, "char_end": 0
                })
                ep_num += 1
                current_text = ""
                current_title = ""

            if not current_title:
                current_title = ch["title"]
            current_text += ch["text"] + "\n\n"

            if len(current_text) >= EPISODE_MIN_CHARS:
                episodes.append({
                    "episode": ep_num,
                    "title": current_title or f"第{ep_num}集",
                    "text": current_text.strip(),
                    "char_start": 0, "char_end": 0
                })
                ep_num += 1
                current_text = ""
                current_title = ""

        if current_text.strip():
            if episodes and len(current_text) < EPISODE_MIN_CHARS // 2:
                episodes[-1]["text"] += "\n\n" + current_text.strip()
            else:
                episodes.append({
                    "episode": ep_num,
                    "title": current_title or f"第{ep_num}集",
                    "text": current_text.strip(),
                    "char_start": 0, "char_end": 0
                })

        return episodes

    def _split_by_length(self) -> list:
        episodes = []
        ep_num = 1
        pos = 0

        while pos < self.total_chars:
            target_end = min(pos + EPISODE_MAX_CHARS, self.total_chars)
            if target_end >= self.total_chars:
                chunk = self.full_text[pos:].strip()
                if chunk:
                    episodes.append({
                        "episode": ep_num, "title": f"第{ep_num}集",
                        "text": chunk, "char_start": pos, "char_end": self.total_chars
                    })
                break

            search_start = max(pos + EPISODE_MIN_CHARS, target_end - 200)
            search_region = self.full_text[search_start:target_end]
            para_break = search_region.rfind('\n\n')
            if para_break != -1:
                cut = search_start + para_break + 2
            else:
                cut = target_end
                for sep in ['。', '！', '？', '."', '"', '\n']:
                    idx = search_region.rfind(sep)
                    if idx != -1:
                        cut = search_start + idx + len(sep)
                        break

            chunk = self.full_text[pos:cut].strip()
            if chunk:
                episodes.append({
                    "episode": ep_num, "title": f"第{ep_num}集",
                    "text": chunk, "char_start": pos, "char_end": cut
                })
                ep_num += 1
            pos = cut

        return episodes
