#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelGrok Web API
提供RESTful API接口供前端调用
"""

import os
import traceback
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

from novel_ai.core.project import NovelProject, Character, Chapter
from novel_ai.core.context_manager import ContextManager
from novel_ai.api.grok_client import GrokClient
from novel_ai.utils.text_utils import format_word_count
import json
import threading

# 加载环境变量
load_dotenv()

# 创建Flask应用
app = Flask(__name__)

# CORS 配置 - 支持公网访问
CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# 配置 session 密钥（从环境变量读取，如果没有则生成一个）
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # session 有效期24小时
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 允许跨站 cookie
use_https = os.getenv('WEB_USE_HTTPS', 'False').lower() in ('true', '1', 'yes')
app.config['SESSION_COOKIE_SECURE'] = use_https  # 从环境变量读取

# 密码配置（从环境变量读取）
# 默认密码: novelgrok2024 （请在 .env 中修改）
PASSWORD_HASH = os.getenv('WEB_PASSWORD_HASH') or generate_password_hash('novelgrok2024')

# 全局变量
context_manager = ContextManager(max_tokens=20000)

# 章节生成状态管理
generation_status = {
    # 格式: 'project_title': {'status': 'generating', 'progress': 50, 'message': '正在生成...'}
}

# 任务持久化目录
TASKS_DIR = os.path.join(os.path.dirname(__file__), 'tasks')
os.makedirs(TASKS_DIR, exist_ok=True)

# 任务恢复锁
task_recovery_lock = threading.Lock()


# ========== 任务持久化工具函数 ==========

def save_task_status(task_key, status):
    """保存任务状态到文件"""
    try:
        task_file = os.path.join(TASKS_DIR, f"{task_key}.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[任务持久化] 保存任务状态失败: {e}")


def load_task_status(task_key):
    """从文件加载任务状态"""
    try:
        task_file = os.path.join(TASKS_DIR, f"{task_key}.json")
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[任务持久化] 加载任务状态失败: {e}")
    return None


def delete_task_status(task_key):
    """删除任务状态文件"""
    try:
        task_file = os.path.join(TASKS_DIR, f"{task_key}.json")
        if os.path.exists(task_file):
            os.remove(task_file)
    except Exception as e:
        print(f"[任务持久化] 删除任务状态失败: {e}")


def recover_pending_tasks():
    """恢复未完成的批量生成任务"""
    with task_recovery_lock:
        try:
            print("[任务恢复] 检查未完成的任务...")
            task_files = [f for f in os.listdir(TASKS_DIR) if f.endswith('.json')]
            
            for task_file in task_files:
                task_key = task_file[:-5]  # 去掉 .json 后缀
                status = load_task_status(task_key)
                
                if not status:
                    continue
                
                # 只恢复批量生成任务
                if not task_key.endswith('_batch'):
                    continue
                
                # 只恢复进行中的任务
                if status.get('status') != 'generating':
                    print(f"[任务恢复] 跳过已完成任务: {task_key}")
                    continue
                
                project_title = task_key.replace('_batch', '')
                print(f"[任务恢复] 恢复任务: {project_title}")
                
                # 将状态加载到内存
                generation_status[task_key] = status
                
                # 获取剩余待生成的大纲
                try:
                    project = NovelProject.load(project_title)
                    completed_chapters = set(status.get('completed_chapters', []))
                    all_chapter_numbers = status.get('all_chapter_numbers', [])
                    
                    # 找出还没生成的章节
                    remaining_numbers = [n for n in all_chapter_numbers if n not in completed_chapters]
                    
                    if not remaining_numbers:
                        print(f"[任务恢复] 任务已全部完成: {project_title}")
                        status['status'] = 'completed'
                        status['message'] = '所有章节已生成完成'
                        save_task_status(task_key, status)
                        continue
                    
                    # 获取对应的大纲
                    outlines_to_generate = [
                        o for o in project.chapter_outlines
                        if o.chapter_number in remaining_numbers
                    ]
                    outlines_to_generate.sort(key=lambda x: x.chapter_number)
                    
                    if not outlines_to_generate:
                        print(f"[任务恢复] 无可用大纲，标记任务完成: {project_title}")
                        status['status'] = 'completed'
                        save_task_status(task_key, status)
                        continue
                    
                    print(f"[任务恢复] 继续生成剩余 {len(outlines_to_generate)} 章")
                    
                    # 重新启动批量生成线程
                    enable_tracking = status.get('enable_character_tracking', False)
                    thread = threading.Thread(
                        target=batch_generate_background,
                        args=(project_title, outlines_to_generate, task_key, enable_tracking),
                        kwargs={'is_recovery': True}
                    )
                    thread.daemon = True
                    thread.start()
                    
                except Exception as e:
                    print(f"[任务恢复] 恢复任务失败 {project_title}: {e}")
                    traceback.print_exc()
                    status['status'] = 'failed'
                    status['message'] = f'恢复任务失败: {str(e)}'
                    save_task_status(task_key, status)
        
        except Exception as e:
            print(f"[任务恢复] 整体恢复失败: {e}")
            traceback.print_exc()


# ========== 登录验证 ==========

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # API 请求返回 401
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': '未登录', 'require_login': True}), 401
            # 页面请求重定向到登录页
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# ========== 页面路由 ==========

@app.route('/login')
def login_page():
    """登录页面"""
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def login():
    """登录接口"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        if check_password_hash(PASSWORD_HASH, password):
            session['logged_in'] = True
            session.permanent = True  # 使用持久化 session
            return jsonify({
                'success': True,
                'message': '登录成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '密码错误'
            }), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """退出登录"""
    session.clear()
    return jsonify({
        'success': True,
        'message': '已退出登录'
    })


@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """检查登录状态"""
    return jsonify({
        'success': True,
        'logged_in': session.get('logged_in', False)
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取前端功能配置"""
    enable_outline = os.getenv('ENABLE_OUTLINE_MODE', 'True').lower() in ('true', '1', 'yes')
    enable_import = os.getenv('ENABLE_IMPORT_NOVEL', 'True').lower() in ('true', '1', 'yes')
    max_outline_chapters = int(os.getenv('MAX_OUTLINE_CHAPTERS', '100'))
    
    return jsonify({
        'success': True,
        'config': {
            'enable_outline_mode': enable_outline,
            'enable_import_novel': enable_import,
            'max_outline_chapters': max_outline_chapters
        }
    })


@app.route('/')
@login_required
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/reader')
@login_required
def reader():
    """小说阅读器页面"""
    return render_template('reader.html')


# ========== 全局请求拦截 ==========

@app.before_request
def check_login():
    """所有请求前检查登录状态（除了登录相关接口）"""
    # 白名单：不需要登录的路径
    whitelist = ['/login', '/api/login', '/api/check-auth', '/api/config', '/static/']
    
    # 检查是否在白名单中
    for path in whitelist:
        if request.path.startswith(path):
            return None
    
    # 其他所有请求都需要登录
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': '未登录', 'require_login': True}), 401
        return redirect(url_for('login_page'))
    
    return None


# ========== API路由 ==========

# === 项目管理 ===

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """获取所有项目列表"""
    try:
        project_names = NovelProject.list_projects()
        projects = []
        
        for name in project_names:
            try:
                project = NovelProject.load(name)
                status = project.get_project_status()
                projects.append({
                    'title': project.title,
                    'genre': project.genre,
                    'background': project.background,
                    'chapter_count': status['chapter_count'],
                    'character_count': status['character_count'],
                    'total_words': status['total_words'],
                    'created_at': status['created_at'],
                    'updated_at': status['updated_at'],
                })
            except Exception as e:
                print(f"加载项目 {name} 失败: {e}")
                continue
        
        return jsonify({
            'success': True,
            'data': projects
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>', methods=['GET'])
def get_project(project_title):
    """获取项目详情"""
    try:
        project = NovelProject.load(project_title)
        status = project.get_project_status()
        
        # 上下文分析
        analysis = context_manager.analyze_context_usage(project)
        
        return jsonify({
            'success': True,
            'data': {
                'title': project.title,
                'genre': project.genre,
                'background': project.background,
                'plot_outline': project.plot_outline,
                'writing_style': project.writing_style,
                'target_audience': project.target_audience,
                'style_guide': project.style_guide,
                'characters': [char.to_dict() for char in project.characters],
                'chapters': [chap.to_dict() for chap in project.chapters],
                'plot_points': project.plot_points,
                'status': status,
                'context_analysis': analysis,
                'character_tracker': project.character_tracker.to_dict(),  # 添加角色追踪数据
            }
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects', methods=['POST'])
def create_project():
    """创建新项目"""
    try:
        data = request.json
        title = data.get('title')
        
        if not title:
            return jsonify({
                'success': False,
                'error': '项目标题不能为空'
            }), 400
        
        # 检查项目是否已存在
        existing_projects = NovelProject.list_projects()
        if title in existing_projects:
            return jsonify({
                'success': False,
                'error': f'项目 "{title}" 已存在'
            }), 400
        
        project = NovelProject(title)
        project.genre = data.get('genre', '')
        project.background = data.get('background', '')
        project.plot_outline = data.get('plot_outline', '')
        project.writing_style = data.get('writing_style', '')
        project.target_audience = data.get('target_audience', '')
        
        project.save()
        
        return jsonify({
            'success': True,
            'message': f'项目创建成功: {title}',
            'data': {
                'title': project.title
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>', methods=['PUT'])
def update_project(project_title):
    """更新项目信息"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        if 'genre' in data:
            project.genre = data['genre']
        if 'background' in data:
            project.background = data['background']
        if 'plot_outline' in data:
            project.plot_outline = data['plot_outline']
        if 'writing_style' in data:
            project.writing_style = data['writing_style']
        if 'target_audience' in data:
            project.target_audience = data['target_audience']
        if 'style_guide' in data:
            project.style_guide = data['style_guide']
        
        project.save()
        
        return jsonify({
            'success': True,
            'message': '项目更新成功'
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/analyze', methods=['POST'])
def analyze_project_with_ai(project_title):
    """使用AI分析项目，自动生成类型、背景和大纲"""
    try:
        project = NovelProject.load(project_title)
        
        if not project.chapters or len(project.chapters) == 0:
            print(f"[AI分析] 错误: 项目 '{project_title}' 中没有章节")
            print(f"[AI分析] 章节列表: {project.chapters}")
            return jsonify({
                'success': False,
                'error': f'项目中没有章节，无法分析。当前章节数: {len(project.chapters) if project.chapters else 0}'
            }), 400
        
        print(f"[AI分析] 开始分析项目 '{project_title}'")
        print(f"[AI分析] 章节数: {len(project.chapters)}")
        
        client = GrokClient()
        
        import time
        start_time = time.time()
        
        # 调用AI分析
        analysis = client.analyze_project_info(project)
        
        # 更新项目信息
        project.genre = analysis.get('genre', '')
        project.background = analysis.get('background', '')
        project.plot_outline = analysis.get('plot_outline', '')
        
        project.save()
        
        elapsed = time.time() - start_time
        print(f"[AI分析] 分析完成，耗时 {elapsed:.1f} 秒")
        
        return jsonify({
            'success': True,
            'data': {
                'genre': analysis.get('genre', ''),
                'background': analysis.get('background', ''),
                'plot_outline': analysis.get('plot_outline', ''),
                'message': 'AI分析完成',
                'elapsed_time': f'{elapsed:.1f}秒'
            }
        })
        
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        print(f"[AI分析] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>', methods=['DELETE'])
def delete_project(project_title):
    """删除项目"""
    try:
        import shutil
        project = NovelProject.load(project_title)
        project_path = project.project_path
        
        # 删除项目目录
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        
        return jsonify({
            'success': True,
            'message': f'项目已删除: {project_title}'
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 角色管理 ===

@app.route('/api/projects/<project_title>/characters', methods=['GET'])
def get_characters(project_title):
    """获取项目的所有角色"""
    try:
        project = NovelProject.load(project_title)
        return jsonify({
            'success': True,
            'data': [char.to_dict() for char in project.characters]
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters', methods=['POST'])
def add_character(project_title):
    """添加角色"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        character = Character(
            name=data.get('name', ''),
            description=data.get('description', ''),
            personality=data.get('personality', ''),
            background=data.get('background', ''),
            relationships=data.get('relationships', {})
        )
        
        project.add_character(character)
        project.save()
        
        return jsonify({
            'success': True,
            'message': f'角色添加成功: {character.name}',
            'data': character.to_dict()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters/<character_name>', methods=['PUT'])
def update_character(project_title, character_name):
    """更新角色信息"""
    try:
        project = NovelProject.load(project_title)
        character = project.get_character(character_name)
        
        if not character:
            return jsonify({
                'success': False,
                'error': f'角色不存在: {character_name}'
            }), 404
        
        data = request.json
        if 'name' in data:
            character.name = data['name']
        if 'description' in data:
            character.description = data['description']
        if 'personality' in data:
            character.personality = data['personality']
        if 'background' in data:
            character.background = data['background']
        if 'relationships' in data:
            character.relationships = data['relationships']
        
        project.save()
        
        return jsonify({
            'success': True,
            'message': '角色更新成功',
            'data': character.to_dict()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters/<character_name>', methods=['DELETE'])
def delete_character(project_title, character_name):
    """删除角色"""
    try:
        project = NovelProject.load(project_title)
        
        if project.remove_character(character_name):
            project.save()
            return jsonify({
                'success': True,
                'message': f'角色已删除: {character_name}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'角色不存在: {character_name}'
            }), 404
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 角色别名管理 ===

@app.route('/api/projects/<project_title>/characters/<character_name>/aliases', methods=['GET'])
def get_character_aliases(project_title, character_name):
    """获取角色的所有别名"""
    try:
        project = NovelProject.load(project_title)
        char = project.get_character_by_exact_name(character_name)
        
        if not char:
            return jsonify({
                'success': False,
                'error': f'角色不存在: {character_name}'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'name': char.name,
                'aliases': char.aliases
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters/<character_name>/aliases', methods=['POST'])
def add_character_alias(project_title, character_name):
    """为角色添加别名"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        alias = data.get('alias', '').strip()
        
        if not alias:
            return jsonify({
                'success': False,
                'error': '别名不能为空'
            }), 400
        
        # 检查别名是否已经被其他角色使用
        existing_char = project.get_character(alias)
        if existing_char and existing_char.name != character_name:
            return jsonify({
                'success': False,
                'error': f'别名"{alias}"已被角色"{existing_char.name}"使用'
            }), 400
        
        if project.add_character_alias(character_name, alias):
            project.save()
            return jsonify({
                'success': True,
                'message': f'别名已添加: {alias}',
                'data': {
                    'name': character_name,
                    'aliases': project.get_character_by_exact_name(character_name).aliases
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '添加别名失败（可能已存在或角色不存在）'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters/<character_name>/aliases/<alias>', methods=['DELETE'])
def remove_character_alias(project_title, character_name, alias):
    """删除角色别名"""
    try:
        project = NovelProject.load(project_title)
        char = project.get_character_by_exact_name(character_name)
        
        if not char:
            return jsonify({
                'success': False,
                'error': f'角色不存在: {character_name}'
            }), 404
        
        if alias in char.aliases:
            char.aliases.remove(alias)
            project.save()
            return jsonify({
                'success': True,
                'message': f'别名已删除: {alias}',
                'data': {
                    'name': character_name,
                    'aliases': char.aliases
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'别名不存在: {alias}'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/characters/merge', methods=['POST'])
def merge_characters(project_title):
    """合并角色（将多个角色识别为同一个）"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        main_name = data.get('main_name', '').strip()
        alias_names = data.get('alias_names', [])
        
        if not main_name:
            return jsonify({
                'success': False,
                'error': '主角色名不能为空'
            }), 400
        
        if not alias_names:
            return jsonify({
                'success': False,
                'error': '要合并的别名列表不能为空'
            }), 400
        
        if project.merge_character_aliases(main_name, alias_names):
            project.save()
            return jsonify({
                'success': True,
                'message': f'已将 {len(alias_names)} 个角色合并到 {main_name}',
                'data': {
                    'name': main_name,
                    'aliases': project.get_character_by_exact_name(main_name).aliases
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '合并失败（主角色可能不存在）'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 章节管理 ===

@app.route('/api/projects/<project_title>/chapters', methods=['GET'])
def get_chapters(project_title):
    """获取项目的所有章节"""
    try:
        project = NovelProject.load(project_title)
        return jsonify({
            'success': True,
            'data': [chap.to_dict() for chap in project.chapters]
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/chapters/<int:chapter_number>', methods=['GET'])
def get_chapter(project_title, chapter_number):
    """获取指定章节"""
    try:
        project = NovelProject.load(project_title)
        chapter = project.get_chapter(chapter_number)
        
        if not chapter:
            return jsonify({
                'success': False,
                'error': f'章节不存在: 第{chapter_number}章'
            }), 404
        
        return jsonify({
            'success': True,
            'data': chapter.to_dict()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/chapters', methods=['POST'])
def add_chapter(project_title):
    """添加章节（手动）"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        chapter = Chapter(
            title=data.get('title', ''),
            content=data.get('content', ''),
            summary=data.get('summary', '')
        )
        
        project.add_chapter(chapter)
        project.save()
        
        return jsonify({
            'success': True,
            'message': f'章节添加成功: {chapter.title}',
            'data': chapter.to_dict()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/chapters/<int:chapter_number>', methods=['PUT'])
def update_chapter(project_title, chapter_number):
    """更新章节内容"""
    try:
        project = NovelProject.load(project_title)
        chapter = project.get_chapter(chapter_number)
        
        if not chapter:
            return jsonify({
                'success': False,
                'error': f'章节不存在: 第{chapter_number}章'
            }), 404
        
        data = request.json
        if 'title' in data:
            chapter.title = data['title']
        if 'content' in data:
            chapter.update_content(data['content'])
        if 'summary' in data:
            chapter.summary = data['summary']
        
        project.save()
        
        return jsonify({
            'success': True,
            'message': '章节更新成功',
            'data': chapter.to_dict()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === AI生成功能 ===

@app.route('/api/projects/<project_title>/generate-chapter', methods=['POST'])
def generate_chapter(project_title):
    """使用AI生成新章节"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        # 检查API配置
        if not os.getenv('XAI_API_KEY'):
            return jsonify({
                'success': False,
                'error': '未配置API密钥，请在.env文件中设置XAI_API_KEY'
            }), 400
        
        # 设置生成状态
        generation_status[project_title] = {
            'status': 'generating',
            'progress': 10,
            'message': '正在准备生成...',
            'stage': 'preparing'
        }
        
        client = GrokClient()
        
        # 更新状态
        generation_status[project_title].update({
            'progress': 30,
            'message': '正在生成章节内容...',
            'stage': 'generating_content'
        })
        
        chapter = client.generate_new_chapter(
            project,
            chapter_title=data.get('title', ''),
            writing_prompt=data.get('prompt', ''),
            target_length=data.get('length', 3500)
        )
        
        # 更新状态
        generation_status[project_title].update({
            'progress': 70,
            'message': '章节生成完成，正在保存...',
            'stage': 'saving'
        })
        
        # 生成摘要
        if data.get('generate_summary', False):
            chapter.summary = client.generate_chapter_summary(chapter, project)
        
        project.add_chapter(chapter)
        
        # 🔥 新增：检测新角色
        new_characters_detected = []
        try:
            generation_status[project_title].update({
                'progress': 75,
                'message': '正在检测新角色...',
                'stage': 'detecting_characters'
            })
            existing_char_names = [c.name for c in project.characters]
            new_characters_detected = client.analyze_new_characters(chapter, existing_char_names)
            if new_characters_detected:
                print(f"🆕 发现 {len(new_characters_detected)} 个新角色: {[c['name'] for c in new_characters_detected]}")
        except Exception as e:
            print(f"⚠ 新角色检测失败（不影响章节生成）: {e}")
        
        # 🔥 自动分析并更新角色追踪
        try:
            if len(project.characters) > 0:  # 只有存在角色时才分析
                generation_status[project_title].update({
                    'progress': 85,
                    'message': '正在分析角色追踪...',
                    'stage': 'analyzing_characters'
                })
                client.auto_update_character_tracker(project, chapter)
                print(f"✓ 章节 {chapter.chapter_number} 的角色追踪已自动更新")
        except Exception as e:
            print(f"⚠ 角色追踪分析失败（不影响章节生成）: {e}")
        
        project.save()
        
        # 更新状态为完成
        generation_status[project_title] = {
            'status': 'completed',
            'progress': 100,
            'message': '章节生成完成！',
            'stage': 'completed',
            'chapter_number': chapter.chapter_number,
            'new_characters': new_characters_detected  # 添加新角色信息
        }
        
        return jsonify({
            'success': True,
            'message': '章节生成成功',
            'data': {
                **chapter.to_dict(),
                'character_tracking_updated': len(project.characters) > 0,
                'new_characters_detected': new_characters_detected  # 返回检测到的新角色
            }
        })
    except FileNotFoundError:
        generation_status[project_title] = {
            'status': 'error',
            'message': f'项目不存在: {project_title}'
        }
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except ValueError as e:
        generation_status[project_title] = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        traceback.print_exc()
        generation_status[project_title] = {
            'status': 'error',
            'message': f'生成失败: {str(e)}'
        }
        return jsonify({
            'success': False,
            'error': f'生成失败: {str(e)}'
        }), 500


@app.route('/api/projects/<project_title>/generation-status', methods=['GET'])
def get_generation_status(project_title):
    """获取章节生成状态（用于轮询）"""
    status = generation_status.get(project_title, {
        'status': 'idle',
        'message': '无生成任务'
    })
    
    return jsonify({
        'success': True,
        'data': status
    })


@app.route('/api/projects/<project_title>/suggest-plot', methods=['POST'])
def suggest_plot(project_title):
    """获取情节建议"""
    try:
        project = NovelProject.load(project_title)
        data = request.json
        
        if not os.getenv('XAI_API_KEY'):
            return jsonify({
                'success': False,
                'error': '未配置API密钥'
            }), 400
        
        client = GrokClient()
        suggestions = client.suggest_plot_development(
            project,
            count=data.get('count', 3)
        )
        
        return jsonify({
            'success': True,
            'data': suggestions
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'生成建议失败: {str(e)}'
        }), 500


@app.route('/api/projects/<project_title>/generate-chapter-idea', methods=['POST'])
def generate_chapter_idea(project_title):
    """生成章节创意（标题和写作提示）"""
    try:
        project = NovelProject.load(project_title)
        
        if not os.getenv('XAI_API_KEY'):
            return jsonify({
                'success': False,
                'error': '未配置API密钥'
            }), 400
        
        client = GrokClient()
        idea = client.generate_chapter_idea(project)
        
        return jsonify({
            'success': True,
            'data': idea
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'生成创意失败: {str(e)}'
        }), 500


@app.route('/api/projects/<project_title>/chapters/<int:chapter_number>/summary', methods=['POST'])
def generate_summary(project_title, chapter_number):
    """为章节生成摘要"""
    try:
        project = NovelProject.load(project_title)
        chapter = project.get_chapter(chapter_number)
        
        if not chapter:
            return jsonify({
                'success': False,
                'error': f'章节不存在: 第{chapter_number}章'
            }), 404
        
        if not os.getenv('XAI_API_KEY'):
            return jsonify({
                'success': False,
                'error': '未配置API密钥'
            }), 400
        
        client = GrokClient()
        summary = client.generate_chapter_summary(chapter, project)
        
        chapter.summary = summary
        project.save()
        
        return jsonify({
            'success': True,
            'message': '摘要生成成功',
            'data': {
                'summary': summary
            }
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'生成摘要失败: {str(e)}'
        }), 500


# === 角色追踪系统API ===

@app.route('/api/projects/<project_title>/character-tracker/<character_name>', methods=['GET'])
def get_character_tracking_info(project_title, character_name):
    """获取角色完整追踪信息"""
    try:
        project = NovelProject.load(project_title)
        tracker = project.character_tracker
        
        return jsonify({
            'success': True,
            'data': {
                'experiences': [exp.to_dict() for exp in tracker.get_character_experiences(character_name)],
                'relationships': [rel.to_dict() for rel in tracker.get_all_relationships(character_name)],
                'personality_traits': [trait.to_dict() for trait in tracker.get_personality_traits(character_name)],
                'personality_evolution': [evo.to_dict() for evo in tracker.get_personality_evolution(character_name)],
                'growth_analysis': tracker.analyze_character_growth(character_name),
                'timeline': tracker.get_character_timeline(character_name)
            }
        })
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'项目不存在: {project_title}'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects/<project_title>/character-tracker/<character_name>/experiences', methods=['POST'])
def add_character_experience(project_title, character_name):
    """添加角色经历"""
    try:
        data = request.get_json()
        project = NovelProject.load(project_title)
        
        project.character_tracker.add_experience(
            character_name=character_name,
            chapter_number=data['chapter_number'],
            event_type=data['event_type'],
            description=data['description'],
            impact=data.get('impact', 'neutral'),
            related_characters=data.get('related_characters', [])
        )
        
        project.save()
        
        return jsonify({'success': True, 'message': '经历添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects/<project_title>/character-tracker/<character_name>/relationships', methods=['POST'])
def add_character_relationship(project_title, character_name):
    """添加或更新角色关系"""
    try:
        data = request.get_json()
        project = NovelProject.load(project_title)
        
        project.character_tracker.add_relationship(
            character_name=character_name,
            target_character=data['target_character'],
            relationship_type=data['relationship_type'],
            intimacy_level=data.get('intimacy_level', 50),
            description=data.get('description', ''),
            first_met_chapter=data.get('first_met_chapter')
        )
        
        project.save()
        
        return jsonify({'success': True, 'message': '关系添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects/<project_title>/character-tracker/<character_name>/personality', methods=['POST'])
def set_character_personality(project_title, character_name):
    """设置角色性格特质"""
    try:
        data = request.get_json()
        project = NovelProject.load(project_title)
        
        project.character_tracker.set_personality_traits(
            character_name=character_name,
            traits=data['traits']
        )
        
        project.save()
        
        return jsonify({'success': True, 'message': '性格特质设置成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects/<project_title>/relationship-network', methods=['GET'])
def get_relationship_network(project_title):
    """获取关系网络（用于可视化）"""
    try:
        project = NovelProject.load(project_title)
        network = project.character_tracker.get_relationship_network()
        
        return jsonify({
            'success': True,
            'data': network
        })
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'项目不存在: {project_title}'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/projects/<project_title>/analyze-chapter/<int:chapter_number>', methods=['POST'])
def analyze_chapter_for_tracking(project_title, chapter_number):
    """分析章节并自动更新角色追踪（同时检测新角色和别名）"""
    try:
        project = NovelProject.load(project_title)
        chapter = project.get_chapter(chapter_number)
        
        if not chapter:
            return jsonify({'success': False, 'error': f'章节不存在: {chapter_number}'}), 404
        
        if not os.getenv('XAI_API_KEY'):
            return jsonify({'success': False, 'error': 'API密钥未配置'}), 400
        
        client = GrokClient()
        
        # 步骤1: 检测新角色
        existing_char_names = [char.name for char in project.characters]
        new_chars = client.analyze_new_characters(chapter, existing_char_names)
        
        new_character_names = []
        if new_chars:
            from novel_ai.core.project import Character
            for char_data in new_chars:
                character = Character(
                    name=char_data['name'],
                    description=char_data['description'],
                    personality=char_data.get('personality', '')
                )
                project.add_character(character)
                new_character_names.append(char_data['name'])
            project.save()
        
        # 步骤2: 更新角色追踪（会自动识别别名）
        client.auto_update_character_tracker(project, chapter)
        
        project.save()
        
        message = '章节分析完成，角色追踪已更新'
        if new_character_names:
            message += f'，发现新角色: {", ".join(new_character_names)}'
        
        return jsonify({
            'success': True,
            'message': message,
            'new_characters': new_character_names
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === 工具接口 ===

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    has_api_key = bool(os.getenv('XAI_API_KEY'))
    
    return jsonify({
        'success': True,
        'data': {
            'status': 'running',
            'api_configured': has_api_key
        }
    })


@app.route('/api/balance', methods=['GET'])
def get_api_balance():
    """获取API余额信息"""
    try:
        client = GrokClient()
        balance_info = client.get_api_balance()
        return jsonify({
            'success': True,
            'data': balance_info
        })
    except Exception as e:
        import traceback
        print(f"获取API余额失败: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 章节大纲管理 ==========

@app.route('/api/projects/<project_title>/generate-outline', methods=['POST'])
def generate_outline(project_title):
    """生成完整章节大纲（同步，可能需要2-3分钟）"""
    try:
        data = request.json
        total_chapters = data.get('total_chapters', 30)
        avg_length = data.get('avg_chapter_length', 3000)
        story_goal = data.get('story_goal', '')
        
        # 验证输入
        if total_chapters < 1 or total_chapters > 100:
            return jsonify({
                'success': False,
                'error': '章节数量必须在1-100之间'
            }), 400
        
        if avg_length < 1000 or avg_length > 10000:
            return jsonify({
                'success': False,
                'error': '章节字数必须在1000-10000之间'
            }), 400
        
        print(f"[大纲生成] 开始为项目 '{project_title}' 生成 {total_chapters} 章大纲")
        if story_goal:
            print(f"[大纲生成] 故事目标: {story_goal}")
        
        project = NovelProject.load(project_title)
        
        # ⚠️ 清空旧大纲（重新生成）
        if project.chapter_outlines:
            old_count = len(project.chapter_outlines)
            print(f"[大纲生成] 清空旧大纲（原有 {old_count} 章）")
            project.chapter_outlines = []
        
        # 保存故事目标到项目
        if story_goal:
            project.story_goal = story_goal
            project.save()
        
        client = GrokClient()
        
        # 记录开始时间
        import time
        start_time = time.time()
        
        outlines_data = client.generate_full_outline(project, total_chapters, avg_length, story_goal)
        
        # 保存大纲到项目
        from novel_ai.core.project import ChapterOutline
        for outline_data in outlines_data:
            outline = ChapterOutline(
                chapter_number=outline_data['chapter_number'],
                title=outline_data['title'],
                summary=outline_data['summary'],
                key_events=outline_data.get('key_events', []),
                involved_characters=outline_data.get('involved_characters', []),
                target_length=outline_data.get('target_length', avg_length),
                notes=outline_data.get('notes', '')
            )
            project.add_chapter_outline(outline)
        
        project.save()
        
        elapsed = time.time() - start_time
        print(f"[大纲生成] 完成！生成 {len(outlines_data)} 章，耗时 {elapsed:.1f} 秒")
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'成功生成{len(outlines_data)}章大纲',
                'outlines': [o.to_dict() for o in project.chapter_outlines],
                'elapsed_time': f'{elapsed:.1f}秒'
            }
        })
    except Exception as e:
        print(f"[大纲生成] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/regenerate-outline-with-feedback', methods=['POST'])
def regenerate_outline_with_feedback(project_title):
    """根据用户反馈重新生成完整大纲（仅在没有生成章节时可用）"""
    try:
        data = request.json
        user_feedback = data.get('user_feedback', '').strip()
        total_chapters = data.get('total_chapters')
        avg_length = data.get('avg_chapter_length', 3000)
        
        if not user_feedback:
            return jsonify({
                'success': False,
                'error': '请输入修改意见'
            }), 400
        
        project = NovelProject.load(project_title)
        
        # 检查是否有已生成的章节
        if project.chapters and len(project.chapters) > 0:
            return jsonify({
                'success': False,
                'error': '项目中已有生成的章节，无法重新生成大纲。如需修改大纲，请先删除所有章节。'
            }), 400
        
        # 检查是否有旧大纲
        if not project.chapter_outlines or len(project.chapter_outlines) == 0:
            return jsonify({
                'success': False,
                'error': '项目中没有大纲，请先生成初始大纲'
            }), 400
        
        # 保存旧大纲数据
        old_outlines = [o.to_dict() for o in project.chapter_outlines]
        old_chapter_count = len(old_outlines)
        
        # 如果没有指定章节数，使用旧大纲的章节数
        if not total_chapters:
            total_chapters = old_chapter_count
        
        print(f"[大纲重新生成] 项目 '{project_title}' - 根据用户反馈重新生成")
        print(f"[大纲重新生成] 用户意见：{user_feedback}")
        print(f"[大纲重新生成] 旧大纲：{old_chapter_count}章 -> 新大纲：{total_chapters}章")
        
        client = GrokClient()
        
        import time
        start_time = time.time()
        
        # 调用新方法：根据反馈重新生成
        outlines_data = client.regenerate_full_outline_with_feedback(
            project=project,
            user_feedback=user_feedback,
            old_outlines=old_outlines,
            total_chapters=total_chapters,
            avg_chapter_length=avg_length
        )
        
        if not outlines_data:
            return jsonify({
                'success': False,
                'error': '大纲生成失败，请重试'
            }), 500
        
        # 清空旧大纲
        project.chapter_outlines = []
        
        # 保存新大纲
        from novel_ai.core.project import ChapterOutline
        for outline_data in outlines_data:
            outline = ChapterOutline(
                chapter_number=outline_data['chapter_number'],
                title=outline_data['title'],
                summary=outline_data['summary'],
                key_events=outline_data.get('key_events', []),
                involved_characters=outline_data.get('involved_characters', []),
                target_length=outline_data.get('target_length', avg_length),
                notes=outline_data.get('notes', '')
            )
            project.add_chapter_outline(outline)
        
        project.save()
        
        elapsed = time.time() - start_time
        print(f"[大纲重新生成] 完成！生成 {len(outlines_data)} 章，耗时 {elapsed:.1f} 秒")
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'根据您的意见成功重新生成{len(outlines_data)}章大纲',
                'outlines': [o.to_dict() for o in project.chapter_outlines],
                'elapsed_time': f'{elapsed:.1f}秒'
            }
        })
        
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'项目不存在: {project_title}'
        }), 404
    except Exception as e:
        print(f"[大纲重新生成] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/outlines', methods=['GET', 'POST'])
def manage_outlines(project_title):
    """获取或更新章节大纲列表"""
    try:
        project = NovelProject.load(project_title)
        
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'data': {
                    'outlines': [o.to_dict() for o in project.chapter_outlines],
                    'total': len(project.chapter_outlines),
                    'generated': sum(1 for o in project.chapter_outlines if o.status in ['generated', 'completed']),
                    'planned': sum(1 for o in project.chapter_outlines if o.status == 'planned')
                }
            })
        
        elif request.method == 'POST':
            # 更新或添加大纲
            data = request.json
            action = data.get('action')  # 'add', 'update', 'delete'
            
            if action == 'add':
                from novel_ai.core.project import ChapterOutline
                outline = ChapterOutline(**data['outline'])
                project.add_chapter_outline(outline)
            elif action == 'update':
                chapter_number = data['chapter_number']
                # 提取更新字段
                updates = {
                    'title': data.get('title'),
                    'summary': data.get('summary'),
                    'key_events': data.get('key_events'),
                    'involved_characters': data.get('involved_characters'),
                    'target_length': data.get('target_length'),
                    'notes': data.get('notes')
                }
                # 移除None值
                updates = {k: v for k, v in updates.items() if v is not None}
                project.update_chapter_outline(chapter_number, **updates)
            elif action == 'delete':
                chapter_number = data['chapter_number']
                project.chapter_outlines = [
                    o for o in project.chapter_outlines 
                    if o.chapter_number != chapter_number
                ]
            
            project.save()
            
            return jsonify({
                'success': True,
                'data': {
                    'outlines': [o.to_dict() for o in project.chapter_outlines]
                }
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/generate-from-outline/<int:chapter_number>', methods=['POST'])
def generate_from_outline(project_title, chapter_number):
    """根据大纲生成章节"""
    try:
        data = request.json or {}
        enable_character_tracking = data.get('enable_character_tracking', False)
        
        project = NovelProject.load(project_title)
        outline = project.get_chapter_outline(chapter_number)
        
        if not outline:
            return jsonify({
                'success': False,
                'error': f'第{chapter_number}章的大纲不存在'
            }), 404
        
        # 异步生成（与普通生成章节相同的机制）
        generation_status[project_title] = {
            'status': 'generating',
            'progress': 0,
            'message': f'正在根据大纲生成第{chapter_number}章...',
            'chapter_number': chapter_number,
            'outline_based': True
        }
        
        import threading
        def generate_task():
            try:
                client = GrokClient()
                chapter = client.generate_chapter_from_outline(project, outline)
                
                # 添加章节
                project.add_chapter(chapter)
                
                # 检测新角色
                new_characters_detected = []
                try:
                    existing_char_names = [c.name for c in project.characters]
                    new_characters_detected = client.analyze_new_characters(chapter, existing_char_names)
                    if new_characters_detected:
                        print(f"🆕 发现 {len(new_characters_detected)} 个新角色: {[c['name'] for c in new_characters_detected]}")
                except Exception as e:
                    print(f"⚠ 新角色检测失败（不影响章节生成）: {e}")
                
                # 根据用户选择决定是否启用角色追踪
                if enable_character_tracking:
                    try:
                        if len(project.characters) > 0:
                            client.auto_update_character_tracker(project, chapter)
                            print(f"✓ 章节 {chapter.chapter_number} 的角色追踪已自动更新")
                    except Exception as e:
                        print(f"⚠ 角色追踪分析失败（不影响章节生成）: {e}")
                else:
                    print(f"ℹ️ 用户选择不启用角色追踪")
                
                # 更新大纲状态
                project.update_chapter_outline(chapter_number, status='generated')
                
                # 保存项目
                project.save()
                
                generation_status[project_title] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': '章节生成完成！',
                    'chapter': chapter.to_dict(),
                    'new_characters': new_characters_detected,
                    'chapter_number': chapter.chapter_number
                }
            except Exception as e:
                generation_status[project_title] = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'生成失败: {str(e)}'
                }
        
        thread = threading.Thread(target=generate_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'data': {
                'message': '开始根据大纲生成章节',
                'chapter_number': chapter_number
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/batch-generate-from-outline', methods=['POST'])
def batch_generate_from_outline(project_title):
    """批量根据大纲生成章节（一键顺序生成）"""
    try:
        data = request.json
        start_chapter = data.get('start_chapter', 1)
        end_chapter = data.get('end_chapter')
        enable_character_tracking = data.get('enable_character_tracking', False)
        
        project = NovelProject.load(project_title)
        
        # 获取所有大纲
        all_outlines = sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
        
        if not all_outlines:
            return jsonify({
                'success': False,
                'error': '没有可用的章节大纲'
            }), 400
        
        # 如果没有指定结束章节，则生成所有大纲章节
        if end_chapter is None:
            end_chapter = max(o.chapter_number for o in all_outlines)
        
        # 筛选需要生成的大纲（只生成尚未生成的）
        outlines_to_generate = [
            o for o in all_outlines 
            if start_chapter <= o.chapter_number <= end_chapter
            and not project.get_chapter(o.chapter_number)  # 只生成不存在的章节
        ]
        
        if not outlines_to_generate:
            return jsonify({
                'success': False,
                'error': f'第{start_chapter}-{end_chapter}章已经全部生成，无需重复生成'
            }), 400
        
        total_count = len(outlines_to_generate)
        tracking_status = "启用" if enable_character_tracking else "关闭"
        print(f"[批量生成] 开始批量生成 {total_count} 个章节（第{start_chapter}-{end_chapter}章），角色追踪：{tracking_status}")
        
        # 初始化批量生成状态
        batch_status_key = f"{project_title}_batch"
        all_chapter_numbers = [o.chapter_number for o in outlines_to_generate]
        
        generation_status[batch_status_key] = {
            'status': 'generating',
            'total': total_count,
            'completed': 0,
            'completed_chapters': [],  # 已完成的章节号列表
            'all_chapter_numbers': all_chapter_numbers,  # 所有待生成章节号
            'current_chapter': outlines_to_generate[0].chapter_number,
            'current_title': outlines_to_generate[0].title,
            'failed': [],
            'enable_character_tracking': enable_character_tracking,
            'message': f'开始批量生成第{start_chapter}-{end_chapter}章...',
            'start_time': datetime.now().isoformat()
        }
        
        # 持久化任务状态
        save_task_status(batch_status_key, generation_status[batch_status_key])
        
        # 启动后台批量生成任务
        thread = threading.Thread(
            target=batch_generate_background,
            args=(project_title, outlines_to_generate, batch_status_key, enable_character_tracking)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'开始批量生成 {total_count} 个章节',
                'total': total_count,
                'chapters': [o.chapter_number for o in outlines_to_generate]
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/batch-generate-progress', methods=['GET'])
def batch_generate_progress(project_title):
    """查询批量生成进度"""
    try:
        batch_status_key = f"{project_title}_batch"
        status = generation_status.get(batch_status_key, {
            'status': 'unknown',
            'total': 0,
            'completed': 0,
            'message': '无批量生成任务'
        })
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/batch-generate-cancel', methods=['POST'])
def batch_generate_cancel(project_title):
    """取消批量生成"""
    try:
        batch_status_key = f"{project_title}_batch"
        if batch_status_key in generation_status:
            generation_status[batch_status_key]['status'] = 'cancelled'
            generation_status[batch_status_key]['message'] = '用户取消了批量生成'
            print(f"[批量生成] 用户取消了批量生成任务")
        
        return jsonify({
            'success': True,
            'data': {'message': '已取消批量生成'}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def batch_generate_background(project_title, outlines_to_generate, batch_status_key, enable_character_tracking=False, is_recovery=False):
    """后台批量生成章节"""
    try:
        project = NovelProject.load(project_title)
        client = GrokClient()
        
        total = len(outlines_to_generate)
        
        # 如果是恢复任务，从已完成的数量继续
        if is_recovery:
            completed = len(generation_status[batch_status_key].get('completed_chapters', []))
            print(f"[批量生成-恢复] 从第{completed+1}章继续，剩余{total}章")
        else:
            completed = 0
        
        for i, outline in enumerate(outlines_to_generate):
            # 检查是否被取消
            if generation_status.get(batch_status_key, {}).get('status') == 'cancelled':
                print(f"[批量生成] 任务已取消，停止生成")
                break
            
            chapter_number = outline.chapter_number
            
            # 更新进度
            generation_status[batch_status_key].update({
                'status': 'generating',
                'completed': completed,
                'current_chapter': chapter_number,
                'current_title': outline.title,
                'message': f'正在生成第{chapter_number}章：{outline.title} ({completed+1}/{generation_status[batch_status_key]["total"]})'
            })
            
            # 持久化当前状态
            save_task_status(batch_status_key, generation_status[batch_status_key])
            
            print(f"[批量生成] 生成第{chapter_number}章：{outline.title} ({completed+1}/{generation_status[batch_status_key]['total']})")
            
            try:
                # 重新加载项目以获取最新的章节内容
                project = NovelProject.load(project_title)
                
                # 生成章节
                chapter = client.generate_chapter_from_outline(project, outline)
                
                # 添加章节
                project.add_chapter(chapter)
                
                # 检测新角色
                try:
                    existing_char_names = [c.name for c in project.characters]
                    new_characters_detected = client.analyze_new_characters(chapter, existing_char_names)
                    if new_characters_detected:
                        print(f"🆕 第{chapter_number}章发现 {len(new_characters_detected)} 个新角色")
                except Exception as e:
                    print(f"⚠ 新角色检测失败: {e}")
                
                # 根据用户选择决定是否启用角色追踪
                if enable_character_tracking:
                    try:
                        if len(project.characters) > 0:
                            client.auto_update_character_tracker(project, chapter)
                            print(f"✓ 第{chapter_number}章角色追踪已更新")
                    except Exception as e:
                        print(f"⚠ 角色追踪更新失败: {e}")
                else:
                    print(f"ℹ️ 第{chapter_number}章跳过角色追踪（用户选择关闭）")
                
                # 更新大纲状态
                project.update_chapter_outline(chapter_number, status='generated')
                
                # 保存项目
                project.save()
                
                completed += 1
                generation_status[batch_status_key]['completed_chapters'].append(chapter_number)
                print(f"✅ 第{chapter_number}章生成完成 ({completed}/{generation_status[batch_status_key]['total']})")
                
                # 持久化更新后的状态
                save_task_status(batch_status_key, generation_status[batch_status_key])
                
            except Exception as e:
                error_msg = f"第{chapter_number}章生成失败: {str(e)}"
                print(f"❌ {error_msg}")
                generation_status[batch_status_key]['failed'].append({
                    'chapter_number': chapter_number,
                    'title': outline.title,
                    'error': str(e)
                })
                # 持久化失败信息
                save_task_status(batch_status_key, generation_status[batch_status_key])
                # 继续生成下一章，不中断整个流程
                continue
        
        # 检查是否被取消
        if generation_status.get(batch_status_key, {}).get('status') == 'cancelled':
            generation_status[batch_status_key].update({
                'status': 'cancelled',
                'completed': completed,
                'message': f'批量生成已取消，已完成 {completed}/{generation_status[batch_status_key]["total"]} 章'
            })
            save_task_status(batch_status_key, generation_status[batch_status_key])
        else:
            # 全部完成
            failed_count = len(generation_status[batch_status_key].get('failed', []))
            if failed_count > 0:
                generation_status[batch_status_key].update({
                    'status': 'completed_with_errors',
                    'completed': completed,
                    'message': f'批量生成完成，但有 {failed_count} 章失败'
                })
                save_task_status(batch_status_key, generation_status[batch_status_key])
            else:
                generation_status[batch_status_key].update({
                    'status': 'completed',
                    'completed': completed,
                    'message': f'批量生成全部完成！共生成 {completed} 章'
                })
                save_task_status(batch_status_key, generation_status[batch_status_key])
                # 任务完成后可以删除持久化文件（可选）
                # delete_task_status(batch_status_key)
        
        print(f"[批量生成] 批量生成任务结束：成功 {completed}/{generation_status[batch_status_key]['total']} 章")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        generation_status[batch_status_key] = {
            'status': 'error',
            'message': f'批量生成失败: {str(e)}'
        }
        save_task_status(batch_status_key, generation_status[batch_status_key])


# ========== 启动服务器 ==========

def main():
    """启动Web服务器"""
    print("=" * 60)
    print("NovelGrok Web界面启动中...")
    print("=" * 60)
    
    # 恢复未完成的任务
    recover_pending_tasks()
    
    # 从环境变量读取配置
    host = os.getenv('WEB_HOST', '0.0.0.0')
    port = int(os.getenv('WEB_PORT', '5001'))
    debug = os.getenv('WEB_DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    print()
    print(f"访问地址: http://localhost:{port}")
    if host == '0.0.0.0':
        print(f"公网访问: http://<your-ip>:{port}")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()
    
    app.run(host=host, port=port, debug=debug)


@app.route('/api/projects/<project_title>/regenerate-outline-range', methods=['POST'])
def regenerate_outline_range(project_title):
    """重新生成指定范围的章节大纲"""
    try:
        data = request.json
        chapter_numbers = data.get('chapter_numbers', [])
        stage_goal = data.get('stage_goal', '')
        avg_length = data.get('avg_chapter_length', 3000)
        
        if not chapter_numbers:
            return jsonify({
                'success': False,
                'error': '请指定要重新生成的章节'
            }), 400
        
        print(f"[局部重生成] 开始为项目 '{project_title}' 重新生成第 {chapter_numbers} 章大纲")
        if stage_goal:
            print(f"[局部重生成] 阶段目标: {stage_goal}")
        
        project = NovelProject.load(project_title)
        client = GrokClient()
        
        import time
        start_time = time.time()
        
        # 调用AI生成指定范围的大纲
        outlines_data = client.regenerate_outline_range(
            project, chapter_numbers, avg_length, stage_goal
        )
        
        # 更新指定章节的大纲
        from novel_ai.core.project import ChapterOutline
        for outline_data in outlines_data:
            chapter_num = outline_data['chapter_number']
            # 删除旧大纲
            project.chapter_outlines = [
                o for o in project.chapter_outlines 
                if o.chapter_number != chapter_num
            ]
            # 添加新大纲
            outline = ChapterOutline(
                chapter_number=outline_data['chapter_number'],
                title=outline_data['title'],
                summary=outline_data['summary'],
                key_events=outline_data.get('key_events', []),
                involved_characters=outline_data.get('involved_characters', []),
                target_length=outline_data.get('target_length', avg_length),
                notes=outline_data.get('notes', '')
            )
            project.add_chapter_outline(outline)
        
        # 重新排序
        project.chapter_outlines.sort(key=lambda x: x.chapter_number)
        project.save()
        
        elapsed = time.time() - start_time
        print(f"[局部重生成] 完成！重新生成 {len(outlines_data)} 章，耗时 {elapsed:.1f} 秒")
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'成功重新生成{len(outlines_data)}章大纲',
                'outlines': [o.to_dict() for o in project.chapter_outlines],
                'elapsed_time': f'{elapsed:.1f}秒'
            }
        })
    except Exception as e:
        print(f"[局部重生成] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/append-outlines', methods=['POST'])
def append_outlines(project_title):
    """追加生成更多章节大纲"""
    try:
        data = request.json
        additional_chapters = data.get('additional_chapters', 10)
        new_goal = data.get('new_goal', '')
        avg_length = data.get('avg_chapter_length', 3000)
        
        if additional_chapters < 1 or additional_chapters > 50:
            return jsonify({
                'success': False,
                'error': '追加章节数必须在1-50之间'
            }), 400
        
        project = NovelProject.load(project_title)
        
        if not project.chapter_outlines:
            return jsonify({
                'success': False,
                'error': '请先生成初始大纲'
            }), 400
        
        current_count = len(project.chapter_outlines)
        print(f"[追加大纲] 开始为项目 '{project_title}' 追加 {additional_chapters} 章大纲")
        print(f"[追加大纲] 当前已有 {current_count} 章，将从第 {current_count + 1} 章开始")
        if new_goal:
            print(f"[追加大纲] 新目标: {new_goal}")
        
        client = GrokClient()
        
        import time
        start_time = time.time()
        
        # 调用AI追加生成大纲
        outlines_data = client.append_outlines(
            project, additional_chapters, avg_length, new_goal
        )
        
        # 添加新大纲
        from novel_ai.core.project import ChapterOutline
        for outline_data in outlines_data:
            outline = ChapterOutline(
                chapter_number=outline_data['chapter_number'],
                title=outline_data['title'],
                summary=outline_data['summary'],
                key_events=outline_data.get('key_events', []),
                involved_characters=outline_data.get('involved_characters', []),
                target_length=outline_data.get('target_length', avg_length),
                notes=outline_data.get('notes', '')
            )
            project.add_chapter_outline(outline)
        
        # 更新story_goal
        if new_goal:
            project.story_goal = new_goal
        
        project.save()
        
        elapsed = time.time() - start_time
        print(f"[追加大纲] 完成！追加 {len(outlines_data)} 章，总计 {len(project.chapter_outlines)} 章，耗时 {elapsed:.1f} 秒")
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'成功追加{len(outlines_data)}章大纲',
                'outlines': [o.to_dict() for o in project.chapter_outlines],
                'elapsed_time': f'{elapsed:.1f}秒'
            }
        })
    except Exception as e:
        print(f"[追加大纲] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 小说导入 ===

@app.route('/api/projects/<project_title>/import-novel', methods=['POST'])
def import_novel(project_title):
    """导入小说文本"""
    try:
        data = request.json
        novel_content = data.get('content', '')
        extract_characters = data.get('extract_characters', True)
        
        if not novel_content or not novel_content.strip():
            return jsonify({
                'success': False,
                'error': '小说内容不能为空'
            }), 400
        
        print(f"[导入小说] 开始导入小说到项目 '{project_title}'")
        print(f"[导入小说] 内容长度: {len(novel_content)} 字符")
        
        # 使用导入器处理小说
        from novel_ai.utils.novel_importer import NovelImporter
        importer = NovelImporter(max_file_size=None)  # 不限制大小
        
        success, chapters, error = importer.import_novel(novel_content)
        
        if not success:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        print(f"[导入小说] 成功切分 {len(chapters)} 个章节")
        
        # 加载或创建项目
        try:
            project = NovelProject.load(project_title)
            print(f"[导入小说] 加载现有项目")
        except FileNotFoundError:
            project = NovelProject(project_title)
            print(f"[导入小说] 创建新项目")
        
        # 将章节添加到项目
        from novel_ai.core.project import Chapter
        for imported_ch in chapters:
            chapter = Chapter(
                title=imported_ch.title,
                content=imported_ch.content,
                chapter_number=imported_ch.chapter_number,
                word_count=imported_ch.word_count,
                source="imported"  # 标记为导入章节
            )
            # 直接添加到章节列表，保持章节号
            project.chapters.append(chapter)
        
        # 后台异步处理：角色提取（必须）+ 角色追踪（可选）
        print(f"[导入小说] 开始后台处理...")
        
        def extract_chars_and_tracking_async():
            try:
                client = GrokClient()
                
                # 步骤1: 提取角色（总是执行）
                print(f"[导入小说] 步骤1: 提取角色信息（必须）...")
                chars = client.extract_characters_from_novel(novel_content)
                
                # 将提取的角色添加到项目
                from novel_ai.core.project import Character
                for char_data in chars:
                    character = Character(
                        name=char_data['name'],
                        description=char_data['description'],
                        personality=char_data['personality']
                    )
                    # 解析relationships字符串为字典（简单处理）
                    if char_data.get('relationships'):
                        # 暂时将关系存为一个通用描述
                        character.relationships = {'其他': char_data['relationships']}
                    
                    project.add_character(character)
                
                project.save()
                print(f"[导入小说] ✓ 成功提取并保存 {len(chars)} 个角色")
                
                # 步骤2: 逐章分析（根据用户选择）
                if extract_characters:
                    print(f"[导入小说] 步骤2: 逐章分析新角色和角色追踪（用户已选择）...")
                    for idx, chapter in enumerate(project.chapters):
                        if chapter.source == 'imported':
                            try:
                                print(f"[导入小说]   分析第{chapter.chapter_number}章: {chapter.title}...")
                                
                                # 2.1 检测新角色
                                existing_char_names = [char.name for char in project.characters]
                                new_chars = client.analyze_new_characters(chapter, existing_char_names)
                                
                                if new_chars:
                                    print(f"[导入小说]     发现 {len(new_chars)} 个新角色: {[c['name'] for c in new_chars]}")
                                    from novel_ai.core.project import Character
                                    for char_data in new_chars:
                                        character = Character(
                                            name=char_data['name'],
                                            description=char_data['description'],
                                            personality=char_data.get('personality', '')
                                        )
                                        project.add_character(character)
                                    project.save()
                                
                                # 2.2 更新角色追踪
                                client.auto_update_character_tracker(project, chapter)
                                project.save()
                                
                            except Exception as e:
                                print(f"[导入小说]   ⚠️ 第{chapter.chapter_number}章分析失败: {e}")
                    
                    print(f"[导入小说] ✓ 新角色检测和角色追踪分析完成！")
                else:
                    print(f"[导入小说] 步骤2: 跳过角色追踪分析（用户未选择）")
                
                print(f"[导入小说] 最终角色数: {len(project.characters)}")
                
            except Exception as e:
                print(f"[导入小说] 后台处理失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 启动后台线程
        import threading
        thread = threading.Thread(target=extract_chars_and_tracking_async)
        thread.daemon = True
        thread.start()
        
        # 保存项目
        project.save()
        
        # 获取导入摘要
        summary = importer.get_import_summary(chapters)
        
        print(f"[导入小说] 导入完成！{summary['chapter_count']}章，共{summary['total_words']}字")
        
        return jsonify({
            'success': True,
            'data': {
                'message': f'成功导入小说，共{len(chapters)}章',
                'summary': summary,
                'chapters': [
                    {
                        'chapter_number': ch.chapter_number,
                        'title': ch.title,
                        'word_count': ch.word_count
                    }
                    for ch in chapters[:20]  # 只返回前20章的信息
                ],
                'character_extraction_started': extract_characters
            }
        })
        
    except Exception as e:
        print(f"[导入小说] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/projects/<project_title>/import-status', methods=['GET'])
def get_import_status(project_title):
    """获取导入状态（主要是角色提取进度）"""
    try:
        project = NovelProject.load(project_title)
        
        return jsonify({
            'success': True,
            'data': {
                'chapter_count': len(project.chapters),
                'character_count': len(project.characters),
                'total_words': project.get_total_word_count(),
                'characters': [
                    {
                        'name': char.name,
                        'description': char.description[:50] + '...' if len(char.description) > 50 else char.description
                    }
                    for char in project.characters
                ]
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    main()
