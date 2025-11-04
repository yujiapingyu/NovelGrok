#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能上下文管理器
解决AI写作中的token限制问题，通过分层架构优化上下文使用
"""

from typing import List, Dict, Optional
from ..utils.text_utils import count_tokens, extract_keywords, split_into_sentences
from .project import NovelProject, Chapter


class ContextManager:
    """
    上下文管理器
    核心功能：
    1. 分层上下文架构（基础信息、近期内容、历史摘要）
    2. 智能token优化和分配
    3. 自动摘要生成
    4. 动态内容选择
    """
    
    def __init__(self, max_tokens: int = 20000):
        """
        初始化上下文管理器
        
        Args:
            max_tokens: 最大token限制
        """
        self.max_tokens = max_tokens
        # 分配策略：基础信息30%，近期内容50%，历史摘要20%
        self.base_info_ratio = 0.3
        self.recent_content_ratio = 0.5
        self.history_summary_ratio = 0.2
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return count_tokens(text)
    
    # === 上下文构建 ===
    
    def build_writing_context(
        self,
        project: NovelProject,
        include_full_recent: int = 2,
        include_summary_count: int = 5,
    ) -> str:
        """
        构建写作上下文（用于生成新章节）
        
        Args:
            project: 小说项目
            include_full_recent: 包含最近N章的完整内容
            include_summary_count: 包含前N章的摘要
        
        Returns:
            构建好的上下文字符串
        """
        context_parts = []
        token_budget = self.max_tokens
        
        # 1. 基础信息（30%）
        base_info = self._build_base_info(project)
        base_tokens = self.count_tokens(base_info)
        context_parts.append(base_info)
        token_budget -= base_tokens
        
        # 2. 历史摘要（20%）
        if len(project.chapters) > include_full_recent:
            history_budget = int(self.max_tokens * self.history_summary_ratio)
            history_summary = self._build_history_summary(
                project,
                exclude_recent=include_full_recent,
                max_count=include_summary_count,
                token_budget=history_budget
            )
            if history_summary:
                context_parts.append(f"\n【前情提要】\n{history_summary}")
                token_budget -= self.count_tokens(history_summary)
        
        # 3. 近期内容（50%）
        recent_content = self._build_recent_content(
            project,
            count=include_full_recent,
            token_budget=token_budget
        )
        if recent_content:
            context_parts.append(f"\n【最近章节】\n{recent_content}")
        
        return "\n".join(context_parts)
    
    def build_improvement_context(
        self,
        chapter: Chapter,
        project: NovelProject,
        focus_area: str = ""
    ) -> str:
        """
        构建改进上下文（用于改进章节内容）
        
        Args:
            chapter: 要改进的章节
            project: 小说项目
            focus_area: 改进重点（如"增加对话"、"丰富描写"等）
        """
        context_parts = []
        
        # 基础信息
        context_parts.append(f"【小说信息】")
        context_parts.append(f"标题：{project.title}")
        if project.genre:
            context_parts.append(f"类型：{project.genre}")
        if project.writing_style:
            context_parts.append(f"写作风格：{project.writing_style}")
        
        # 角色信息（简化）
        if project.characters:
            char_names = "、".join([c.name for c in project.characters])
            context_parts.append(f"主要角色：{char_names}")
        
        # 当前章节
        context_parts.append(f"\n【待改进章节】")
        context_parts.append(f"## {chapter.title}")
        context_parts.append(chapter.content)
        
        # 改进要求
        if focus_area:
            context_parts.append(f"\n【改进重点】\n{focus_area}")
        
        return "\n".join(context_parts)
    
    # === 内部构建方法 ===
    
    def _build_base_info(self, project: NovelProject, simplified: bool = False) -> str:
        """构建基础信息"""
        parts = [f"【小说基本信息】"]
        parts.append(f"标题：{project.title}")
        
        if project.genre:
            parts.append(f"类型：{project.genre}")
        
        if project.background:
            parts.append(f"背景设定：{project.background}")
        
        if project.plot_outline:
            parts.append(f"故事大纲：{project.plot_outline}")
        
        if project.writing_style:
            parts.append(f"写作风格：{project.writing_style}")
        
        # 角色信息
        if not simplified and project.characters:
            parts.append(f"\n【角色设定】")
            for char in project.characters:
                parts.append(f"- {char.name}：{char.description}")
                if char.personality:
                    parts.append(f"  性格：{char.personality}")
        elif simplified and project.characters:
            char_list = "、".join([f"{c.name}（{c.description}）" for c in project.characters[:3]])
            parts.append(f"主要角色：{char_list}")
        
        # 情节要点
        if not simplified and project.plot_points:
            parts.append(f"\n【重要情节】")
            for i, point in enumerate(project.plot_points[-5:], 1):
                parts.append(f"{i}. {point}")
        
        return "\n".join(parts)
    
    def _build_history_summary(
        self,
        project: NovelProject,
        exclude_recent: int = 2,
        max_count: int = 5,
        token_budget: int = 2000
    ) -> str:
        """构建历史摘要"""
        if len(project.chapters) <= exclude_recent:
            return ""
        
        history_chapters = project.chapters[:-exclude_recent] if exclude_recent > 0 else project.chapters
        summary_parts = []
        current_tokens = 0
        
        # 从最新到最旧，但输出时反转
        for chapter in reversed(history_chapters[-max_count:]):
            summary_text = chapter.summary if chapter.summary else self.generate_simple_summary(chapter)
            summary_line = f"第{chapter.chapter_number}章《{chapter.title}》：{summary_text}"
            
            line_tokens = self.count_tokens(summary_line)
            if current_tokens + line_tokens > token_budget:
                break
            
            summary_parts.insert(0, summary_line)
            current_tokens += line_tokens
        
        return "\n".join(summary_parts)
    
    def _build_recent_content(
        self,
        project: NovelProject,
        count: int = 2,
        token_budget: int = 4000
    ) -> str:
        """构建近期内容"""
        recent_chapters = project.get_recent_chapters(count)
        if not recent_chapters:
            return ""
        
        content_parts = []
        current_tokens = 0
        
        for chapter in recent_chapters:
            chapter_text = f"## 第{chapter.chapter_number}章：{chapter.title}\n{chapter.content}"
            chapter_tokens = self.count_tokens(chapter_text)
            
            # 如果单章超出预算，进行截断
            if chapter_tokens > token_budget - current_tokens:
                # 保留前面的内容
                available_tokens = token_budget - current_tokens
                truncated = self._truncate_to_token_limit(chapter.content, available_tokens)
                chapter_text = f"## 第{chapter.chapter_number}章：{chapter.title}\n{truncated}\n[内容过长，已截断]"
            
            content_parts.append(chapter_text)
            current_tokens += self.count_tokens(chapter_text)
            
            if current_tokens >= token_budget:
                break
        
        return "\n\n".join(content_parts)
    
    def _truncate_to_token_limit(self, text: str, token_limit: int) -> str:
        """将文本截断到指定token限制"""
        sentences = split_into_sentences(text)
        result = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            if current_tokens + sentence_tokens > token_limit:
                break
            result.append(sentence)
            current_tokens += sentence_tokens
        
        return "。".join(result) + "。"
    
    # === 摘要生成 ===
    
    def generate_simple_summary(self, chapter: Chapter, max_length: int = 200) -> str:
        """
        生成简单摘要（基于规则，不使用AI）
        提取关键句子和关键词
        """
        content = chapter.content
        sentences = split_into_sentences(content)
        
        if not sentences:
            return "本章暂无内容"
        
        # 取前3句和最后1句
        summary_sentences = []
        if len(sentences) >= 4:
            summary_sentences = sentences[:3] + [sentences[-1]]
        else:
            summary_sentences = sentences
        
        summary = "。".join(summary_sentences)
        
        # 如果还是太长，截断
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return summary
    
    def generate_chapter_summary(self, chapter: Chapter, max_length: int = 300) -> str:
        """
        为章节生成摘要
        这个方法返回一个简单摘要，实际使用时可以用AI生成更好的摘要
        """
        # 提取关键信息
        keywords = extract_keywords(chapter.content, top_n=5)
        keyword_text = "、".join(keywords) if keywords else ""
        
        # 简单摘要
        simple_summary = self.generate_simple_summary(chapter, max_length)
        
        # 组合
        if keyword_text:
            return f"{simple_summary}\n关键词：{keyword_text}"
        return simple_summary
    
    # === 上下文分析 ===
    
    def analyze_context_usage(self, project: NovelProject) -> Dict:
        """
        分析上下文使用情况
        返回详细的token分配信息
        """
        base_info = self._build_base_info(project)
        base_tokens = self.count_tokens(base_info)
        
        recent_content = self._build_recent_content(project, count=2)
        recent_tokens = self.count_tokens(recent_content)
        
        history_summary = self._build_history_summary(project)
        history_tokens = self.count_tokens(history_summary)
        
        total_tokens = base_tokens + recent_tokens + history_tokens
        
        return {
            "max_tokens": self.max_tokens,
            "total_used": total_tokens,
            "remaining": self.max_tokens - total_tokens,
            "usage_percent": round(total_tokens / self.max_tokens * 100, 2),
            "breakdown": {
                "base_info": base_tokens,
                "recent_content": recent_tokens,
                "history_summary": history_tokens,
            }
        }
    
    def get_context_preview(self, project: NovelProject, max_display: int = 500) -> str:
        """获取上下文预览"""
        full_context = self.build_writing_context(project)
        
        if len(full_context) <= max_display:
            return full_context
        
        return full_context[:max_display] + f"\n\n... (还有{len(full_context) - max_display}个字符) ..."
