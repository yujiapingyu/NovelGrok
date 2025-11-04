# NovelGrok - AI小说写作工具

一个基于Python和Grok API的智能小说写作工具。

## 🎯 核心特性

- 📚 **智能上下文管理**: 分层上下文架构，解决token限制问题
- 👥 **角色一致性跟踪**: 维护角色信息、性格特征和关系网络
- 📖 **情节连贯管理**: 跟踪故事线索和重要事件，保持逻辑一致
- 🧠 **自动摘要生成**: 为长章节生成摘要，优化上下文使用
- 📝 **多种写作模式**: 新章节生成、续写、改进等多种模式
- 💾 **完整项目管理**: 项目保存、加载、导出等完整功能
- 🌐 **Web可视化界面**: 美观易用的Web界面，所见即所得

## 🧠 上下文问题解决方案

### 传统AI写作的问题
- **Token窗口限制**: 无法处理长篇小说的完整上下文
- **信息遗忘**: 角色设定和早期情节容易被遗忘
- **一致性缺失**: 角色性格、故事逻辑出现矛盾

### 我们的创新解决方案

#### 1. 分层上下文架构
```
上下文分配策略:
├── 基础信息 (30%) ── 角色设定、故事背景、大纲
├── 近期内容 (50%) ── 最近2-3章的完整文本  
└── 历史摘要 (20%) ── 早期章节的关键信息
```

#### 2. 智能Token优化
- **动态内容选择**: 根据当前写作需要选择最相关的历史内容
- **自动摘要压缩**: 将冗长章节压缩为关键信息点
- **Token预算管理**: 智能分配token使用，最大化有效信息密度

## 📦 快速开始

### 安装依赖

```bash
# 虚拟环境已创建（venv/）
# 依赖已安装（openai, python-dotenv）
```

### 配置API

1. 复制 `.env.example` 到 `.env`
2. 在 `.env` 中设置你的Grok API密钥：
```env
XAI_API_KEY=your_grok_api_key_here
XAI_BASE_URL=https://api.x.ai/v1
```

## 🚀 使用方法

### 🌐 Web界面（推荐）

```bash
# 启动Web服务器
python web_api.py

# 在浏览器中访问
http://localhost:5001
```

**Web界面功能**：
- ✅ 创建和管理项目
- ✅ 添加和编辑角色
- ✅ 查看角色经历
- ✅ 手动添加和编辑章节
- ✅ AI生成新章节
- ✅ 获取情节建议
- ✅ 实时统计数据可视化
- ✅ 美观的现代化界面
- ✅ **📥 小说导入功能** - 支持导入现有小说并自动提取角色
- ✅ **🤖 AI一键分析** - 自动分析小说类型、背景设定和故事大纲（新功能）

### 📥 小说导入功能（新功能）

**功能说明**：
NovelGrok现在支持导入已有的小说文本，自动切分章节并提取角色信息。

**支持的章节格式**：
- `第一章：标题` / `第1章 标题`
- `第一回：标题` / `第1回 标题`  
- `Chapter 1: Title` / `CHAPTER 1: Title`
- `1. 标题` / `1、标题`
- `【第一章】标题`

**使用方法**：

1. **通过Web界面导入**：
   - 点击"📥 导入小说"按钮
   - 输入项目名称
   - 粘贴小说文本（或从文件加载）
   - 点击"👁️ 预览"查看切分结果
   - 确认后点击"✅ 确认导入"

2. **文件大小限制**：
   - 最大支持1MB的文本文件
   - 约100万字符（中文约30-40万字）
   - 实时显示文件大小和字符数

4. **自动功能**：
   - ✅ 智能识别章节标题格式
   - ✅ 自动切分章节内容
   - ✅ 统计字数和章节数
   - ✅ **AI自动提取主要角色**（可选）
   - ✅ 分析角色描述、性格、关系
   - ✅ **智能新角色检测**（增强功能）
     * 先分析全文前10万字提取初始角色
     * 逐章检测后续章节的新登场角色
     * 确保不遗漏任何重要角色
   - ✅ **自动分析角色经历追踪**（可选）
     * 逐章分析角色经历和重要事件
     * 追踪角色关系的演变
     * 记录性格特质的变化轨迹
   - ✅ 导入章节与生成章节可视化区分

4. **导入后**：
   - 章节显示📥导入标记
   - 可继续使用AI生成后续章节
   - 角色信息自动填充到角色列表
   - 支持编辑和修改导入的内容

**代码示例**：

```python
from novel_ai.utils.novel_importer import NovelImporter
from novel_ai.api.grok_client import GrokClient

# 创建导入器
importer = NovelImporter(max_file_size=1024*1024)  # 1MB

# 导入小说
with open('my_novel.txt', 'r', encoding='utf-8') as f:
    content = f.read()

success, chapters, error = importer.import_novel(content)

if success:
    print(f"成功导入 {len(chapters)} 章")
    
    # 提取角色
    client = GrokClient()
    characters = client.extract_characters_from_novel(content)
    print(f"提取到 {len(characters)} 个角色")
else:
    print(f"导入失败: {error}")
```

**技术特点**：
- 正则表达式模式匹配，支持多种章节格式
- 智能模式检测，自动选择最匹配的格式
- Grok AI驱动的角色提取，准确识别主要角色
- 后台异步处理，不阻塞界面操作
- 完整的错误处理和用户提示

### 🤖 AI一键分析功能（新功能）

**功能说明**：
在项目概览页面，点击"🤖 AI一键分析"按钮，系统会自动分析已有的章节内容，智能生成项目的类型、背景设定和故事大纲。

**适用场景**：
- 导入小说后快速生成项目信息
- 已写作多章但未填写项目设定
- 想要客观的AI视角总结作品

**分析内容**：
1. **小说类型** - 自动识别类型（科幻、奇幻、悬疑、都市等）
2. **背景设定** - 总结世界观、时代、地点等关键设定
3. **故事大纲** - 概括主要情节、主角目标、主要冲突

**使用方法**：
```
1. 打开项目 → 切换到"📊 概览"标签
2. 点击"🤖 AI一键分析"按钮
3. 确认分析（会覆盖现有的项目信息）
4. 等待AI处理（通常20-60秒）
5. 查看自动生成的类型、背景和大纲
```

**代码示例**：
```python
from novel_ai.api.grok_client import GrokClient
from novel_ai.core.project import NovelProject

# 加载项目
project = NovelProject.load("我的小说")

# AI分析
client = GrokClient()
analysis = client.analyze_project_info(project)

print(f"类型: {analysis['genre']}")
print(f"背景: {analysis['background']}")
print(f"大纲: {analysis['plot_outline']}")

# 更新项目
project.genre = analysis['genre']
project.background = analysis['background']
project.plot_outline = analysis['plot_outline']
project.save()
```

**注意事项**：
- 需要项目中至少有一个章节
- 会分析前50000字符的内容
- 生成的内容会覆盖现有的项目类型、背景和大纲
- 建议在导入小说后使用此功能
```

## 📄 许可证

MIT License
