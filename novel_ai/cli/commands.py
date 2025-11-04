#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行接口实现
"""

import sys
import argparse
from typing import Optional
from ..core.project import NovelProject, Character, Chapter
from ..core.context_manager import ContextManager
from ..api.grok_client import GrokClient
from ..utils.text_utils import format_word_count


def create_project_command(args):
    """创建新项目"""
    try:
        project = NovelProject(args.title)
        
        if args.genre:
            project.genre = args.genre
        if args.background:
            project.background = args.background
        if args.outline:
            project.plot_outline = args.outline
        if args.style:
            project.writing_style = args.style
        
        project.save()
        
        print(f"✓ 项目创建成功: {args.title}")
        print(f"  项目路径: {project.project_path}")
        
        status = project.get_project_status()
        print(f"\n项目信息:")
        print(f"  类型: {project.genre or '未设置'}")
        print(f"  章节数: {status['chapter_count']}")
        print(f"  角色数: {status['character_count']}")
        
    except Exception as e:
        print(f"❌ 创建失败: {e}", file=sys.stderr)
        sys.exit(1)


def add_character_command(args):
    """添加角色"""
    try:
        project = NovelProject.load(args.project)
        
        character = Character(
            name=args.name,
            description=args.description,
            personality=args.personality or "",
            background=args.background or "",
        )
        
        # 添加关系
        if args.relationships:
            for rel in args.relationships:
                if ':' in rel:
                    other_name, relation = rel.split(':', 1)
                    character.relationships[other_name.strip()] = relation.strip()
        
        project.add_character(character)
        project.save()
        
        print(f"✓ 角色添加成功: {args.name}")
        print(f"\n{character.get_full_description()}")
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 添加失败: {e}", file=sys.stderr)
        sys.exit(1)


def generate_chapter_command(args):
    """生成新章节"""
    try:
        project = NovelProject.load(args.project)
        
        print(f"正在生成章节...")
        print(f"项目: {project.title}")
        if args.title:
            print(f"标题: {args.title}")
        print()
        
        client = GrokClient()
        
        chapter = client.generate_new_chapter(
            project,
            chapter_title=args.title or "",
            writing_prompt=args.prompt or "",
            target_length=args.length,
        )
        
        # 生成摘要
        if args.summary:
            print("正在生成章节摘要...")
            chapter.summary = client.generate_chapter_summary(chapter, project)
        
        project.add_chapter(chapter)
        project.save()
        
        print(f"✓ 章节生成成功!")
        print(f"\n{'='*50}")
        print(f"第{chapter.chapter_number}章：{chapter.title}")
        print(f"{'='*50}")
        print(chapter.content)
        print(f"{'='*50}")
        print(f"字数: {chapter.word_count}")
        
        if chapter.summary:
            print(f"\n摘要: {chapter.summary}")
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ 配置错误: {e}", file=sys.stderr)
        print("提示: 请确保已设置XAI_API_KEY环境变量", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成失败: {e}", file=sys.stderr)
        sys.exit(1)


def improve_chapter_command(args):
    """改进章节"""
    try:
        project = NovelProject.load(args.project)
        
        chapter = project.get_chapter(args.chapter_number)
        if not chapter:
            print(f"❌ 章节不存在: 第{args.chapter_number}章", file=sys.stderr)
            sys.exit(1)
        
        print(f"正在改进第{args.chapter_number}章...")
        
        client = GrokClient()
        
        improved_content = client.improve_chapter(
            chapter,
            project,
            improvement_focus=args.focus or "整体改进",
        )
        
        # 保存原内容
        if args.save:
            project.update_chapter(args.chapter_number, improved_content)
            project.save()
            print(f"✓ 改进内容已保存!")
        else:
            print(f"✓ 改进完成（未保存，使用 --save 保存）")
        
        print(f"\n{'='*50}")
        print("改进后的内容:")
        print(f"{'='*50}")
        print(improved_content)
        print(f"{'='*50}")
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 改进失败: {e}", file=sys.stderr)
        sys.exit(1)


def suggest_plot_command(args):
    """获取情节建议"""
    try:
        project = NovelProject.load(args.project)
        
        print(f"正在分析项目并生成情节建议...")
        
        client = GrokClient()
        suggestions = client.suggest_plot_development(project, count=args.count)
        
        print(f"\n✓ 为《{project.title}》生成了 {len(suggestions)} 个情节建议：\n")
        
        for i, suggestion in enumerate(suggestions, 1):
            print(f"{i}. {suggestion}\n")
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成建议失败: {e}", file=sys.stderr)
        sys.exit(1)


def generate_summary_command(args):
    """生成章节摘要"""
    try:
        project = NovelProject.load(args.project)
        
        chapter = project.get_chapter(args.chapter_number)
        if not chapter:
            print(f"❌ 章节不存在: 第{args.chapter_number}章", file=sys.stderr)
            sys.exit(1)
        
        print(f"正在生成第{args.chapter_number}章的摘要...")
        
        client = GrokClient()
        summary = client.generate_chapter_summary(chapter, project)
        
        chapter.summary = summary
        project.save()
        
        print(f"✓ 摘要生成成功!\n")
        print(f"第{args.chapter_number}章《{chapter.title}》")
        print(f"摘要: {summary}")
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成摘要失败: {e}", file=sys.stderr)
        sys.exit(1)


def status_command(args):
    """查看项目状态"""
    try:
        project = NovelProject.load(args.project)
        
        status = project.get_project_status()
        
        print(f"\n{'='*60}")
        print(f"项目: {project.title}")
        print(f"{'='*60}")
        
        print(f"\n基本信息:")
        print(f"  类型: {project.genre or '未设置'}")
        print(f"  总字数: {format_word_count(status['total_words'])}")
        print(f"  章节数: {status['chapter_count']}")
        print(f"  角色数: {status['character_count']}")
        print(f"  创建时间: {status['created_at'][:10]}")
        print(f"  更新时间: {status['updated_at'][:10]}")
        
        if project.background:
            print(f"\n背景设定:")
            print(f"  {project.background}")
        
        if project.characters:
            print(f"\n角色列表:")
            for char in project.characters:
                print(f"  - {char.name}: {char.description}")
        
        if project.chapters:
            print(f"\n章节列表:")
            for chapter in project.chapters:
                print(f"  第{chapter.chapter_number}章: {chapter.title} ({chapter.word_count}字)")
        
        # 上下文分析
        if args.context:
            context_manager = ContextManager()
            analysis = context_manager.analyze_context_usage(project)
            
            print(f"\n上下文分析:")
            print(f"  Token限制: {analysis['max_tokens']}")
            print(f"  已使用: {analysis['total_used']} ({analysis['usage_percent']}%)")
            print(f"  剩余: {analysis['remaining']}")
            print(f"  分配:")
            print(f"    基础信息: {analysis['breakdown']['base_info']} tokens")
            print(f"    近期内容: {analysis['breakdown']['recent_content']} tokens")
            print(f"    历史摘要: {analysis['breakdown']['history_summary']} tokens")
        
        print()
        
    except FileNotFoundError:
        print(f"❌ 项目不存在: {args.project}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 查看状态失败: {e}", file=sys.stderr)
        sys.exit(1)


def list_projects_command(args):
    """列出所有项目"""
    try:
        projects = NovelProject.list_projects()
        
        if not projects:
            print("还没有创建任何项目")
            print("使用 'python main.py create-project' 创建新项目")
            return
        
        print(f"\n找到 {len(projects)} 个项目:\n")
        
        for title in projects:
            try:
                project = NovelProject.load(title)
                status = project.get_project_status()
                
                print(f"📖 {title}")
                print(f"   类型: {project.genre or '未设置'}")
                print(f"   章节: {status['chapter_count']} | 字数: {format_word_count(status['total_words'])}")
                print()
            except Exception as e:
                print(f"📖 {title} (加载失败: {e})\n")
        
    except Exception as e:
        print(f"❌ 列出项目失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """主命令行入口"""
    parser = argparse.ArgumentParser(
        description="NovelGrok - AI小说写作工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建项目
    create_parser = subparsers.add_parser('create-project', help='创建新项目')
    create_parser.add_argument('title', help='项目标题')
    create_parser.add_argument('--genre', help='小说类型')
    create_parser.add_argument('--background', help='背景设定')
    create_parser.add_argument('--outline', help='故事大纲')
    create_parser.add_argument('--style', help='写作风格')
    create_parser.set_defaults(func=create_project_command)
    
    # 添加角色
    char_parser = subparsers.add_parser('add-character', help='添加角色')
    char_parser.add_argument('project', help='项目名称')
    char_parser.add_argument('name', help='角色名称')
    char_parser.add_argument('description', help='角色描述')
    char_parser.add_argument('--personality', help='性格特征')
    char_parser.add_argument('--background', help='角色背景')
    char_parser.add_argument('--relationships', nargs='+', help='人物关系 (格式: 角色名:关系)')
    char_parser.set_defaults(func=add_character_command)
    
    # 生成章节
    gen_parser = subparsers.add_parser('generate-chapter', help='生成新章节 (需要API)')
    gen_parser.add_argument('project', help='项目名称')
    gen_parser.add_argument('--title', help='章节标题')
    gen_parser.add_argument('--prompt', help='写作提示')
    gen_parser.add_argument('--length', type=int, default=3500, help='目标字数 (默认3500)')
    gen_parser.add_argument('--summary', action='store_true', help='自动生成摘要')
    gen_parser.set_defaults(func=generate_chapter_command)
    
    # 改进章节
    improve_parser = subparsers.add_parser('improve-chapter', help='改进章节内容 (需要API)')
    improve_parser.add_argument('project', help='项目名称')
    improve_parser.add_argument('chapter_number', type=int, help='章节编号')
    improve_parser.add_argument('--focus', help='改进重点')
    improve_parser.add_argument('--save', action='store_true', help='保存改进后的内容')
    improve_parser.set_defaults(func=improve_chapter_command)
    
    # 情节建议
    suggest_parser = subparsers.add_parser('suggest-plot', help='获取情节建议 (需要API)')
    suggest_parser.add_argument('project', help='项目名称')
    suggest_parser.add_argument('--count', type=int, default=3, help='建议数量 (默认3)')
    suggest_parser.set_defaults(func=suggest_plot_command)
    
    # 生成摘要
    summary_parser = subparsers.add_parser('generate-summary', help='生成章节摘要 (需要API)')
    summary_parser.add_argument('project', help='项目名称')
    summary_parser.add_argument('chapter_number', type=int, help='章节编号')
    summary_parser.set_defaults(func=generate_summary_command)
    
    # 查看状态
    status_parser = subparsers.add_parser('status', help='查看项目状态')
    status_parser.add_argument('project', help='项目名称')
    status_parser.add_argument('--context', action='store_true', help='显示上下文分析')
    status_parser.set_defaults(func=status_command)
    
    # 列出项目
    list_parser = subparsers.add_parser('list-projects', help='列出所有项目')
    list_parser.set_defaults(func=list_projects_command)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # 执行命令
    args.func(args)


if __name__ == '__main__':
    main()
