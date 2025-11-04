#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理工具函数
"""

import re
from typing import List


def count_tokens(text: str) -> int:
    """
    估算文本的token数量
    对于中文，大约1个字符=1.5个token
    对于英文，大约1个单词=1.3个token
    """
    if not text:
        return 0
    
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计英文单词
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
    # 统计其他字符（标点、数字等）
    other_chars = len(text) - chinese_chars - sum(len(word) for word in re.findall(r'\b[a-zA-Z]+\b', text))
    
    # 估算token数
    tokens = int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)
    return max(tokens, 1)


def count_chinese_chars(text: str) -> int:
    """统计中文字符数（不包括标点和空格）"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    简单的关键词提取
    提取高频词汇（排除常见停用词）
    """
    # 中文停用词
    stopwords = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
        '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
        '看', '好', '自己', '这', '那', '他', '她', '们', '吗', '吧', '啊', '呢',
    }
    
    # 提取中文词汇（简单按2-4字切分）
    words = []
    for length in [4, 3, 2]:
        pattern = f'[\u4e00-\u9fff]{{{length}}}'
        words.extend(re.findall(pattern, text))
    
    # 统计频率
    word_freq = {}
    for word in words:
        if word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # 返回top N
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:top_n]]


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def split_into_sentences(text: str) -> List[str]:
    """将文本分割成句子"""
    # 按中文句号、问号、感叹号分割
    sentences = re.split(r'[。！？\n]+', text)
    # 过滤空句子
    return [s.strip() for s in sentences if s.strip()]


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两段文本的相似度（基于字符重叠）
    返回0-1之间的值
    """
    if not text1 or not text2:
        return 0.0
    
    # 提取字符集
    chars1 = set(text1)
    chars2 = set(text2)
    
    # 计算交集和并集
    intersection = len(chars1 & chars2)
    union = len(chars1 | chars2)
    
    return intersection / union if union > 0 else 0.0


def format_word_count(count: int) -> str:
    """格式化字数显示"""
    if count < 1000:
        return f"{count}字"
    elif count < 20000:
        return f"{count/1000:.1f}千字"
    else:
        return f"{count/20000:.1f}万字"


def clean_text(text: str) -> str:
    """清理文本（去除多余空白、统一标点等）"""
    # 去除多余空行
    text = re.sub(r'\n\s*\n', '\n\n', text)
    # 去除行首行尾空白
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines)
