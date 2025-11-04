#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目管理核心模块
包含小说项目、章节、角色等数据结构
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from .character_tracker import CharacterTracker


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_number: int
    title: str
    summary: str  # 章节概要
    key_events: List[str] = field(default_factory=list)  # 关键事件
    involved_characters: List[str] = field(default_factory=list)  # 涉及角色
    target_length: int = 3000  # 目标字数
    status: str = "planned"  # planned/generated/completed
    notes: str = ""  # 备注
    
    def to_dict(self) -> dict:
        return {
            'chapter_number': self.chapter_number,
            'title': self.title,
            'summary': self.summary,
            'key_events': self.key_events,
            'involved_characters': self.involved_characters,
            'target_length': self.target_length,
            'status': self.status,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ChapterOutline':
        return ChapterOutline(**data)


@dataclass
class Character:
    """角色数据类"""
    name: str
    description: str
    personality: str = ""
    background: str = ""
    relationships: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """从字典创建"""
        return cls(**data)
    
    def get_full_description(self) -> str:
        """获取完整的角色描述"""
        parts = [f"角色：{self.name}", f"描述：{self.description}"]
        if self.personality:
            parts.append(f"性格：{self.personality}")
        if self.background:
            parts.append(f"背景：{self.background}")
        if self.relationships:
            rel_text = "、".join([f"{k}({v})" for k, v in self.relationships.items()])
            parts.append(f"关系：{rel_text}")
        return "\n".join(parts)


@dataclass
class Chapter:
    """章节数据类"""
    title: str
    content: str
    chapter_number: int = 0
    summary: str = ""
    word_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """初始化后处理"""
        if self.word_count == 0:
            self.word_count = len(self.content)
    
    def update_content(self, new_content: str):
        """更新章节内容"""
        self.content = new_content
        self.word_count = len(new_content)
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Chapter":
        """从字典创建"""
        return cls(**data)
    
    def get_preview(self, length: int = 200) -> str:
        """获取章节预览"""
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + "..."


class NovelProject:
    """小说项目管理类"""
    
    def __init__(self, title: str, project_dir: str = "projects"):
        self.title = title
        self.genre = ""
        self.background = ""
        self.plot_outline = ""
        self.writing_style = ""
        self.target_audience = ""
        self.story_goal = ""  # 故事目标/最终状态
        
        self.characters: List[Character] = []
        self.chapters: List[Chapter] = []
        self.plot_points: List[str] = []
        self.chapter_outlines: List[ChapterOutline] = []  # 章节大纲列表
        
        # 角色动态追踪系统
        self.character_tracker = CharacterTracker()
        
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        self.project_dir = project_dir
        self.project_path = os.path.join(project_dir, self.title)
    
    # === 角色管理 ===
    
    def add_character(self, character: Character) -> None:
        """添加角色"""
        self.characters.append(character)
        self.updated_at = datetime.now().isoformat()
    
    def get_character(self, name: str) -> Optional[Character]:
        """获取角色"""
        for char in self.characters:
            if char.name == name:
                return char
        return None
    
    def remove_character(self, name: str) -> bool:
        """删除角色"""
        for i, char in enumerate(self.characters):
            if char.name == name:
                self.characters.pop(i)
                self.updated_at = datetime.now().isoformat()
                return True
        return False
    
    def get_all_characters_info(self) -> str:
        """获取所有角色信息的文本描述"""
        if not self.characters:
            return "暂无角色信息"
        return "\n\n".join([char.get_full_description() for char in self.characters])
    
    # === 章节管理 ===
    
    def add_chapter(self, chapter: Chapter) -> None:
        """添加章节"""
        chapter.chapter_number = len(self.chapters) + 1
        self.chapters.append(chapter)
        self.updated_at = datetime.now().isoformat()
    
    def get_chapter(self, chapter_number: int) -> Optional[Chapter]:
        """获取指定章节"""
        if 0 < chapter_number <= len(self.chapters):
            return self.chapters[chapter_number - 1]
        return None
    
    def get_latest_chapter(self) -> Optional[Chapter]:
        """获取最新章节"""
        return self.chapters[-1] if self.chapters else None
    
    def get_recent_chapters(self, count: int = 3) -> List[Chapter]:
        """获取最近的N个章节"""
        return self.chapters[-count:] if self.chapters else []
    
    def update_chapter(self, chapter_number: int, new_content: str) -> bool:
        """更新章节内容"""
        chapter = self.get_chapter(chapter_number)
        if chapter:
            chapter.update_content(new_content)
            self.updated_at = datetime.now().isoformat()
            return True
        return False
    
    def get_total_word_count(self) -> int:
        """获取总字数"""
        return sum(chapter.word_count for chapter in self.chapters)
    
    # === 情节管理 ===
    
    def add_plot_point(self, plot_point: str) -> None:
        """添加情节要点"""
        self.plot_points.append(plot_point)
        self.updated_at = datetime.now().isoformat()
    
    def get_plot_summary(self) -> str:
        """获取情节摘要"""
        if not self.plot_points:
            return "暂无情节记录"
        return "\n".join([f"{i+1}. {point}" for i, point in enumerate(self.plot_points)])
    
    # === 章节大纲管理 ===
    
    def add_chapter_outline(self, outline: ChapterOutline) -> None:
        """添加章节大纲"""
        self.chapter_outlines.append(outline)
        self.updated_at = datetime.now().isoformat()
    
    def get_chapter_outline(self, chapter_number: int) -> Optional[ChapterOutline]:
        """获取指定章节大纲"""
        for outline in self.chapter_outlines:
            if outline.chapter_number == chapter_number:
                return outline
        return None
    
    def update_chapter_outline(self, chapter_number: int, **kwargs) -> bool:
        """更新章节大纲"""
        outline = self.get_chapter_outline(chapter_number)
        if outline:
            for key, value in kwargs.items():
                if hasattr(outline, key):
                    setattr(outline, key, value)
            self.updated_at = datetime.now().isoformat()
            return True
        return False
    
    def get_next_ungenerated_outline(self) -> Optional[ChapterOutline]:
        """获取下一个未生成的大纲"""
        for outline in self.chapter_outlines:
            if outline.status == "planned":
                return outline
        return None
    
    def get_outline_summary(self) -> str:
        """获取大纲概览"""
        if not self.chapter_outlines:
            return "暂无章节大纲"
        
        summary_lines = []
        for outline in self.chapter_outlines:
            status_icon = "✅" if outline.status == "completed" else "⏳" if outline.status == "generated" else "📝"
            summary_lines.append(f"{status_icon} 第{outline.chapter_number}章: {outline.title} - {outline.summary[:30]}...")
        return "\n".join(summary_lines)
    
    # === 上下文信息 ===
    
    def get_story_context(self) -> str:
        """获取故事上下文信息"""
        context_parts = [
            f"【小说信息】",
            f"标题：{self.title}",
        ]
        
        if self.genre:
            context_parts.append(f"类型：{self.genre}")
        if self.background:
            context_parts.append(f"背景设定：{self.background}")
        if self.plot_outline:
            context_parts.append(f"故事大纲：{self.plot_outline}")
        if self.writing_style:
            context_parts.append(f"写作风格：{self.writing_style}")
        
        context_parts.append(f"\n【角色信息】")
        context_parts.append(self.get_all_characters_info())
        
        if self.plot_points:
            context_parts.append(f"\n【情节要点】")
            context_parts.append(self.get_plot_summary())
        
        return "\n".join(context_parts)
    
    def get_project_status(self) -> Dict:
        """获取项目状态"""
        return {
            "title": self.title,
            "genre": self.genre,
            "chapter_count": len(self.chapters),
            "character_count": len(self.characters),
            "total_words": self.get_total_word_count(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    # === 保存和加载 ===
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "genre": self.genre,
            "background": self.background,
            "plot_outline": self.plot_outline,
            "writing_style": self.writing_style,
            "target_audience": self.target_audience,
            "story_goal": self.story_goal,
            "characters": [char.to_dict() for char in self.characters],
            "chapters": [chap.to_dict() for chap in self.chapters],
            "plot_points": self.plot_points,
            "chapter_outlines": [outline.to_dict() for outline in self.chapter_outlines],
            "character_tracker": self.character_tracker.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    def save(self) -> str:
        """保存项目到JSON文件"""
        os.makedirs(self.project_path, exist_ok=True)
        
        file_path = os.path.join(self.project_path, "project.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        return file_path
    
    @classmethod
    def load(cls, title: str, project_dir: str = "projects") -> "NovelProject":
        """从JSON文件加载项目"""
        project_path = os.path.join(project_dir, title, "project.json")
        
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"项目文件不存在: {project_path}")
        
        with open(project_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        project = cls(title, project_dir)
        project.genre = data.get("genre", "")
        project.background = data.get("background", "")
        project.plot_outline = data.get("plot_outline", "")
        project.writing_style = data.get("writing_style", "")
        project.target_audience = data.get("target_audience", "")
        project.story_goal = data.get("story_goal", "")
        
        project.characters = [Character.from_dict(c) for c in data.get("characters", [])]
        project.chapters = [Chapter.from_dict(c) for c in data.get("chapters", [])]
        project.plot_points = data.get("plot_points", [])
        project.chapter_outlines = [ChapterOutline.from_dict(o) for o in data.get("chapter_outlines", [])]
        
        # 加载角色追踪数据
        if "character_tracker" in data:
            project.character_tracker = CharacterTracker.from_dict(data["character_tracker"])
        
        project.created_at = data.get("created_at", project.created_at)
        project.updated_at = data.get("updated_at", project.updated_at)
        
        return project
    
    @staticmethod
    def list_projects(project_dir: str = "projects") -> List[str]:
        """列出所有项目"""
        if not os.path.exists(project_dir):
            return []
        
        projects = []
        for item in os.listdir(project_dir):
            project_path = os.path.join(project_dir, item, "project.json")
            if os.path.exists(project_path):
                projects.append(item)
        
        return sorted(projects)
    
    def __repr__(self) -> str:
        return f"NovelProject(title='{self.title}', chapters={len(self.chapters)}, characters={len(self.characters)})"
