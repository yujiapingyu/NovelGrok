#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小说导入模块
支持导入外部小说文本，自动切分章节
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ImportedChapter:
    """导入的章节"""
    chapter_number: int
    title: str
    content: str
    word_count: int
    
    def __post_init__(self):
        if self.word_count == 0:
            self.word_count = len(self.content)


class NovelImporter:
    """小说导入器"""
    
    # 常见的章节标题模式
    CHAPTER_PATTERNS = [
        # 中文模式
        r'^第[0-9零一二三四五六七八九十百千万]+章[：:\s]*.+$',  # 第一章：标题
        r'^第[0-9零一二三四五六七八九十百千万]+章\s*$',  # 第一章
        r'^第[0-9零一二三四五六七八九十百千万]+回[：:\s]*.+$',  # 第一回：标题
        r'^第[0-9零一二三四五六七八九十百千万]+回\s*$',  # 第一回
        r'^[0-9]+\.[：:\s]*.+$',  # 1. 标题
        r'^[0-9]+、.+$',  # 1、标题
        r'^【第[0-9零一二三四五六七八九十百千万]+章】.+$',  # 【第一章】标题
        
        # 英文模式
        r'^Chapter\s+\d+[：:\s]*.+$',  # Chapter 1: Title
        r'^Chapter\s+\d+\s*$',  # Chapter 1
        r'^CHAPTER\s+\d+[：:\s]*.+$',  # CHAPTER 1: Title
    ]
    
    def __init__(self, max_file_size: Optional[int] = 1024 * 1024):  # 默认1MB，None表示不限制
        """
        初始化导入器
        
        Args:
            max_file_size: 最大文件大小（字节），None表示不限制
        """
        self.max_file_size = max_file_size
        self.chapter_patterns = [re.compile(pattern, re.MULTILINE | re.IGNORECASE) 
                                for pattern in self.CHAPTER_PATTERNS]
    
    def validate_file_size(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        验证文件大小
        
        Returns:
            (是否有效, 错误信息)
        """
        # 如果没有设置限制，直接返回有效
        if self.max_file_size is None:
            return True, None
        
        size = len(content.encode('utf-8'))
        if size > self.max_file_size:
            size_mb = size / (1024 * 1024)
            limit_mb = self.max_file_size / (1024 * 1024)
            return False, f"文件大小 {size_mb:.2f}MB 超过限制 {limit_mb:.2f}MB"
        return True, None
    
    def detect_chapter_pattern(self, content: str) -> Optional[re.Pattern]:
        """
        检测文本使用的章节标题模式
        
        Returns:
            匹配的正则表达式模式，如果没有找到则返回None
        """
        lines = content.split('\n')
        
        # 统计每个模式的匹配次数
        pattern_matches = {}
        for pattern in self.chapter_patterns:
            matches = 0
            for line in lines:
                line = line.strip()
                if line and pattern.match(line):
                    matches += 1
            if matches > 0:
                pattern_matches[pattern] = matches
        
        if not pattern_matches:
            return None
        
        # 返回匹配次数最多的模式
        return max(pattern_matches.items(), key=lambda x: x[1])[0]
    
    def split_chapters(self, content: str) -> List[ImportedChapter]:
        """
        将小说文本切分为章节
        
        Args:
            content: 小说文本内容
            
        Returns:
            章节列表
        """
        # 检测章节模式
        pattern = self.detect_chapter_pattern(content)
        
        if not pattern:
            # 没有检测到章节标题，作为单章处理
            return [ImportedChapter(
                chapter_number=1,
                title="导入章节",
                content=content.strip(),
                word_count=len(content)
            )]
        
        # 按行分割
        lines = content.split('\n')
        chapters = []
        current_chapter_lines = []
        current_title = None
        chapter_number = 0
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是章节标题
            if line_stripped and pattern.match(line_stripped):
                # 保存上一章节
                if current_title is not None and current_chapter_lines:
                    chapter_content = '\n'.join(current_chapter_lines).strip()
                    if chapter_content:  # 只保存有内容的章节
                        chapters.append(ImportedChapter(
                            chapter_number=chapter_number,
                            title=current_title,
                            content=chapter_content,
                            word_count=len(chapter_content)
                        ))
                
                # 开始新章节
                chapter_number += 1
                current_title = line_stripped
                current_chapter_lines = []
            else:
                # 累积章节内容
                if current_title is not None:
                    current_chapter_lines.append(line)
        
        # 保存最后一章
        if current_title is not None and current_chapter_lines:
            chapter_content = '\n'.join(current_chapter_lines).strip()
            if chapter_content:
                chapters.append(ImportedChapter(
                    chapter_number=chapter_number,
                    title=current_title,
                    content=chapter_content,
                    word_count=len(chapter_content)
                ))
        
        return chapters
    
    def get_import_summary(self, chapters: List[ImportedChapter]) -> Dict:
        """
        获取导入摘要信息
        
        Returns:
            包含统计信息的字典
        """
        if not chapters:
            return {
                'chapter_count': 0,
                'total_words': 0,
                'avg_words_per_chapter': 0,
                'min_words': 0,
                'max_words': 0,
            }
        
        word_counts = [ch.word_count for ch in chapters]
        
        return {
            'chapter_count': len(chapters),
            'total_words': sum(word_counts),
            'avg_words_per_chapter': int(sum(word_counts) / len(word_counts)),
            'min_words': min(word_counts),
            'max_words': max(word_counts),
        }
    
    def import_novel(self, content: str) -> Tuple[bool, List[ImportedChapter], Optional[str]]:
        """
        导入小说
        
        Args:
            content: 小说文本内容
            
        Returns:
            (是否成功, 章节列表, 错误信息)
        """
        # 验证文件大小
        valid, error = self.validate_file_size(content)
        if not valid:
            return False, [], error
        
        try:
            # 切分章节
            chapters = self.split_chapters(content)
            
            if not chapters:
                return False, [], "未能识别到任何章节"
            
            return True, chapters, None
            
        except Exception as e:
            return False, [], f"导入失败: {str(e)}"
    
    def preview_chapters(self, chapters: List[ImportedChapter], preview_length: int = 100) -> str:
        """
        生成章节预览文本
        
        Args:
            chapters: 章节列表
            preview_length: 每章预览字符数
            
        Returns:
            预览文本
        """
        if not chapters:
            return "无章节"
        
        preview_lines = []
        for chapter in chapters[:10]:  # 最多显示前10章
            content_preview = chapter.content[:preview_length]
            if len(chapter.content) > preview_length:
                content_preview += "..."
            
            preview_lines.append(
                f"第{chapter.chapter_number}章: {chapter.title} ({chapter.word_count}字)\n"
                f"  {content_preview}\n"
            )
        
        if len(chapters) > 10:
            preview_lines.append(f"... 还有 {len(chapters) - 10} 章")
        
        return "\n".join(preview_lines)
