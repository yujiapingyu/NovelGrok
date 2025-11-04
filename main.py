#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelGrok - AI小说写作工具主程序
命令行界面入口
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入CLI模块
from novel_ai.cli.commands import main as cli_main

if __name__ == "__main__":
    cli_main()
