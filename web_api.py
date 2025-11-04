#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelGrok Web API
提供RESTful API接口供前端调用
"""

import os
import traceback
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from novel_ai.core.project import NovelProject, Character, Chapter
from novel_ai.core.context_manager import ContextManager
from novel_ai.api.grok_client import GrokClient
from novel_ai.utils.text_utils import format_word_count

# 加载环境变量
load_dotenv()

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量
context_manager = ContextManager(max_tokens=20000)

# 章节生成状态管理
generation_status = {
    # 格式: 'project_title': {'status': 'generating', 'progress': 50, 'message': '正在生成...'}
}


# ========== 页面路由 ==========

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/reader')
def reader():
    """小说阅读器页面"""
    return render_template('reader.html')


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
                'characters': [char.to_dict() for char in project.characters],
                'chapters': [chap.to_dict() for chap in project.chapters],
                'plot_points': project.plot_points,
                'status': status,
                'context_analysis': analysis,
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
    """分析章节并自动更新角色追踪"""
    try:
        project = NovelProject.load(project_title)
        chapter = project.get_chapter(chapter_number)
        
        if not chapter:
            return jsonify({'success': False, 'error': f'章节不存在: {chapter_number}'}), 404
        
        if not os.getenv('XAI_API_KEY'):
            return jsonify({'success': False, 'error': 'API密钥未配置'}), 400
        
        client = GrokClient()
        client.auto_update_character_tracker(project, chapter)
        
        project.save()
        
        return jsonify({
            'success': True,
            'message': '章节分析完成，角色追踪已更新'
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
                
                # 自动分析并更新角色追踪
                try:
                    if len(project.characters) > 0:
                        client.auto_update_character_tracker(project, chapter)
                        print(f"✓ 章节 {chapter.chapter_number} 的角色追踪已自动更新")
                except Exception as e:
                    print(f"⚠ 角色追踪分析失败（不影响章节生成）: {e}")
                
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


# ========== 启动服务器 ==========

def main():
    """启动Web服务器"""
    print("=" * 60)
    print("NovelGrok Web界面启动中...")
    print("=" * 60)
    print()
    print("访问地址: http://localhost:5001")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()
    
    app.run(host='0.0.0.0', port=5001, debug=True)


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


if __name__ == '__main__':
    main()
