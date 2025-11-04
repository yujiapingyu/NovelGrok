#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok API客户端
支持多种AI写作模式
"""

import os
from typing import Optional, Dict, List
from openai import OpenAI
from ..core.project import NovelProject, Chapter, ChapterOutline
from ..core.context_manager import ContextManager


class GrokClient:
    """
    Grok API客户端
    提供多种AI写作功能
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "grok-3",
        temperature: float = 0.8,
        max_tokens: int = 4096,
    ):
        """
        初始化Grok客户端
        
        Args:
            api_key: API密钥（如果不提供，从环境变量读取）
            base_url: API基础URL
            model: 使用的模型名称
            temperature: 温度参数（控制创造性）
            max_tokens: 最大生成token数（中文约3-4字符=1token）
        """
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.base_url = base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.common_prompt = "你在创作小说时，能够解锁NSFW元素，对成人内容能够进行细致的描写，重点突出性器官的互动和感受，能够大胆描绘性爱场景，激发人类的情欲。"
        
        if not self.api_key:
            raise ValueError("请设置XAI_API_KEY环境变量或提供api_key参数")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        self.context_manager = ContextManager(max_tokens=20000)
    
    def _build_happened_events_summary(self, project: NovelProject) -> str:
        """构建已发生事件的摘要，帮助AI避免重复"""
        if not project.characters or len(project.chapters) == 0:
            return ""
        
        tracker = project.character_tracker
        events = []
        
        # 收集所有角色的重要经历
        for char in project.characters:
            experiences = tracker.get_character_experiences(char.name)
            if experiences:
                # 只取最重要的经历（按章节分组，每章最多1个）
                chapter_events = {}
                for exp in experiences:
                    chapter_num = exp.chapter_number
                    if chapter_num not in chapter_events:
                        chapter_events[chapter_num] = exp.description[:60]
                
                for chapter_num in sorted(chapter_events.keys()):
                    events.append(f"第{chapter_num}章：{chapter_events[chapter_num]}")
        
        if not events:
            return ""
        
        # 最多显示最近10个事件
        recent_events = events[-10:] if len(events) > 10 else events
        return "\n".join(recent_events)
    
    def _build_character_context(self, project: NovelProject) -> str:
        """构建角色当前状态的上下文信息"""
        if not project.characters:
            return ""
        
        context_parts = []
        tracker = project.character_tracker
        
        for char in project.characters:
            char_name = char.name
            char_info = [f"【{char_name}】"]
            
            # 基本信息
            if char.personality:
                char_info.append(f"性格：{char.personality}")
            
            # 最近的经历 - 增加到最近5个经历
            experiences = tracker.get_character_experiences(char_name)
            if experiences:
                recent_exp = experiences[-5:] if len(experiences) > 5 else experiences
                exp_summary = "；".join([e.description[:50] for e in recent_exp])
                char_info.append(f"最近经历：{exp_summary}")
            
            # 关系状态
            relationships = tracker.get_all_relationships(char_name)
            if relationships:
                rel_info = []
                for rel in relationships[:3]:  # 最多3个
                    rel_info.append(f"{rel.target_character}({rel.relationship_type},亲密度{rel.intimacy_level})")
                char_info.append(f"关系：" + "，".join(rel_info))
            
            # 性格特质
            traits = tracker.get_personality_traits(char_name)
            if traits:
                trait_info = [f"{t.trait_name}({t.intensity})" for t in traits[:3]]
                char_info.append(f"特质：" + "，".join(trait_info))
            
            context_parts.append("\n".join(char_info))
        
        return "\n\n".join(context_parts)
    
    def _make_request(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送API请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
        
        Returns:
            生成的文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"API请求失败: {str(e)}")
    
    # === 核心写作功能 ===
    
    def generate_new_chapter(
        self,
        project: NovelProject,
        chapter_title: str = "",
        writing_prompt: str = "",
        target_length: int = 3500,
    ) -> Chapter:
        """
        生成新章节
        
        Args:
            project: 小说项目
            chapter_title: 章节标题（如果为空，AI会生成）
            writing_prompt: 写作提示/要求
            target_length: 目标字数
        
        Returns:
            新生成的章节对象
        """
        # 构建上下文 - 增加历史章节数量，提供更完整的故事脉络
        context = self.context_manager.build_writing_context(
            project,
            include_full_recent=3,  # 增加到3章完整内容
            include_summary_count=10  # 增加到10章摘要
        )
        
        # 获取角色追踪信息用于增强连贯性
        character_context = self._build_character_context(project)
        latest_chapter = project.get_latest_chapter()
        
        # 构建"已发生事件"摘要，避免重复
        happened_events = self._build_happened_events_summary(project)
        
        # 构建写作提示
        system_prompt = "你是一位富有创意的小说作家，擅长创作引人入胜、情节连贯的故事内容。" + self.common_prompt
        
        user_prompt_parts = [context]
        
        # 添加已发生事件摘要
        if happened_events:
            user_prompt_parts.append(f"\n【已发生的关键事件（不要重复）】\n{happened_events}")
        
        # 添加角色当前状态信息
        if character_context:
            user_prompt_parts.append(f"\n【角色当前状态】\n{character_context}")
        
        # 添加上一章节的结尾分析，确保连贯性
        if latest_chapter and latest_chapter.content:
            # 获取更多的结尾内容，确保上下文充足
            paragraphs = latest_chapter.content.split('\n')
            # 取最后5段或最后500字，哪个更多
            last_paragraphs = '\n'.join(paragraphs[-5:])
            if len(last_paragraphs) < 500 and len(latest_chapter.content) > 500:
                last_paragraphs = latest_chapter.content[-500:]
            
            user_prompt_parts.append(f"\n【上章结尾（第{latest_chapter.chapter_number}章：{latest_chapter.title}）】")
            user_prompt_parts.append(last_paragraphs)
            user_prompt_parts.append(f"\n⚠️ 重要连贯性要求：")
            user_prompt_parts.append(f"1. 新章节必须从上述结尾的场景、时间、情绪自然延续")
            user_prompt_parts.append(f"2. 不要重复上一章已经发生的事情")
            user_prompt_parts.append(f"3. 角色的心理状态应该基于上一章结尾时的状态")
            user_prompt_parts.append(f"4. 如果上一章有悬念或伏笔，本章应该有所呼应或推进")
        
        if chapter_title:
            user_prompt_parts.append(f"\n【新章节标题】\n{chapter_title}")
        else:
            user_prompt_parts.append(f"\n【任务】\n请为这个故事创作下一章，并为这章起一个合适的标题。")
        
        if writing_prompt:
            user_prompt_parts.append(f"\n【写作要求】\n{writing_prompt}")
        
        user_prompt_parts.append(f"\n【写作指引】")
        user_prompt_parts.append(f"✅ 目标字数：约{target_length}字")
        user_prompt_parts.append(f"✅ 情节连贯：确保与上一章自然衔接，避免突兀跳跃")
        user_prompt_parts.append(f"✅ 角色一致：严格遵循角色性格、关系、当前状态")
        user_prompt_parts.append(f"✅ 场景连续：注意时间、地点的合理过渡")
        user_prompt_parts.append(f"✅ 情绪延续：延续前章的情感基调和氛围")
        user_prompt_parts.append(f"✅ 细节呼应：适当呼应之前的伏笔和细节")
        user_prompt_parts.append(f"✅ 生动描写：使用细腻的描写和自然的对话")
        user_prompt_parts.append(f"✅ 节奏把控：情节要有起伏和张力，避免平铺直叙")
        
        user_prompt_parts.append(f"\n【重要约束】")
        user_prompt_parts.append(f"❌ 不要重复之前章节的情节内容")
        user_prompt_parts.append(f"❌ 不要让时间线混乱（注意时间顺序）")
        user_prompt_parts.append(f"❌ 不要突然改变角色性格或关系")
        user_prompt_parts.append(f"❌ 不要引入与主线无关的新情节")
        user_prompt_parts.append(f"❌ 不要让场景转换过于突兀")
        
        # 如果有多个章节，添加情节递进要求
        if len(project.chapters) > 0:
            user_prompt_parts.append(f"\n【情节发展要求】")
            user_prompt_parts.append(f"📈 本章是第{len(project.chapters) + 1}章，情节必须在上一章基础上有所推进")
            user_prompt_parts.append(f"📈 角色关系、心理状态应该有微妙的变化")
            user_prompt_parts.append(f"📈 故事节奏要循序渐进，不要原地踏步")
            user_prompt_parts.append(f"📈 每一章都要为总体故事发展服务")
        
        if not chapter_title:
            user_prompt_parts.append(f"\n请按以下格式输出：")
            user_prompt_parts.append(f"标题：[章节标题]")
            user_prompt_parts.append(f"\n[正文内容]")
        else:
            user_prompt_parts.append(f"\n请直接输出正文内容。")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        # 调用API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 中文字数转token计算
        # 中文：约2-2.5个字符=1token
        # 给AI足够的自由度，不要限制太死
        estimated_tokens = int(target_length / 2 * 2)  # 给2倍的空间
        
        # 设置最小值
        if estimated_tokens < 2000:
            estimated_tokens = 2000
        
        # Grok-3 支持最大 131072 tokens 输出，设置一个很高的上限
        # 基本上不会触及这个限制
        max_tokens_for_request = min(estimated_tokens, 100000)
        
        response_text = self._make_request(messages, max_tokens=max_tokens_for_request)
        
        # 解析响应
        if not chapter_title:
            # 尝试从响应中提取标题
            lines = response_text.split('\n')
            if lines[0].startswith('标题：') or lines[0].startswith('# '):
                chapter_title = lines[0].replace('标题：', '').replace('# ', '').strip()
                content = '\n'.join(lines[1:]).strip()
            else:
                chapter_title = f"第{len(project.chapters) + 1}章"
                content = response_text.strip()
        else:
            content = response_text.strip()
        
        # 创建章节对象
        chapter = Chapter(
            title=chapter_title,
            content=content,
            chapter_number=len(project.chapters) + 1
        )
        
        return chapter
    
    def improve_chapter(
        self,
        chapter: Chapter,
        project: NovelProject,
        improvement_focus: str = "整体改进",
    ) -> str:
        """
        改进章节内容
        
        Args:
            chapter: 要改进的章节
            project: 小说项目
            improvement_focus: 改进重点
        
        Returns:
            改进后的内容
        """
        context = self.context_manager.build_improvement_context(
            chapter,
            project,
            improvement_focus
        )
        
        system_prompt = "你是一位专业的小说编辑，擅长改进和润色文学作品。" + self.common_prompt
        
        user_prompt = f"{context}\n\n【任务】\n请改进上述章节内容，重点关注：{improvement_focus}\n\n直接输出改进后的完整内容。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        improved_content = self._make_request(messages, max_tokens=20000)
        
        return improved_content.strip()
    
    # === 辅助功能 ===
    
    def generate_chapter_summary(
        self,
        chapter: Chapter,
        project: NovelProject,
        max_length: int = 200,
    ) -> str:
        """
        为章节生成AI摘要
        
        Args:
            chapter: 章节对象
            project: 小说项目
            max_length: 摘要最大长度
        
        Returns:
            章节摘要
        """
        system_prompt = "你是一位文学编辑，擅长提炼故事的核心情节。" + self.common_prompt
        
        user_prompt = f"""请为以下章节生成一个简洁的摘要（约{max_length}字以内）：

小说：{project.title}
章节：{chapter.title}

内容：
{chapter.content}

摘要要求：
- 概括本章的主要情节
- 提及重要的角色和事件
- 简洁明了，便于回顾

请直接输出摘要内容。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        summary = self._make_request(messages, max_tokens=3500, temperature=0.5)
        
        return summary.strip()
    
    def suggest_plot_development(self, project: NovelProject, count: int = 3) -> List[str]:
        """
        为项目提供情节发展建议
        
        Args:
            project: 小说项目
            count: 建议数量
        
        Returns:
            情节建议列表
        """
        context = self.context_manager.build_writing_context(project)
        
        system_prompt = "你是一位经验丰富的小说策划，擅长构思引人入胜的情节发展。" + self.common_prompt
        
        user_prompt = f"""{context}

【任务】
基于目前的故事发展，请提供{count}个可能的情节发展方向。每个建议应该：
- 符合现有的角色设定和世界观
- 有一定的戏剧性和吸引力
- 能推动故事向前发展

请按以下格式输出：
1. [建议1]
2. [建议2]
3. [建议3]"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages, temperature=0.9)
        
        # 解析建议
        suggestions = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                # 移除序号
                suggestion = line.lstrip('0123456789.-•) ').strip()
                if suggestion:
                    suggestions.append(suggestion)
        
        return suggestions[:count]
    
    def generate_chapter_idea(self, project: NovelProject) -> Dict[str, str]:
        """
        为下一章生成创意（标题和写作提示）
        
        Args:
            project: 小说项目
        
        Returns:
            包含 title 和 prompt 的字典
        """
        context = self.context_manager.build_writing_context(project)
        
        system_prompt = "你是一位经验丰富的小说策划，擅长构思引人入胜的章节创意。" + self.common_prompt
        
        next_chapter_num = len(project.chapters) + 1
        
        user_prompt = f"""{context}

【任务】
基于当前故事进展，为第{next_chapter_num}章生成一个引人入胜的创意。

请按以下JSON格式输出（不要添加任何额外说明）：
```json
{{
  "title": "章节标题（简短有力，3-8个字）",
  "prompt": "写作提示（50-150字，包含：情节要点、场景设置、情感基调、角色互动等关键要素）"
}}
```

要求：
1. 标题要吸引人，体现章节核心冲突或转折
2. 写作提示要具体明确，便于AI创作时把握方向
3. 确保与之前章节连贯，推动故事发展
4. 符合{project.genre if project.genre else '小说'}类型的特点"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages, temperature=0.8)
        
        # 提取JSON
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            idea = json.loads(response)
            return {
                "title": idea.get("title", "").strip(),
                "prompt": idea.get("prompt", "").strip()
            }
        except Exception as e:
            print(f"解析章节创意失败: {e}")
            print(f"原始响应: {response[:500]}")
            # 返回默认值
            return {
                "title": f"第{next_chapter_num}章",
                "prompt": "继续推进故事发展，展现角色成长和关系变化。"
            }
    
    def generate_character_dialogue(
        self,
        project: NovelProject,
        character_name: str,
        situation: str,
        other_character: str = "",
    ) -> str:
        """
        为特定角色生成对话
        
        Args:
            project: 小说项目
            character_name: 角色名称
            situation: 对话情境
            other_character: 对话对象（可选）
        
        Returns:
            生成的对话内容
        """
        character = project.get_character(character_name)
        if not character:
            raise ValueError(f"角色 {character_name} 不存在")
        
        system_prompt = f"你正在为小说《{project.title}》创作对话，请根据角色性格特点生成符合其个性的对话。" + self.common_prompt
        
        user_prompt_parts = [
            f"【角色信息】",
            character.get_full_description(),
        ]
        
        if other_character:
            other_char = project.get_character(other_character)
            if other_char:
                user_prompt_parts.append(f"\n【对话对象】")
                user_prompt_parts.append(other_char.get_full_description())
        
        user_prompt_parts.append(f"\n【情境】\n{situation}")
        user_prompt_parts.append(f"\n请为{character_name}生成符合其性格的对话（包括适当的动作和心理描写）。")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        dialogue = self._make_request(messages)
        
        return dialogue.strip()
    
    def expand_scene(
        self,
        project: NovelProject,
        scene_description: str,
        target_length: int = 500,
    ) -> str:
        """
        扩展场景描写
        
        Args:
            project: 小说项目
            scene_description: 场景简述
            target_length: 目标字数
        
        Returns:
            扩展后的场景描写
        """
        system_prompt = "你是一位擅长场景描写的小说家，能够通过生动的细节营造氛围。" + self.common_prompt
        
        user_prompt = f"""小说：{project.title}
类型：{project.genre if project.genre else '未指定'}

【场景简述】
{scene_description}

【任务】
请将上述场景扩展为约{target_length}字的详细描写，包括：
- 视觉细节（景物、色彩、光影等）
- 其他感官体验（声音、气味、触感等）
- 氛围营造
- 符合{project.genre if project.genre else '小说'}类型的风格

直接输出扩展后的场景描写。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        expanded_scene = self._make_request(messages, max_tokens=target_length)
        
        return expanded_scene.strip()
    
    # ========== 角色动态分析 ==========
    
    def analyze_chapter_for_character_events(
        self,
        project: NovelProject,
        chapter: Chapter
    ) -> Dict:
        """
        分析章节内容，提取角色相关事件
        
        Args:
            project: 小说项目
            chapter: 章节对象
        
        Returns:
            包含经历、关系变化、性格变化的字典
        """
        system_prompt = "你是一位敏锐的文学分析师，擅长从小说章节中提取角色发展相关信息。" + self.common_prompt
        
        character_names = [char.name for char in project.characters]
        
        # 获取角色当前状态，帮助更准确的分析
        character_context = []
        tracker = project.character_tracker
        for char_name in character_names:
            traits = tracker.get_personality_traits(char_name)
            rels = tracker.get_all_relationships(char_name)
            context = f"{char_name}（"
            if traits:
                context += "特质:" + ",".join([f"{t.trait_name}({t.intensity})" for t in traits[:2]]) + "；"
            if rels:
                context += "关系:" + ",".join([f"{r.target_character}({r.intimacy_level})" for r in rels[:2]])
            context += "）"
            character_context.append(context)
        
        user_prompt = f"""请深度分析以下章节内容，精确提取角色发展的细节信息。

【小说】：{project.title}（类型：{project.genre or '未知'}）
【章节】：第{chapter.chapter_number}章 - {chapter.title}
【字数】：{chapter.word_count}字

【已知角色及当前状态】
{chr(10).join(character_context)}

【章节内容】（已截取核心部分）
{chapter.content[:3000]}...

【深度分析要求】
请仔细阅读章节内容，从以下维度分析每个角色：

1. 📝 **重要经历**：本章中角色的关键事件、行为、决策
   - 成就(achievement)：获得的成功、完成的目标
   - 冲突(conflict)：遭遇的矛盾、困难、挑战  
   - 关系(relationship)：与他人的互动、交流
   - 成长(growth)：认知、能力的提升
   - 创伤(trauma)：负面打击、心理伤害

2. 🤝 **关系变化**：角色间关系的细微变化
   - 注意对话、肢体接触、情感表达
   - 亲密度变化范围：-20到+20（需要显著变化才记录）
   - 关系类型要准确：friend/enemy/family/lover/mentor/rival/neutral
   - 记录关系的具体描述（如："同事关系，李明是魏铁的上司"）

3. 🧠 **性格演变**：性格特质强度的变化
   - 从行为、语言、心理活动推断
   - 特质如：勇敢、自信、开放性、支配性、温柔、果断等
   - 强度变化范围：-20到+20（需要明显变化才记录）

【输出格式】
严格按照以下JSON格式输出，不要添加任何注释或说明文字：

```json
{{
  "experiences": [
    {{
      "character": "角色名（必须是已知角色之一）",
      "event_type": "achievement或conflict或relationship或growth或trauma",
      "description": "事件的具体描述，包含关键细节（30-80字）",
      "impact": "positive或negative或neutral",
      "related_characters": ["相关角色1", "相关角色2"]
    }}
  ],
  "relationships": [
    {{
      "character": "角色A（必须是已知角色）",
      "target": "角色B（必须是已知角色）",
      "type": "friend或enemy或family或lover或mentor或rival或neutral",
      "intimacy_change": 5,
      "description": "关系的具体描述，如'同事关系，经常一起工作'（15-40字）",
      "reason": "导致关系变化的具体原因（20-50字）"
    }}
  ],
  "personality_changes": [
    {{
      "character": "角色名（必须是已知角色）",
      "trait": "性格特质名称（如：勇敢、自信、开放性等）",
      "intensity_change": 5,
      "reason": "导致性格变化的具体原因（20-50字）"
    }}
  ]
}}
```

⚠️ 关键要求：
1. 只分析已知角色：{', '.join(character_names)}
2. 每个类别至少提取2-3条信息（如果章节中有的话）
3. intimacy_change和intensity_change：-20到+20之间的整数
4. description和reason要具体详细，不要笼统概括
5. 如果某类别确实无内容，才返回空数组[]
6. JSON必须完全符合格式，不要有任何额外字符
7. 特别注意章节中的对话、心理描写、行为细节
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3, max_tokens=3500)
            
            # 尝试提取JSON（可能被包裹在markdown代码块中）
            original_response = response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            analysis = json.loads(response)
            return analysis
            
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            print(f"📄 AI原始响应（前500字符）:")
            print(f"{original_response[:500] if 'original_response' in locals() else response[:500]}")
            print(f"...")
            return {
                "experiences": [],
                "relationships": [],
                "personality_changes": []
            }
    
    def auto_update_character_tracker(
        self,
        project: NovelProject,
        chapter: Chapter
    ):
        """
        自动分析章节并更新角色追踪器
        
        Args:
            project: 小说项目
            chapter: 章节对象
        """
        print(f"\n📊 开始分析章节 {chapter.chapter_number}：{chapter.title}")
        print(f"   角色数量: {len(project.characters)}")
        print(f"   章节字数: {chapter.word_count}")
        
        analysis = self.analyze_chapter_for_character_events(project, chapter)
        tracker = project.character_tracker
        
        # 统计
        exp_count = len(analysis.get("experiences", []))
        rel_count = len(analysis.get("relationships", []))
        per_count = len(analysis.get("personality_changes", []))
        
        print(f"\n✨ AI分析结果:")
        print(f"   - 发现 {exp_count} 个角色经历")
        print(f"   - 发现 {rel_count} 个关系变化")
        print(f"   - 发现 {per_count} 个性格变化")
        
        # 添加经历
        for exp in analysis.get("experiences", []):
            print(f"   📝 {exp['character']}: {exp['description'][:30]}...")
            tracker.add_experience(
                character_name=exp["character"],
                chapter_number=chapter.chapter_number,
                event_type=exp["event_type"],
                description=exp["description"],
                impact=exp["impact"],
                related_characters=exp.get("related_characters", [])
            )
        
        # 更新关系
        for rel in analysis.get("relationships", []):
            print(f"   🤝 {rel['character']} ↔ {rel['target']}: {rel.get('type', 'unknown')}")
            # 确保关系存在
            existing_rel = tracker.get_relationship(rel["character"], rel["target"])
            if not existing_rel:
                tracker.add_relationship(
                    character_name=rel["character"],
                    target_character=rel["target"],
                    relationship_type=rel["type"],
                    description=rel.get("description", ""),
                    first_met_chapter=chapter.chapter_number
                )
            
            tracker.update_relationship(
                character_name=rel["character"],
                target_character=rel["target"],
                new_type=rel.get("type"),
                intimacy_change=rel.get("intimacy_change", 0),
                description=rel.get("description", ""),
                reason=rel.get("reason", ""),
                chapter=chapter.chapter_number
            )
        
        # 更新性格
        for pc in analysis.get("personality_changes", []):
            print(f"   🧠 {pc['character']}: {pc['trait']} {pc.get('intensity_change', 0):+d}")
            # 确保性格特质存在
            traits = tracker.get_personality_traits(pc["character"])
            trait_exists = any(t.trait_name == pc["trait"] for t in traits)
            
            if not trait_exists:
                # 创建新特质（初始强度50）
                tracker.set_personality_traits(pc["character"], [
                    *[t.to_dict() for t in traits],
                    {"trait_name": pc["trait"], "intensity": 50, "description": ""}
                ])
            
            # 更新特质
            current_trait = next((t for t in tracker.get_personality_traits(pc["character"]) 
                                 if t.trait_name == pc["trait"]), None)
            if current_trait:
                new_intensity = current_trait.intensity + pc.get("intensity_change", 0)
                tracker.update_personality_trait(
                    character_name=pc["character"],
                    trait_name=pc["trait"],
                    new_intensity=new_intensity,
                    reason=pc.get("reason", ""),
                    chapter_number=chapter.chapter_number
                )
        
        print(f"\n✅ 角色追踪更新完成！\n")
    
    def analyze_new_characters(
        self,
        chapter: Chapter,
        existing_characters: List[str]
    ) -> List[Dict[str, str]]:
        """
        分析章节中是否出现新的重要角色
        
        Args:
            chapter: 要分析的章节
            existing_characters: 已存在的角色名列表
        
        Returns:
            新角色列表，每个包含: name, description, personality
        """
        # 如果章节太短，不分析
        if len(chapter.content) < 200:
            return []
        
        system_prompt = "你是一位资深的小说编辑，擅长识别故事中的重要角色。"
        
        existing_chars_text = "、".join(existing_characters) if existing_characters else "无"
        
        user_prompt = f"""请分析以下章节内容，识别是否有新的**重要角色**出现。

【已知角色】：{existing_chars_text}

【章节内容】：
{chapter.content[:3000]}

【分析要求】：
1. 只识别**有名字且重要的新角色**（不要识别路人甲乙、服务员等次要角色）
2. 新角色应该：
   - 有明确的名字
   - 在情节中有重要作用
   - 有一定的描写或对话
   - 可能会在后续章节中再次出现

3. 对于每个新角色，提取：
   - name: 角色名字
   - description: 角色的外貌、身份、特点（30-80字）
   - personality: 性格特点（20-50字）

4. 如果没有发现重要的新角色，返回空数组

【输出格式】（必须是有效的JSON）：
```json
[
  {{
    "name": "角色名字",
    "description": "角色描述（外貌、身份、特点）",
    "personality": "性格特点"
  }}
]
```

⚠️ 注意：
- 只返回JSON数组，不要其他内容
- 如果没有新角色，返回 []
- 不要识别已知角色：{existing_chars_text}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3, max_tokens=1000)
            
            # 提取JSON - 更强大的提取逻辑
            import re
            import json
            
            # 首先尝试提取 ```json ... ``` 代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 尝试提取 ``` ... ``` 代码块
                json_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # 直接使用响应内容
                    json_str = response.strip()
            
            # 移除可能的多余文本（只保留JSON数组部分）
            # 查找第一个 [ 到最后一个 ]
            start_idx = json_str.find('[')
            end_idx = json_str.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = json_str[start_idx:end_idx + 1]
            
            # 解析JSON
            new_characters = json.loads(json_str)
            
            # 确保返回的是列表
            if not isinstance(new_characters, list):
                print(f"⚠️ 返回的不是列表: {type(new_characters)}")
                return []
            
            # 过滤掉已存在的角色
            filtered = []
            for char in new_characters:
                if isinstance(char, dict) and char.get("name") and char["name"] not in existing_characters:
                    filtered.append(char)
            
            return filtered
            
        except json.JSONDecodeError as e:
            print(f"⚠️ 新角色分析失败 (JSON解析错误): {e}")
            print(f"   响应内容: {response[:200]}...")
            return []
        except Exception as e:
            print(f"⚠️ 新角色分析失败: {e}")
            return []
    
    def get_api_balance(self) -> Dict:
        """
        获取API余额信息
        
        Returns:
            包含余额信息的字典
        """
        try:
            # x.ai API 不提供标准的余额查询接口
            # 返回基本配置信息
            return {
                "available": True,
                "message": "API 已配置",
                "model": self.model,
                "base_url": self.base_url,
                "api_key": self.api_key[:10] + "..." if self.api_key else "未配置"
            }
            
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "message": "API 配置错误"
            }
    
    def generate_full_outline(
        self,
        project: NovelProject,
        total_chapters: int = 30,
        avg_chapter_length: int = 3000,
        story_goal: str = ""
    ) -> List[Dict]:
        """
        生成完整的章节大纲
        
        Args:
            project: 小说项目
            total_chapters: 总章节数
            avg_chapter_length: 平均章节字数
            story_goal: 故事目标/最终状态（可选）
        
        Returns:
            章节大纲列表
        """
        system_prompt = "你是一位资深小说编剧，擅长构建完整连贯的故事框架和章节大纲。" + self.common_prompt
        
        character_info = "\n".join([
            f"- {char.name}: {char.description}" 
            for char in project.characters
        ])
        
        # 构建故事目标部分
        goal_section = ""
        if story_goal:
            goal_section = f"\n故事目标：{story_goal}"
        elif project.story_goal:
            goal_section = f"\n故事目标：{project.story_goal}"
        
        user_prompt = f"""请为以下小说构建完整的章节大纲。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
背景设定：{project.background or '未指定'}
总体大纲：{project.plot_outline or '未指定'}
写作风格：{project.writing_style or '未指定'}{goal_section}

【主要角色】
{character_info if character_info else '暂无角色'}

【大纲要求】
1. 总章节数：{total_chapters}章
2. 平均字数：每章约{avg_chapter_length}字
3. 情节结构：起承转合，节奏合理
4. 角色发展：主要角色有完整的成长弧线
5. 冲突设计：层层递进，高潮迭起

【大纲设计原则】
1. **开篇（1-3章）**：引入主角，建立世界观，埋下主线冲突
2. **发展（4-10章）**：角色关系建立，支线展开，小冲突不断
3. **高潮前（11-20章）**：矛盾激化，转折点出现，危机逼近
4. **高潮（21-{total_chapters-3}章）**：主要冲突爆发，情节密集
5. **结局（最后3章）**：收束线索，解决矛盾，留有余韵{f"，最终达到：{story_goal or project.story_goal}" if (story_goal or project.story_goal) else ""}

【输出格式】
请严格按照以下JSON格式输出章节大纲：

```json
[
  {{
    "chapter_number": 1,
    "title": "章节标题（简洁有力）",
    "summary": "章节概要，描述主要情节走向（80-150字）",
    "key_events": [
      "关键事件1：具体描述",
      "关键事件2：具体描述",
      "关键事件3：具体描述"
    ],
    "involved_characters": ["角色1", "角色2", "角色3"],
    "target_length": {avg_chapter_length},
    "notes": "创作要点提示（可选）"
  }},
  {{
    "chapter_number": 2,
    ...
  }}
]
```

⚠️ 关键要求：
1. 每个章节的summary要具体，不要笼统
2. key_events要详细，至少3-5个
3. 确保情节连贯，前后呼应
4. 合理分配角色出场
5. JSON格式必须完全正确
6. 生成完整的{total_chapters}章大纲

现在请开始生成大纲："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.7, max_tokens=8000)
            
            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            outlines = json.loads(response)
            
            print(f"✅ 成功生成{len(outlines)}章大纲")
            return outlines
            
        except Exception as e:
            print(f"❌ 大纲生成失败: {e}")
            return []
    
    def _get_outline_context(self, project: NovelProject, current_chapter: int) -> str:
        """
        获取当前章节的大纲上下文（前后章大纲）
        
        Args:
            project: 小说项目
            current_chapter: 当前章节号
        
        Returns:
            大纲上下文文本
        """
        outlines = sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
        context_parts = []
        
        # 前一章大纲
        prev_outline = next((o for o in outlines if o.chapter_number == current_chapter - 1), None)
        if prev_outline:
            context_parts.append(f"前一章（第{prev_outline.chapter_number}章）：{prev_outline.title}\n  {prev_outline.summary}")
        
        # 当前章标记
        context_parts.append(f"\n👉 当前章节：第{current_chapter}章")
        
        # 后续2章大纲（让AI知道故事走向）
        next_outlines = [o for o in outlines if current_chapter < o.chapter_number <= current_chapter + 2]
        for next_outline in next_outlines[:2]:
            context_parts.append(f"后续章节（第{next_outline.chapter_number}章）：{next_outline.title}\n  {next_outline.summary}")
        
        return "\n".join(context_parts) if context_parts else "无大纲脉络信息"
    
    def generate_chapter_from_outline(
        self,
        project: NovelProject,
        outline: 'ChapterOutline'
    ) -> Chapter:
        """
        根据大纲生成章节
        
        Args:
            project: 小说项目
            outline: 章节大纲
        
        Returns:
            生成的章节
        """
        from ..core.context_manager import ContextManager
        context_manager = ContextManager(max_tokens=self.max_tokens)
        
        # 构建上下文
        context = context_manager.build_writing_context(
            project,
            include_full_recent=2,
            include_summary_count=8
        )
        
        # 🔥 特别强调前一章的内容（用于衔接）
        prev_chapter_context = ""
        if outline.chapter_number > 1:
            prev_chapter = project.get_chapter(outline.chapter_number - 1)
            if prev_chapter:
                # 获取前一章的最后1000字作为衔接上下文
                prev_ending = prev_chapter.content[-1000:] if len(prev_chapter.content) > 1000 else prev_chapter.content
                prev_chapter_context = f"""
【前一章结尾部分】（第{prev_chapter.chapter_number}章：{prev_chapter.title}）
{prev_ending}

⚠️ 重要提示：本章必须从上述内容自然延续，确保情节、场景、角色状态连贯一致！
"""
        
        system_prompt = "你是一位专业的小说作家，擅长根据大纲创作连贯生动的小说章节。" + self.common_prompt
        
        # 获取相关角色信息
        char_details = []
        for char_name in outline.involved_characters:
            char = project.get_character(char_name)
            if char:
                char_details.append(f"- {char.name}: {char.description}")
        
        # 获取已发生的关键事件
        tracker = project.character_tracker
        happened_events = []
        for char_name in outline.involved_characters[:2]:  # 只取前2个主要角色
            experiences = tracker.get_character_experiences(char_name)
            if experiences:
                recent = experiences[-3:]  # 最近3个经历
                for exp in recent:
                    happened_events.append(f"[{char_name}] {exp.description}")
        
        user_prompt = f"""请根据以下大纲创作第{outline.chapter_number}章的完整内容。

{context}

{prev_chapter_context}

【大纲脉络】
{self._get_outline_context(project, outline.chapter_number)}

【本章大纲】
章节编号：第{outline.chapter_number}章
章节标题：{outline.title}
章节概要：{outline.summary}

【关键事件】
{chr(10).join([f"{i+1}. {event}" for i, event in enumerate(outline.key_events)])}

【涉及角色】
{chr(10).join(char_details) if char_details else '请根据情节需要安排角色'}

【已发生的相关事件】
{chr(10).join(happened_events[-5:]) if happened_events else '这是故事的开端'}

【创作要求】
1. **无缝衔接前章**：开头必须自然延续前一章的结尾，场景、时间、角色状态要连贯
2. **严格按照大纲**：所有关键事件都要在章节中体现
3. **情节连贯**：与前面章节不矛盾，角色记忆、关系、状态保持一致
4. **细节丰富**：对话、心理、动作、环境描写要生动具体
5. **节奏把控**：张弛有度，不要平铺直叙
6. **目标字数**：约{outline.target_length}字
7. **承上启下**：既要呼应前文，又要为后续埋下伏笔

{f"【创作提示】{outline.notes}" if outline.notes else ""}

现在请开始创作，直接输出章节内容，不要任何前言后语："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        print(f"\n📝 开始根据大纲生成第{outline.chapter_number}章：{outline.title}")
        print(f"   目标字数: {outline.target_length}")
        print(f"   关键事件数: {len(outline.key_events)}")
        
        # 根据目标字数调整 max_tokens
        target_tokens = int(outline.target_length / 2 * 2)
        target_tokens = max(2000, min(target_tokens, 100000))
        
        response = self._make_request(messages, temperature=0.8, max_tokens=target_tokens)
        
        # 创建章节对象
        chapter = Chapter(
            title=outline.title,
            content=response.strip()
        )
        
        print(f"✅ 章节生成完成，实际字数: {chapter.word_count}")
        
        return chapter
    
    def regenerate_outline_range(
        self,
        project: NovelProject,
        chapter_numbers: List[int],
        avg_chapter_length: int = 3000,
        stage_goal: str = ""
    ) -> List[Dict]:
        """
        重新生成指定范围的章节大纲
        
        Args:
            project: 小说项目
            chapter_numbers: 要重新生成的章节号列表
            avg_chapter_length: 平均章节字数
            stage_goal: 这几章的阶段目标
        
        Returns:
            章节大纲列表
        """
        system_prompt = "你是一位资深小说编剧，擅长调整和优化故事框架。" + self.common_prompt
        
        # 获取前后文大纲信息
        all_outlines = sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
        min_chapter = min(chapter_numbers)
        max_chapter = max(chapter_numbers)
        
        # 前置大纲
        before_outlines = [o for o in all_outlines if o.chapter_number < min_chapter]
        before_context = ""
        if before_outlines:
            before_context = "\n".join([
                f"第{o.chapter_number}章《{o.title}》: {o.summary}"
                for o in before_outlines[-3:]  # 只取前3章
            ])
        
        # 后续大纲
        after_outlines = [o for o in all_outlines if o.chapter_number > max_chapter]
        after_context = ""
        if after_outlines:
            after_context = "\n".join([
                f"第{o.chapter_number}章《{o.title}》: {o.summary}"
                for o in after_outlines[:3]  # 只取后3章
            ])
        
        character_info = "\n".join([
            f"- {char.name}: {char.description}" 
            for char in project.characters
        ])
        
        stage_goal_text = f"\n\n【阶段目标】\n这几章需要达到的状态：{stage_goal}" if stage_goal else ""
        
        user_prompt = f"""请重新规划以下章节的大纲。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
总体目标：{project.story_goal or '未指定'}

【主要角色】
{character_info if character_info else '暂无角色'}

【需要重新规划的章节】
第 {min_chapter} 章到第 {max_chapter} 章（共{len(chapter_numbers)}章）{stage_goal_text}

【前置剧情】（作为参考，不要修改）
{before_context if before_context else '暂无前置剧情'}

【后续剧情】（需衔接，不要修改）
{after_context if after_context else '暂无后续剧情'}

【重新规划要求】
1. 确保与前后剧情自然衔接
2. 情节连贯，节奏合理
3. 每章约{avg_chapter_length}字
4. 角色发展合理
5. 如有阶段目标，需在这几章内达成

【输出格式】
请严格按照JSON格式输出：

```json
[
  {{
    "chapter_number": {min_chapter},
    "title": "章节标题",
    "summary": "章节概要（80-150字）",
    "key_events": ["事件1", "事件2", "事件3"],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "创作要点"
  }},
  ...
]
```

现在请开始重新规划第{min_chapter}-{max_chapter}章的大纲："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.7, max_tokens=6000)
            
            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            outlines = json.loads(response)
            
            print(f"成功生成{len(outlines)}章大纲")
            return outlines
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"响应内容: {response}")
            raise Exception("AI返回的大纲格式错误，请重试")
        except Exception as e:
            print(f"生成大纲时出错: {e}")
            raise
    
    def append_outlines(
        self,
        project: NovelProject,
        additional_chapters: int = 10,
        avg_chapter_length: int = 3000,
        new_goal: str = ""
    ) -> List[Dict]:
        """
        追加生成更多章节大纲
        
        Args:
            project: 小说项目
            additional_chapters: 追加章节数
            avg_chapter_length: 平均章节字数
            new_goal: 续写部分的目标
        
        Returns:
            新增章节大纲列表
        """
        system_prompt = "你是一位资深小说编剧，擅长续写和扩展故事情节。" + self.common_prompt
        
        current_outlines = sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
        current_count = len(current_outlines)
        start_chapter = current_count + 1
        end_chapter = current_count + additional_chapters
        
        # 获取最近几章的大纲作为上下文
        recent_outlines = current_outlines[-5:]  # 取最后5章
        recent_context = "\n".join([
            f"第{o.chapter_number}章《{o.title}》: {o.summary}"
            for o in recent_outlines
        ])
        
        character_info = "\n".join([
            f"- {char.name}: {char.description}" 
            for char in project.characters
        ])
        
        goal_text = new_goal or project.story_goal or "延续之前的故事发展"
        
        user_prompt = f"""请为小说续写章节大纲。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
当前进度：已规划到第{current_count}章

【主要角色】
{character_info if character_info else '暂无角色'}

【最近剧情】（作为续写的基础）
{recent_context}

【续写要求】
1. 起始章节：第{start_chapter}章
2. 结束章节：第{end_chapter}章（共{additional_chapters}章）
3. 续写目标：{goal_text}
4. 每章约{avg_chapter_length}字
5. 确保与已有大纲自然衔接
6. 情节推进合理，走向预期目标

【续写原则】
- 基于已有剧情和角色发展
- 不要与之前的情节矛盾
- 合理安排情节密度和节奏
- 设置悬念和冲突
- 逐步达成目标，留有余韵

【输出格式】
请严格按照JSON格式输出：

```json
[
  {{
    "chapter_number": {start_chapter},
    "title": "章节标题",
    "summary": "章节概要（80-150字）",
    "key_events": ["事件1", "事件2", "事件3"],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "创作要点"
  }},
  ...
]
```

现在请开始生成第{start_chapter}-{end_chapter}章的大纲："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.7, max_tokens=8000)
            
            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            outlines = json.loads(response)
            
            print(f"成功追加生成{len(outlines)}章大纲")
            return outlines
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"响应内容: {response}")
            raise Exception("AI返回的大纲格式错误，请重试")
        except Exception as e:
            print(f"追加大纲时出错: {e}")
            raise


