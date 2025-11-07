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
        self.common_prompt = ""
        
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
        user_prompt_parts.append(f"❌ 章节结尾必须是具体的情节或对话，直接结束即可，绝对不要加'且看下回分解'、'欲知后事如何'等总结性语句")
        user_prompt_parts.append(f"❌ 不要写'本章完'、'未完待续'等提示语")
        
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
        
        # 获取角色当前状态和别名，帮助更准确的分析
        character_context = []
        tracker = project.character_tracker
        for char in project.characters:
            char_name = char.name
            traits = tracker.get_personality_traits(char_name)
            rels = tracker.get_all_relationships(char_name)
            
            # 构建角色上下文信息
            context = f"{char_name}"
            
            # 添加别名信息
            if char.aliases:
                context += f"（别名：{', '.join(char.aliases)}）"
            
            context += "（"
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

【章节内容】（重点部分，已截取前8000字符）
{chapter.content[:8000]}{'...' if len(chapter.content) > 8000 else ''}

【深度分析要求】
请仔细阅读章节内容，从以下维度分析每个角色的**完整经历**：

## 1. 📝 **重要经历**（核心任务：提取详细的事件过程）

对于每个重要事件，需要提取：
- **事件类型**：
  * achievement（成就）：获得的成功、完成的目标、取得的进展
  * conflict（冲突）：遭遇的矛盾、困难、挑战、对抗
  * relationship（关系）：与他人的互动、交流、情感连接
  * growth（成长）：认知、能力、心智的提升和突破
  * trauma（创伤）：负面打击、心理伤害、痛苦经历

- **完整描述**（100-300字，必须包含）：
  1. **事件背景/前因**：为什么会发生这件事？
  2. **具体经过**：发生了什么？有哪些关键细节？
  3. **角色反应**：角色如何应对？说了什么？做了什么？
  4. **事件结果**：最终结果是什么？

- **事件背景** (context)：事件发生的前因和情境（50-100字）
- **情绪状态** (emotional_state)：角色在事件中的情绪变化（30-60字）
- **事件后果** (consequence)：对角色或剧情的影响和后续效应（50-100字）
- **发生场景** (location)：具体地点/场景（如："公司会议室"、"家中卧室"）
- **关键对话/想法** (key_dialogue)：最能体现事件核心的一句话（可选）

**举例说明**（参考这个详细程度）：
```
角色：李明
事件类型：conflict
完整描述：李明在公司年会上当众被总经理批评业绩不佳。事情起因是他上个月的销售额低于目标30%，而总经理在全体员工面前点名："有些人拿着高薪却不干活，该反省了。"李明当时脸色涨红，紧握双拳，但最终还是低着头没有辩解。这次公开批评让他在同事面前颜面扫地，也让他意识到必须改变现状。
背景：上个月业绩未达标，总经理对团队整体表现不满
情绪：从震惊、羞愧到愤怒，最后是深深的挫败感和自我怀疑
后果：在同事中威信下降，激发了他要证明自己的决心，开始重新审视工作方法
场景：公司年会宴会厅，200多名员工在场
关键对话："有些人拿着高薪却不干活，该反省了。"
```

## 2. 🤝 **关系变化**：角色间关系的微妙变化
   - 仔细观察：对话语气、肢体接触、眼神交流、互动频率
   - 亲密度变化范围：-20到+20（只记录明显变化）
   - 关系类型：friend/enemy/family/lover/mentor/rival/neutral
   - 关系描述要具体：如"上下级关系，王芳是李明的直属上司，平时管得很严"
   - 变化原因要详细：50-100字，说清楚为什么关系发生了变化

## 3. 🧠 **性格演变**：性格特质强度的变化
   - 从具体行为、对话、心理活动推断
   - 常见特质：勇敢、自信、开放性、支配性、温柔、果断、耐心、冷静等
   - 强度变化：-20到+20（只记录明显变化）
   - 原因要详细：50-100字，说明什么事件导致了性格变化

【输出格式】
严格按照以下JSON格式输出，不要添加任何注释或说明文字：

```json
{{
  "experiences": [
    {{
      "character": "角色名（必须是已知角色之一）",
      "event_type": "achievement或conflict或relationship或growth或trauma",
      "description": "事件的完整描述，包含背景、经过、反应、结果（100-300字）",
      "impact": "positive或negative或neutral",
      "related_characters": ["相关角色1", "相关角色2"],
      "context": "事件发生的背景/前因（50-100字）",
      "emotional_state": "角色的情绪状态和变化（30-60字）",
      "consequence": "事件的后果和影响（50-100字）",
      "location": "发生地点/场景",
      "key_dialogue": "关键对话或想法（可选）"
    }}
  ],
  "relationships": [
    {{
      "character": "角色A（必须是已知角色）",
      "target": "角色B（必须是已知角色）",
      "type": "friend或enemy或family或lover或mentor或rival或neutral",
      "intimacy_change": 5,
      "description": "关系的详细描述（30-80字）",
      "reason": "导致关系变化的具体原因，包含事件经过（50-100字）"
    }}
  ],
  "personality_changes": [
    {{
      "character": "角色名（必须是已知角色）",
      "trait": "性格特质名称",
      "intensity_change": 5,
      "reason": "导致性格变化的详细原因（50-100字）"
    }}
  ]
}}
```

⚠️ 关键要求：
1. **只分析已知角色**：{', '.join(character_names)}
2. **经历描述必须详细**：每个事件100-300字，包含背景、经过、反应、结果
3. **提取所有重要事件**：不要遗漏任何对角色有影响的事件
4. **数值范围**：intimacy_change和intensity_change：-20到+20之间的整数
5. **避免笼统概括**：要有具体细节、对话、行为描写
6. **JSON格式严格**：不要有注释、不要省略字段、不要有额外字符
7. **重点关注**：对话、心理描写、行为细节、情感变化

⚠️ 特别提醒：
- 如果某个事件很重要，宁可写得详细一些，不要惜字如金
- 每个角色至少应该有2-3个重要经历（如果章节中有的话）
- 如果某类别确实无内容，才返回空数组[]
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3, max_tokens=6000)
            
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
        
        # 第一步：识别角色别名
        if project.characters:
            print(f"\n🔍 识别角色别名...")
            known_character_names = [char.name for char in project.characters]
            aliases = self.identify_character_aliases(
                chapter_content=chapter.content,
                known_characters=known_character_names
            )
            
            # 自动添加识别到的别名
            for char_name, alias_list in aliases.items():
                char = project.get_character_by_exact_name(char_name)
                if char:
                    for alias in alias_list:
                        if char.add_alias(alias):
                            print(f"   ✅ 为 {char_name} 添加别名: {alias}")
        
        # 第二步：分析角色事件
        analysis = self.analyze_chapter_for_character_events(project, chapter)
        tracker = project.character_tracker
        
        # 第三步：将分析结果中的别名统一转换为正式名字
        def normalize_character_name(name: str) -> str:
            """将可能的别名转换为正式名字"""
            canonical = project.find_character_canonical_name(name)
            return canonical if canonical else name
        
        # 转换experiences中的角色名
        for exp in analysis.get("experiences", []):
            exp["character"] = normalize_character_name(exp["character"])
            if "related_characters" in exp:
                exp["related_characters"] = [
                    normalize_character_name(name) 
                    for name in exp["related_characters"]
                ]
        
        # 转换relationships中的角色名
        for rel in analysis.get("relationships", []):
            rel["character"] = normalize_character_name(rel["character"])
            rel["target"] = normalize_character_name(rel["target"])
        
        # 转换personality_changes中的角色名
        for pc in analysis.get("personality_changes", []):
            pc["character"] = normalize_character_name(pc["character"])
        
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
            desc_preview = exp['description'][:50] + "..." if len(exp['description']) > 50 else exp['description']
            print(f"   📝 {exp['character']}: {desc_preview}")
            tracker.add_experience(
                character_name=exp["character"],
                chapter_number=chapter.chapter_number,
                event_type=exp["event_type"],
                description=exp["description"],
                impact=exp["impact"],
                related_characters=exp.get("related_characters", []),
                context=exp.get("context", ""),
                emotional_state=exp.get("emotional_state", ""),
                consequence=exp.get("consequence", ""),
                location=exp.get("location", ""),
                key_dialogue=exp.get("key_dialogue", "")
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
        
        # 计算三幕剧的章节分布
        act1_end = max(3, int(total_chapters * 0.25))  # 第一幕：前25%
        act2_end = max(act1_end + 5, int(total_chapters * 0.75))  # 第二幕：25%-75%
        midpoint = int(total_chapters * 0.5)  # 中点
        
        user_prompt = f"""请为以下小说构建完整的章节大纲。你需要创造一个引人入胜、充满悬念、情节不重复的故事。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
背景设定：{project.background or '未指定'}
总体大纲：{project.plot_outline or '未指定'}
写作风格：{project.writing_style or '未指定'}{goal_section}

【主要角色】
{character_info if character_info else '暂无角色'}

【总体要求】
- 总章节数：{total_chapters}章
- 每章约{avg_chapter_length}字
- 遵循三幕剧结构，节奏分明
- 每章都要有新的进展，绝不重复内容
- 设置悬念和伏笔，让读者欲罢不能

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【三幕剧结构设计】（请严格遵循）

🎬 **第一幕：设定与冲突（第1-{act1_end}章）**
目标：建立世界，介绍角色，引出主要冲突

第1章：开场钩子
  - 用强烈的场景或事件吸引读者
  - 展示主角的日常生活或初始状态
  - 埋下第一个悬念或疑问

第2-{act1_end-1}章：建立世界
  - 逐步展现世界观和规则
  - 介绍主要角色及其关系
  - 铺垫主线冲突的根源
  - 至少埋下2-3个伏笔

第{act1_end}章：进入第二幕的转折点
  - 重大事件发生，主角被迫行动
  - 主角做出关键决定，踏上旅程
  - 故事从"准备"转向"行动"

🎬 **第二幕：对抗与升级（第{act1_end+1}-{act2_end}章）**
目标：矛盾激化，多次挫折，角色成长

第{act1_end+1}-{midpoint-1}章：初次尝试与挫折
  - 主角采取行动，但遇到困难
  - 引入新的支线和次要角色
  - 揭示部分真相，但产生更多疑问
  - 小胜利与小失败交替，制造张力

第{midpoint}章：中点转折（超级重要！）
  - 重大真相揭露或假胜利/假失败
  - 故事走向发生根本性变化
  - 主角的目标或动机改变
  - 赌注升级，风险加倍

第{midpoint+1}-{act2_end-1}章：黑暗时刻与最低点
  - 情况急转直下，主角陷入困境
  - 内外双重压力（外部冲突+内心挣扎）
  - 同伴背叛或分离、秘密曝光等
  - 至少回收1-2个前面的伏笔

第{act2_end}章：第二幕结束的低谷
  - 主角最绝望的时刻
  - 似乎一切都失败了
  - 但萌生新的觉悟或获得关键信息
  - 为最终决战做准备

🎬 **第三幕：高潮与结局（第{act2_end+1}-{total_chapters}章）**
目标：决战、真相大白、完成角色弧光

第{act2_end+1}-{total_chapters-2}章：最终对决
  - 主角集结力量，发起反击
  - 激烈的高潮场景
  - 反派最后的挣扎或反转
  - 回收所有重要伏笔

第{total_chapters-1}章：尾声前奏
  - 主要冲突解决
  - 次要线索收束
  - 展示角色的成长和变化

第{total_chapters}章：结局
  - 新的平衡状态
  - 角色的最终归宿{f"，达成：{story_goal or project.story_goal}" if (story_goal or project.story_goal) else ""}
  - 可留白或开放式结局
  - 呼应开篇，形成完整闭环

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【核心创作原则】（必须遵守！）

✅ **悬念设计**
- 每章结尾留下钩子（疑问、危机、转折）
- 设置至少3-5个贯穿全文的悬念线
- 分层揭示真相，不要一次说完
- 用"为什么"、"接下来呢"驱动阅读

✅ **伏笔与回收**
- 前{act1_end}章至少埋下5个伏笔
- 第{midpoint}章前后回收2-3个
- 高潮章节回收剩余所有伏笔
- 伏笔要自然，不刻意

✅ **避免重复**
- 每章必须推进主线或支线
- 不要重复相同类型的场景（如：不要3次约会场景、不要2次类似的打斗）
- 不要让角色反复讨论同一个问题
- 每章的"关键事件"必须是全新的内容

✅ **节奏控制**
- 紧张（冲突、危机）与舒缓（日常、情感）交替
- 每3-5章安排一个小高潮
- 中点和结尾是大高潮
- 避免连续多章平淡无奇

✅ **角色成长**
- 主角要有明确的成长弧线（从A状态到B状态）
- 配角也要有变化，不能只是工具人
- 通过冲突和选择展现角色性格
- 关系要发展（从陌生到熟悉、从信任到背叛等）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【输出格式】
请严格按照以下JSON格式输出{total_chapters}章大纲：

```json
[
  {{
    "chapter_number": 1,
    "title": "引人入胜的标题",
    "summary": "详细概要（100-150字），包含：主要场景、核心事件、角色状态、情感走向、章末悬念",
    "key_events": [
      "事件1：具体行动+结果",
      "事件2：对话或冲突+影响",
      "事件3：转折或发现+后续影响",
      "事件4（可选）：伏笔或铺垫"
    ],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "【悬念】本章留下什么疑问？【伏笔】埋下什么线索？【情绪】主基调是什么？"
  }}
]
```

⚠️ **严格检查清单**
1. ✅ 是否遵循三幕剧结构？
2. ✅ 每章是否都有新内容，没有重复？
3. ✅ 是否设置了足够的悬念和钩子？
4. ✅ 伏笔是否合理分布并在后文回收？
5. ✅ 节奏是否张弛有度？
6. ✅ 角色是否有成长变化？
7. ✅ JSON格式是否完全正确？

现在请深呼吸，认真思考故事结构，然后生成一个精彩的{total_chapters}章大纲："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # 根据章节数动态调整max_tokens
            # 每章大约需要200-300 tokens，预留一些空间
            estimated_tokens = total_chapters * 300 + 1000
            max_tokens_needed = min(estimated_tokens, 16000)  # 最多16k tokens
            
            print(f"📝 开始生成{total_chapters}章大纲（预计需要{estimated_tokens} tokens）")
            
            response = self._make_request(messages, temperature=0.7, max_tokens=max_tokens_needed)
            
            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            outlines = json.loads(response)
            
            # 验证大纲质量
            if len(outlines) != total_chapters:
                print(f"⚠️ 警告：生成了{len(outlines)}章，预期{total_chapters}章")
            
            print(f"✅ 成功生成{len(outlines)}章大纲")
            return outlines
            
        except Exception as e:
            print(f"❌ 大纲生成失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def regenerate_full_outline_with_feedback(
        self,
        project: NovelProject,
        user_feedback: str,
        old_outlines: List[Dict],
        total_chapters: int = 30,
        avg_chapter_length: int = 3000
    ) -> List[Dict]:
        """
        根据用户反馈重新生成完整大纲
        
        Args:
            project: 小说项目
            user_feedback: 用户的修改意见
            old_outlines: 上一次生成的大纲
            total_chapters: 总章节数
            avg_chapter_length: 平均章节字数
        
        Returns:
            新的章节大纲列表
        """
        system_prompt = "你是一位资深小说编剧，擅长根据反馈意见优化和重构故事大纲。" + self.common_prompt
        
        character_info = "\n".join([
            f"- {char.name}: {char.description}" 
            for char in project.characters
        ])
        
        # 构建旧大纲摘要
        old_outline_summary = "\n".join([
            f"第{o.get('chapter_number', i+1)}章：{o.get('title', '未命名')}\n  概要：{o.get('summary', '')[:100]}"
            for i, o in enumerate(old_outlines[:10])  # 只展示前10章避免太长
        ])
        
        if len(old_outlines) > 10:
            old_outline_summary += f"\n...（共{len(old_outlines)}章，此处省略后续章节）"
        
        # 计算三幕剧的章节分布
        act1_end = max(3, int(total_chapters * 0.25))
        act2_end = max(act1_end + 5, int(total_chapters * 0.75))
        midpoint = int(total_chapters * 0.5)
        
        user_prompt = f"""请根据用户的修改意见，重新生成小说的完整章节大纲。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
背景设定：{project.background or '未指定'}
总体大纲：{project.plot_outline or '未指定'}
写作风格：{project.writing_style or '未指定'}
故事目标：{project.story_goal or '未指定'}

【主要角色】
{character_info if character_info else '暂无角色'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【上一版本大纲】
{old_outline_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 【用户修改意见】（最高优先级！）
{user_feedback}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【任务要求】
1. **严格遵循用户意见**：用户的反馈是最高优先级，必须充分体现在新大纲中
2. **保留可取之处**：如果用户没有明确否定的部分，可以保留并优化
3. **解决用户提出的问题**：针对性地改进用户不满意的地方
4. **保持三幕剧结构**：第一幕（第1-{act1_end}章）、第二幕（第{act1_end+1}-{act2_end}章）、第三幕（第{act2_end+1}-{total_chapters}章）
5. **避免重复**：每章必须有新内容，不要重复相同类型的场景和事件
6. **设置悬念**：每章结尾留下钩子，让读者想继续读下去
7. **总章节数**：{total_chapters}章，每章约{avg_chapter_length}字

【输出格式】
请严格按照以下JSON格式输出{total_chapters}章大纲：

```json
[
  {{
    "chapter_number": 1,
    "title": "引人入胜的标题",
    "summary": "详细概要（100-150字），包含：主要场景、核心事件、角色状态、情感走向、章末悬念",
    "key_events": [
      "事件1：具体行动+结果",
      "事件2：对话或冲突+影响",
      "事件3：转折或发现+后续影响"
    ],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "【改进说明】相比上一版有什么优化？如何体现用户意见？"
  }}
]
```

⚠️ **重要提醒**
- 必须完整输出{total_chapters}章的大纲
- JSON格式必须完全正确，可以被程序解析
- 每一章都要体现"根据用户意见的改进"
- 确保新大纲比旧大纲更好、更符合用户期望

现在请认真分析用户意见，生成改进后的{total_chapters}章大纲："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            estimated_tokens = total_chapters * 300 + 1000
            max_tokens_needed = min(estimated_tokens, 16000)
            
            print(f"📝 开始根据用户反馈重新生成{total_chapters}章大纲")
            print(f"📋 用户意见：{user_feedback[:100]}...")
            
            response = self._make_request(messages, temperature=0.7, max_tokens=max_tokens_needed)
            
            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            import json
            outlines = json.loads(response)
            
            if len(outlines) != total_chapters:
                print(f"⚠️ 警告：生成了{len(outlines)}章，预期{total_chapters}章")
            
            print(f"✅ 成功根据反馈重新生成{len(outlines)}章大纲")
            return outlines
            
        except Exception as e:
            print(f"❌ 大纲重新生成失败: {e}")
            import traceback
            traceback.print_exc()
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
        # 增加历史摘要数量，让AI更清楚前面发生了什么，避免重复描述
        context = context_manager.build_writing_context(
            project,
            include_full_recent=2,
            include_summary_count=15  # 从8增加到15，涵盖更多历史信息
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
        
        # 🔥 风格设定（最高优先级）
        style_guide_section = ""
        if project.style_guide and project.style_guide.strip():
            style_guide_section = f"""
⚠️⚠️⚠️ 【风格设定 - 最高优先级】 ⚠️⚠️⚠️
{project.style_guide}
以上风格设定必须严格遵守，优先级高于所有其他要求！
================================

"""
        
        user_prompt = f"""请根据以下大纲创作第{outline.chapter_number}章的完整内容。

{style_guide_section}{context}

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
8. **自然结尾**：章节结尾必须是具体的情节或对话，直接结束即可，绝对不要加"且看下回分解"、"欲知后事如何"等总结性语句，也不要写"本章完"
9. **避免重复**：不要重复前面章节已经详细描述过的内容（如角色外貌、背景设定等），只需简短提及即可
10. **保持沉浸感**：让读者沉浸在故事中，下一章会自然延续，不需要任何提示
11. **开头多样性**：每章开头要有变化，可以从对话、动作、内心独白、环境描写等不同角度切入，避免使用相同的场景描述模式（例如：不要每章都从"某地的夜色依旧..."、"LOFT公寓的落地窗外..."等相似句式开始）
12. **避免公式化**：拒绝使用固定的叙事模板和套路化的场景铺陈，每章都应该有独特的叙事节奏和视角，让读者感受到新鲜感

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
        
        user_prompt = f"""请重新规划第{min_chapter}到第{max_chapter}章的大纲（共{len(chapter_numbers)}章）。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
总体目标：{project.story_goal or '未指定'}

【主要角色】
{character_info if character_info else '暂无角色'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【重新规划的范围】
第{min_chapter}章 到 第{max_chapter}章

【前置剧情】（不可修改，必须衔接）
{before_context if before_context else '这是故事开端，无前置剧情'}

【后续剧情】（不可修改，必须对接）
{after_context if after_context else '后续未规划'}

{stage_goal_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【重新规划核心原则】

✅ **前后衔接**
- 必须从前置剧情自然延续
- 必须为后续剧情铺垫或过渡
- 不能与已有设定矛盾

✅ **避免重复**
- 不要重复前置剧情中的内容
- 每章都要有新的实质性进展
- 不要让角色做相同的事情

✅ **故事结构**
- 根据章节在整体中的位置安排节奏
- 开头部分：建立基础，缓慢推进
- 中间部分：冲突升级，张弛有度
- 结尾部分：快速推进，高潮迭起

✅ **悬念设计**
- 每章设置新的悬念或问题
- 逐步揭示真相，但保留谜团
- 章节结尾留下钩子

✅ **角色发展**
- 继续推进角色成长
- 深化角色关系变化
- 避免角色行为不一致

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【输出格式】
请严格按照以下JSON格式输出{len(chapter_numbers)}章大纲：

```json
[
  {{
    "chapter_number": {min_chapter},
    "title": "引人入胜的标题",
    "summary": "详细概要（100-150字），包含：主要场景、核心事件、角色状态、情感走向、章末悬念",
    "key_events": [
      "事件1：具体行动+结果",
      "事件2：对话或冲突+影响",
      "事件3：转折或发现+后续影响"
    ],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "【悬念】本章留下什么疑问？【衔接】如何连接前后章节？"
  }}
]
```

⚠️ **检查清单**
1. ✅ 是否与前置剧情自然衔接？
2. ✅ 是否为后续剧情做好准备？
3. ✅ 每章是否都有新内容，没有重复？
4. ✅ 是否设置了足够的悬念？
5. ✅ 节奏是否合理？
6. ✅ JSON格式是否正确？

现在请深呼吸，认真思考故事结构，重新规划第{min_chapter}-{max_chapter}章的大纲："""
        
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
        
        user_prompt = f"""请为小说续写章节大纲，从第{start_chapter}章到第{end_chapter}章。

【小说信息】
标题：{project.title}
类型：{project.genre or '未指定'}
当前进度：已规划到第{current_count}章

【主要角色】
{character_info if character_info else '暂无角色'}

【最近5章剧情】（续写的起点）
{recent_context}

【续写目标】
{goal_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【续写核心原则】

✅ **无缝衔接**
- 从第{current_count}章的结尾自然延续
- 不要突兀地引入新元素
- 保持已建立的故事基调和节奏

✅ **避免重复**
- 不要重复前{current_count}章已经发生的情节
- 不要让角色反复做相同的事情
- 每章都要有实质性的新进展

✅ **设置悬念**
- 续写部分要有新的悬念和冲突
- 每章结尾留下钩子
- 逐步揭示真相，但保留部分谜团

✅ **角色发展**
- 继续推进角色成长弧线
- 深化已有角色关系
- 如需引入新角色，要有充分理由

✅ **节奏控制**
- 根据在故事中的位置调整节奏
- 如果接近结局，要加快节奏、提高密度
- 如果还在中段，要稳定推进、张弛有度

✅ **目标导向**
- 每章都要朝着"{goal_text}"靠近
- 不要无意义的支线或拖沓
- 最终要自然地达成目标

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【输出格式】
请严格按照以下JSON格式输出{additional_chapters}章大纲：

```json
[
  {{
    "chapter_number": {start_chapter},
    "title": "引人入胜的标题",
    "summary": "详细概要（100-150字），包含：主要场景、核心事件、角色状态、情感走向、章末悬念",
    "key_events": [
      "事件1：具体行动+结果",
      "事件2：对话或冲突+影响",
      "事件3：转折或发现+后续影响"
    ],
    "involved_characters": ["角色1", "角色2"],
    "target_length": {avg_chapter_length},
    "notes": "【悬念】本章留下什么疑问？【与前文的联系】如何衔接第{current_count}章？"
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
    
    def extract_characters_from_novel(
        self,
        novel_content: str,
        max_content_length: int = 100000  # 约100KB的中文文本
    ) -> List[Dict[str, str]]:
        """
        从导入的小说中提取主要角色
        
        Args:
            novel_content: 小说全文内容
            max_content_length: 最大分析内容长度（避免超过上下文限制）
        
        Returns:
            角色列表，每个包含: name, description, personality, relationships
        """
        # 如果小说太长，只分析前半部分（通常前半部分会介绍主要角色）
        if len(novel_content) > max_content_length:
            novel_content = novel_content[:max_content_length]
            analysis_note = f"（分析前{max_content_length}字）"
        else:
            analysis_note = ""
        
        system_prompt = "你是一位资深的小说分析专家，擅长从小说中提取和总结角色信息。"
        
        user_prompt = f"""请分析以下小说内容{analysis_note}，提取所有**重要角色**的信息。

【小说内容】：
{novel_content}

【提取要求】：
1. 只提取**主要角色和重要配角**（不要提取路人甲乙等次要角色）
2. 对于每个角色，提取：
   - name: 角色名字
   - description: 角色的外貌、身份、职业、特点（50-120字）
   - personality: 性格特点（30-80字）
   - relationships: 与其他角色的关系（如果有）

3. 按角色重要性排序（主角最前面）

4. 尽量完整准确，基于小说中的实际描写

【输出格式】（必须是有效的JSON）：
```json
[
  {{
    "name": "角色名字",
    "description": "角色的外貌、身份、职业、特点等详细描述",
    "personality": "性格特点",
    "relationships": "与其他角色的关系（可选）"
  }}
]
```

⚠️ 注意：
- 只返回JSON数组，不要其他内容
- 至少提取5个主要角色（如果有的话）
- 如果角色没有明显关系描述，relationships字段可以为空字符串
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3, max_tokens=4000)
            
            # 提取JSON
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
            start_idx = json_str.find('[')
            end_idx = json_str.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = json_str[start_idx:end_idx + 1]
            
            # 解析JSON
            characters = json.loads(json_str)
            
            # 确保返回的是列表
            if not isinstance(characters, list):
                print(f"⚠️ 返回的不是列表: {type(characters)}")
                return []
            
            # 验证每个角色的数据结构
            validated_characters = []
            for char in characters:
                if isinstance(char, dict) and char.get("name"):
                    # 确保所有字段都存在
                    validated_char = {
                        "name": char.get("name", ""),
                        "description": char.get("description", ""),
                        "personality": char.get("personality", ""),
                        "relationships": char.get("relationships", "")
                    }
                    validated_characters.append(validated_char)
            
            print(f"✓ 成功提取{len(validated_characters)}个角色")
            return validated_characters
            
        except json.JSONDecodeError as e:
            print(f"⚠️ 角色提取失败 (JSON解析错误): {e}")
            print(f"   响应内容: {response[:300]}...")
            return []
        except Exception as e:
            print(f"⚠️ 角色提取失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def analyze_project_info(
        self,
        project: NovelProject
    ) -> Dict[str, str]:
        """
        使用AI分析项目，自动生成类型、背景和大纲
        
        Args:
            project: 小说项目
        
        Returns:
            包含 genre, background, plot_outline 的字典
        """
        if not project.chapters or len(project.chapters) == 0:
            raise Exception("项目中没有章节，无法分析")
        
        # 收集所有章节内容（限制长度）
        all_content = ""
        max_length = 50000  # 约50KB，足够分析
        
        for chapter in project.chapters:
            if len(all_content) >= max_length:
                break
            remaining = max_length - len(all_content)
            all_content += f"\n\n【第{chapter.chapter_number}章：{chapter.title}】\n{chapter.content[:remaining]}"
        
        if len(all_content) < 500:
            raise Exception("内容太短，无法进行有效分析")
        
        print(f"📊 开始AI分析项目...")
        print(f"   分析内容长度: {len(all_content)} 字符")
        print(f"   章节数: {len(project.chapters)}")
        
        system_prompt = "你是一位资深的小说编辑和文学评论家，擅长分析小说的类型、背景设定和故事大纲。"
        
        user_prompt = f"""请分析以下小说内容，提供专业的分类和总结。

【小说标题】：{project.title}

【小说内容】：
{all_content}

【分析要求】：
请基于实际内容，提供以下信息：

1. **类型（genre）**：
   - 识别小说的主要类型（如：科幻、奇幻、悬疑、都市、言情、武侠等）
   - 可以是混合类型（例如："科幻悬疑"）
   - 20字以内

2. **背景设定（background）**：
   - 概括故事发生的世界观、时代背景、地点
   - 包括关键的世界设定元素
   - 100-200字

3. **故事大纲（plot_outline）**：
   - 概括主要情节线索
   - 包括主角目标、主要冲突、故事发展方向
   - 不要透露结局（如果是进行中的故事）
   - 200-400字

【输出格式】（必须是有效的JSON）：
```json
{{
  "genre": "小说类型",
  "background": "背景设定描述",
  "plot_outline": "故事大纲"
}}
```

⚠️ 注意：
- 只返回JSON对象，不要其他内容
- 基于实际内容分析，不要编造
- 使用准确、专业的描述
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.5, max_tokens=2000)
            
            # 提取JSON
            import re
            import json
            
            # 尝试提取JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    json_str = response.strip()
            
            # 查找JSON对象
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = json_str[start_idx:end_idx + 1]
            
            # 解析JSON
            result = json.loads(json_str)
            
            # 验证必需字段
            required_fields = ['genre', 'background', 'plot_outline']
            for field in required_fields:
                if field not in result:
                    result[field] = ""
            
            print(f"✅ AI分析完成")
            print(f"   类型: {result['genre']}")
            print(f"   背景: {result['background'][:50]}...")
            print(f"   大纲: {result['plot_outline'][:50]}...")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️ 分析失败 (JSON解析错误): {e}")
            print(f"   响应内容: {response[:500]}...")
            raise Exception("AI返回的分析结果格式错误，请重试")
        except Exception as e:
            print(f"⚠️ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def identify_character_aliases(
        self,
        chapter_content: str,
        known_characters: List[str],
        max_content_length: int = 10000
    ) -> Dict[str, List[str]]:
        """
        识别章节中出现的角色别名
        
        Args:
            chapter_content: 章节内容
            known_characters: 已知的角色正式名字列表
            max_content_length: 最大分析内容长度
        
        Returns:
            字典，key为正式名字，value为在本章中出现的别名列表
            例如: {"林歆颜": ["林老师", "小颜", "妻子"], "张明": ["老公", "明哥"]}
        """
        # 限制内容长度
        if len(chapter_content) > max_content_length:
            chapter_content = chapter_content[:max_content_length]
        
        system_prompt = """你是一位专业的文本分析专家，擅长识别小说中同一个角色的不同称呼。"""
        
        user_prompt = f"""请分析以下小说章节，识别出每个角色在文中的**所有不同称呼**（别名、昵称、关系称呼等）。

【已知角色列表】：
{chr(10).join(f'- {name}' for name in known_characters)}

【章节内容】：
{chapter_content}

【分析要求】：
1. 对于每个已知角色，找出在文中出现的**所有不同称呼**
2. 包括但不限于：
   - 昵称、小名（如"小颜"、"小明"）
   - 职业称呼（如"林老师"、"王医生"）
   - 关系称呼（如"妻子"、"老公"、"妈妈"）
   - 敬称（如"林总"、"张哥"）
   - 其他指代（如"那个女人"、"他"等代词不用）
3. 只识别**明确指代某个角色的称呼**，不要包含模糊的代词
4. 如果某个角色在本章没有出现或只用正式名字，则不返回该角色

【输出格式】（必须是有效的JSON）：
```json
{{
  "角色正式名字": ["别名1", "别名2", "别名3"],
  "另一个角色": ["别名1", "别名2"]
}}
```

⚠️ 注意：
- 只返回JSON对象，不要其他内容
- 别名应该是实际在文中出现的称呼
- 不要返回正式名字本身
- 如果某个角色没有别名，不要在结果中包含该角色
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.2, max_tokens=2000)
            
            # 提取JSON
            import re
            import json
            
            # 提取JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    json_str = response.strip()
            
            # 查找JSON对象
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = json_str[start_idx:end_idx + 1]
            
            # 解析JSON
            aliases = json.loads(json_str)
            
            # 验证返回的是字典
            if not isinstance(aliases, dict):
                print(f"⚠️ 返回的不是字典: {type(aliases)}")
                return {}
            
            # 验证每个值都是列表
            validated_aliases = {}
            for char_name, alias_list in aliases.items():
                if char_name in known_characters:
                    if isinstance(alias_list, list):
                        # 过滤掉空字符串和正式名字本身
                        validated_list = [
                            alias for alias in alias_list 
                            if alias and isinstance(alias, str) and alias != char_name
                        ]
                        if validated_list:
                            validated_aliases[char_name] = validated_list
            
            if validated_aliases:
                print(f"✅ 识别到角色别名:")
                for char, aliases in validated_aliases.items():
                    print(f"   {char}: {', '.join(aliases)}")
            else:
                print("ℹ️ 本章未识别到新的角色别名")
            
            return validated_aliases
            
        except json.JSONDecodeError as e:
            print(f"⚠️ 别名识别失败 (JSON解析错误): {e}")
            print(f"   响应内容: {response[:300]}...")
            return {}
        except Exception as e:
            print(f"⚠️ 别名识别失败: {e}")
            import traceback
            traceback.print_exc()
            return {}


