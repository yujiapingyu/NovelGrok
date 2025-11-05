#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色动态追踪管理器
追踪角色经历、关系变化、性格发展
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class CharacterExperience:
    """角色经历事件"""
    chapter_number: int
    event_type: str  # 'achievement', 'conflict', 'relationship', 'growth', 'trauma'
    description: str
    impact: str  # 'positive', 'negative', 'neutral'
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    related_characters: List[str] = field(default_factory=list)
    # 新增字段：提供更丰富的事件信息
    context: str = ""  # 事件发生的背景/前因
    emotional_state: str = ""  # 角色当时的情绪状态
    consequence: str = ""  # 事件的后果/影响
    location: str = ""  # 事件发生的场景/地点
    key_dialogue: str = ""  # 关键对话或想法
    
    def to_dict(self) -> dict:
        return {
            'chapter_number': self.chapter_number,
            'event_type': self.event_type,
            'description': self.description,
            'impact': self.impact,
            'timestamp': self.timestamp,
            'related_characters': self.related_characters,
            'context': self.context,
            'emotional_state': self.emotional_state,
            'consequence': self.consequence,
            'location': self.location,
            'key_dialogue': self.key_dialogue
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'CharacterExperience':
        # 兼容旧数据格式
        return CharacterExperience(
            chapter_number=data.get('chapter_number', 0),
            event_type=data.get('event_type', 'unknown'),
            description=data.get('description', ''),
            impact=data.get('impact', 'neutral'),
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            related_characters=data.get('related_characters', []),
            context=data.get('context', ''),
            emotional_state=data.get('emotional_state', ''),
            consequence=data.get('consequence', ''),
            location=data.get('location', ''),
            key_dialogue=data.get('key_dialogue', '')
        )


@dataclass
class CharacterRelationship:
    """角色关系"""
    target_character: str
    relationship_type: str  # 'friend', 'enemy', 'family', 'lover', 'mentor', 'rival', 'neutral'
    intimacy_level: int  # 0-100
    description: str
    evolution_history: List[Dict] = field(default_factory=list)
    first_met_chapter: Optional[int] = None
    
    def to_dict(self) -> dict:
        return {
            'target_character': self.target_character,
            'relationship_type': self.relationship_type,
            'intimacy_level': self.intimacy_level,
            'description': self.description,
            'evolution_history': self.evolution_history,
            'first_met_chapter': self.first_met_chapter
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'CharacterRelationship':
        return CharacterRelationship(**data)
    
    def update(self, new_type: str = None, intimacy_change: int = 0, reason: str = "", chapter: int = None):
        """更新关系状态"""
        old_type = self.relationship_type
        old_intimacy = self.intimacy_level
        
        if new_type:
            self.relationship_type = new_type
        if intimacy_change:
            self.intimacy_level = max(0, min(100, self.intimacy_level + intimacy_change))
        
        # 记录变化历史
        if old_type != self.relationship_type or intimacy_change != 0:
            self.evolution_history.append({
                'chapter': chapter,
                'timestamp': datetime.now().isoformat(),
                'old_type': old_type,
                'new_type': self.relationship_type,
                'old_intimacy': old_intimacy,
                'new_intimacy': self.intimacy_level,
                'reason': reason
            })


@dataclass
class PersonalityTrait:
    """性格特质"""
    trait_name: str
    intensity: int  # 0-100，强度
    description: str
    
    def to_dict(self) -> dict:
        return {
            'trait_name': self.trait_name,
            'intensity': self.intensity,
            'description': self.description
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'PersonalityTrait':
        return PersonalityTrait(**data)


@dataclass
class PersonalityEvolution:
    """性格演变记录"""
    chapter_number: int
    trait_name: str
    old_intensity: int
    new_intensity: int
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            'chapter_number': self.chapter_number,
            'trait_name': self.trait_name,
            'old_intensity': self.old_intensity,
            'new_intensity': self.new_intensity,
            'reason': self.reason,
            'timestamp': self.timestamp
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'PersonalityEvolution':
        return PersonalityEvolution(**data)


class CharacterTracker:
    """角色动态追踪管理器"""
    
    def __init__(self):
        self.experiences: Dict[str, List[CharacterExperience]] = {}
        self.relationships: Dict[str, List[CharacterRelationship]] = {}
        self.personality_traits: Dict[str, List[PersonalityTrait]] = {}
        self.personality_evolution: Dict[str, List[PersonalityEvolution]] = {}
    
    # ========== 经历管理 ==========
    
    def add_experience(
        self,
        character_name: str,
        chapter_number: int,
        event_type: str,
        description: str,
        impact: str = 'neutral',
        related_characters: List[str] = None,
        context: str = "",
        emotional_state: str = "",
        consequence: str = "",
        location: str = "",
        key_dialogue: str = ""
    ):
        """添加角色经历"""
        if character_name not in self.experiences:
            self.experiences[character_name] = []
        
        experience = CharacterExperience(
            chapter_number=chapter_number,
            event_type=event_type,
            description=description,
            impact=impact,
            related_characters=related_characters or [],
            context=context,
            emotional_state=emotional_state,
            consequence=consequence,
            location=location,
            key_dialogue=key_dialogue
        )
        self.experiences[character_name].append(experience)
    
    def get_character_experiences(
        self,
        character_name: str,
        event_type: Optional[str] = None,
        chapter_range: Optional[tuple] = None
    ) -> List[CharacterExperience]:
        """获取角色经历"""
        if character_name not in self.experiences:
            return []
        
        experiences = self.experiences[character_name]
        
        # 按类型筛选
        if event_type:
            experiences = [e for e in experiences if e.event_type == event_type]
        
        # 按章节范围筛选
        if chapter_range:
            start, end = chapter_range
            experiences = [e for e in experiences if start <= e.chapter_number <= end]
        
        return sorted(experiences, key=lambda x: x.chapter_number)
    
    # ========== 关系管理 ==========
    
    def add_relationship(
        self,
        character_name: str,
        target_character: str,
        relationship_type: str,
        intimacy_level: int = 50,
        description: str = "",
        first_met_chapter: int = None
    ):
        """添加或更新角色关系"""
        if character_name not in self.relationships:
            self.relationships[character_name] = []
        
        # 检查是否已存在关系
        existing = self.get_relationship(character_name, target_character)
        if existing:
            existing.relationship_type = relationship_type
            existing.intimacy_level = intimacy_level
            existing.description = description
        else:
            relationship = CharacterRelationship(
                target_character=target_character,
                relationship_type=relationship_type,
                intimacy_level=intimacy_level,
                description=description,
                first_met_chapter=first_met_chapter
            )
            self.relationships[character_name].append(relationship)
    
    def update_relationship(
        self,
        character_name: str,
        target_character: str,
        new_type: str = None,
        intimacy_change: int = 0,
        description: str = None,
        reason: str = "",
        chapter: int = None
    ):
        """更新关系状态"""
        relationship = self.get_relationship(character_name, target_character)
        if relationship:
            # 如果提供了新的描述，更新描述
            if description:
                relationship.description = description
            relationship.update(new_type, intimacy_change, reason, chapter)
    
    def get_relationship(
        self,
        character_name: str,
        target_character: str
    ) -> Optional[CharacterRelationship]:
        """获取指定关系"""
        if character_name not in self.relationships:
            return None
        
        for rel in self.relationships[character_name]:
            if rel.target_character == target_character:
                return rel
        return None
    
    def get_all_relationships(self, character_name: str) -> List[CharacterRelationship]:
        """获取角色所有关系"""
        return self.relationships.get(character_name, [])
    
    def get_relationship_network(self) -> Dict[str, List[Dict]]:
        """获取完整关系网络（用于可视化）"""
        network = {}
        for char_name, relationships in self.relationships.items():
            network[char_name] = [
                {
                    'target': rel.target_character,
                    'type': rel.relationship_type,
                    'intimacy': rel.intimacy_level,
                    'description': rel.description
                }
                for rel in relationships
            ]
        return network
    
    # ========== 性格管理 ==========
    
    def set_personality_traits(
        self,
        character_name: str,
        traits: List[Dict[str, any]]
    ):
        """设置角色性格特质"""
        self.personality_traits[character_name] = [
            PersonalityTrait(**trait) for trait in traits
        ]
    
    def update_personality_trait(
        self,
        character_name: str,
        trait_name: str,
        new_intensity: int,
        reason: str = "",
        chapter_number: int = None
    ):
        """更新性格特质强度"""
        if character_name not in self.personality_traits:
            return
        
        for trait in self.personality_traits[character_name]:
            if trait.trait_name == trait_name:
                old_intensity = trait.intensity
                trait.intensity = max(0, min(100, new_intensity))
                
                # 记录演变
                if character_name not in self.personality_evolution:
                    self.personality_evolution[character_name] = []
                
                evolution = PersonalityEvolution(
                    chapter_number=chapter_number or 0,
                    trait_name=trait_name,
                    old_intensity=old_intensity,
                    new_intensity=trait.intensity,
                    reason=reason
                )
                self.personality_evolution[character_name].append(evolution)
                break
    
    def get_personality_traits(self, character_name: str) -> List[PersonalityTrait]:
        """获取角色性格特质"""
        return self.personality_traits.get(character_name, [])
    
    def get_personality_evolution(self, character_name: str) -> List[PersonalityEvolution]:
        """获取性格演变历史"""
        return self.personality_evolution.get(character_name, [])
    
    # ========== 分析功能 ==========
    
    def analyze_character_growth(self, character_name: str) -> Dict:
        """分析角色成长轨迹"""
        experiences = self.get_character_experiences(character_name)
        personality_changes = self.get_personality_evolution(character_name)
        
        return {
            'total_experiences': len(experiences),
            'experience_breakdown': {
                event_type: len([e for e in experiences if e.event_type == event_type])
                for event_type in set(e.event_type for e in experiences)
            },
            'positive_events': len([e for e in experiences if e.impact == 'positive']),
            'negative_events': len([e for e in experiences if e.impact == 'negative']),
            'personality_changes': len(personality_changes),
            'most_changed_trait': self._get_most_changed_trait(personality_changes)
        }
    
    def _get_most_changed_trait(self, evolutions: List[PersonalityEvolution]) -> Optional[str]:
        """获取变化最大的性格特质"""
        if not evolutions:
            return None
        
        trait_changes = {}
        for evo in evolutions:
            if evo.trait_name not in trait_changes:
                trait_changes[evo.trait_name] = 0
            trait_changes[evo.trait_name] += abs(evo.new_intensity - evo.old_intensity)
        
        return max(trait_changes.items(), key=lambda x: x[1])[0] if trait_changes else None
    
    def get_character_timeline(self, character_name: str) -> List[Dict]:
        """获取角色完整时间线"""
        timeline = []
        
        # 添加经历
        for exp in self.get_character_experiences(character_name):
            timeline.append({
                'chapter': exp.chapter_number,
                'type': 'experience',
                'event_type': exp.event_type,
                'content': exp.description,
                'impact': exp.impact,
                'timestamp': exp.timestamp
            })
        
        # 添加关系变化
        for rel in self.get_all_relationships(character_name):
            for change in rel.evolution_history:
                timeline.append({
                    'chapter': change['chapter'],
                    'type': 'relationship',
                    'content': f"与{rel.target_character}的关系：{change['old_type']} → {change['new_type']}",
                    'reason': change['reason'],
                    'timestamp': change['timestamp']
                })
        
        # 添加性格变化
        for evo in self.get_personality_evolution(character_name):
            timeline.append({
                'chapter': evo.chapter_number,
                'type': 'personality',
                'trait': evo.trait_name,
                'content': f"{evo.trait_name}：{evo.old_intensity} → {evo.new_intensity}",
                'reason': evo.reason,
                'timestamp': evo.timestamp
            })
        
        # 按时间排序
        return sorted(timeline, key=lambda x: (x.get('chapter', 0), x['timestamp']))
    
    # ========== 角色合并 ==========
    
    def merge_character_data(self, source_name: str, target_name: str):
        """
        合并角色数据（将source_name的所有数据合并到target_name）
        
        Args:
            source_name: 源角色名（要被合并的）
            target_name: 目标角色名（保留的）
        """
        # 合并经历
        if source_name in self.experiences:
            if target_name not in self.experiences:
                self.experiences[target_name] = []
            self.experiences[target_name].extend(self.experiences[source_name])
            # 按章节号排序
            self.experiences[target_name].sort(key=lambda x: x.chapter_number)
            del self.experiences[source_name]
        
        # 合并关系
        if source_name in self.relationships:
            if target_name not in self.relationships:
                self.relationships[target_name] = []
            
            # 合并关系，避免重复
            existing_targets = {rel.target_character for rel in self.relationships[target_name]}
            for rel in self.relationships[source_name]:
                if rel.target_character not in existing_targets:
                    self.relationships[target_name].append(rel)
            
            del self.relationships[source_name]
        
        # 更新其他角色对此角色的关系引用
        for char_name, rels in self.relationships.items():
            for rel in rels:
                if rel.target_character == source_name:
                    rel.target_character = target_name
        
        # 更新经历中的相关角色引用
        for char_name, exps in self.experiences.items():
            for exp in exps:
                if source_name in exp.related_characters:
                    exp.related_characters.remove(source_name)
                    if target_name not in exp.related_characters:
                        exp.related_characters.append(target_name)
        
        # 合并性格特质
        if source_name in self.personality_traits:
            if target_name not in self.personality_traits:
                self.personality_traits[target_name] = []
            
            # 合并特质，避免重复
            existing_traits = {trait.trait_name for trait in self.personality_traits[target_name]}
            for trait in self.personality_traits[source_name]:
                if trait.trait_name not in existing_traits:
                    self.personality_traits[target_name].append(trait)
            
            del self.personality_traits[source_name]
        
        # 合并性格演变
        if source_name in self.personality_evolution:
            if target_name not in self.personality_evolution:
                self.personality_evolution[target_name] = []
            self.personality_evolution[target_name].extend(self.personality_evolution[source_name])
            # 按章节号排序
            self.personality_evolution[target_name].sort(key=lambda x: x.chapter_number)
            del self.personality_evolution[source_name]
    
    def rename_character(self, old_name: str, new_name: str):
        """
        重命名角色（在所有追踪数据中更新角色名）
        
        Args:
            old_name: 旧名字
            new_name: 新名字
        """
        # 这个方法与merge_character_data类似，但是简单的重命名
        if old_name == new_name:
            return
        
        # 重命名经历
        if old_name in self.experiences:
            self.experiences[new_name] = self.experiences[old_name]
            del self.experiences[old_name]
        
        # 重命名关系
        if old_name in self.relationships:
            self.relationships[new_name] = self.relationships[old_name]
            del self.relationships[old_name]
        
        # 更新关系引用
        for char_name, rels in self.relationships.items():
            for rel in rels:
                if rel.target_character == old_name:
                    rel.target_character = new_name
        
        # 更新经历中的相关角色引用
        for char_name, exps in self.experiences.items():
            for exp in exps:
                if old_name in exp.related_characters:
                    idx = exp.related_characters.index(old_name)
                    exp.related_characters[idx] = new_name
        
        # 重命名性格特质
        if old_name in self.personality_traits:
            self.personality_traits[new_name] = self.personality_traits[old_name]
            del self.personality_traits[old_name]
        
        # 重命名性格演变
        if old_name in self.personality_evolution:
            self.personality_evolution[new_name] = self.personality_evolution[old_name]
            del self.personality_evolution[old_name]
    
    # ========== 序列化 ==========
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'experiences': {
                char: [exp.to_dict() for exp in exps]
                for char, exps in self.experiences.items()
            },
            'relationships': {
                char: [rel.to_dict() for rel in rels]
                for char, rels in self.relationships.items()
            },
            'personality_traits': {
                char: [trait.to_dict() for trait in traits]
                for char, traits in self.personality_traits.items()
            },
            'personality_evolution': {
                char: [evo.to_dict() for evo in evos]
                for char, evos in self.personality_evolution.items()
            }
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'CharacterTracker':
        """从字典创建"""
        tracker = CharacterTracker()
        
        if 'experiences' in data:
            tracker.experiences = {
                char: [CharacterExperience.from_dict(exp) for exp in exps]
                for char, exps in data['experiences'].items()
            }
        
        if 'relationships' in data:
            tracker.relationships = {
                char: [CharacterRelationship.from_dict(rel) for rel in rels]
                for char, rels in data['relationships'].items()
            }
        
        if 'personality_traits' in data:
            tracker.personality_traits = {
                char: [PersonalityTrait.from_dict(trait) for trait in traits]
                for char, traits in data['personality_traits'].items()
            }
        
        if 'personality_evolution' in data:
            tracker.personality_evolution = {
                char: [PersonalityEvolution.from_dict(evo) for evo in evos]
                for char, evos in data['personality_evolution'].items()
            }
        
        return tracker
