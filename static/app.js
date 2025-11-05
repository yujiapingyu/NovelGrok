// NovelGrok Web应用 - JavaScript逻辑

// 全局状态
let currentProject = null;
let projects = [];
let isGenerating = false; // 防止重复请求
let generationPollingTimer = null; // 轮询定时器
let currentCharacterTracking = null; // 当前查看的角色追踪数据

// API基础URL
const API_BASE = '';

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    checkAPIStatus();
});

// ========== 工具函数 ==========

function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '<div class="loading active"><div class="spinner"></div><p style="margin-top: 10px;">加载中...</p></div>';
    }
}

function showAlert(message, type = 'success') {
    let alertClass = 'alert-success';
    if (type === 'error') alertClass = 'alert-error';
    else if (type === 'warning') alertClass = 'alert-warning';
    else if (type === 'info') alertClass = 'alert-info';
    
    const alertHtml = `<div class="alert ${alertClass}">${message}</div>`;
    
    // 在当前活动的标签页显示提示
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        const existingAlert = activeTab.querySelector('.alert');
        if (existingAlert) existingAlert.remove();
        
        activeTab.insertAdjacentHTML('afterbegin', alertHtml);
        
        setTimeout(() => {
            const alert = activeTab.querySelector('.alert');
            if (alert) alert.remove();
        }, 5000);
    }
}

function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('zh-CN');
}

function formatWordCount(count) {
    if (count < 1000) return `${count}字`;
    if (count < 20000) return `${(count/1000).toFixed(1)}千字`;
    return `${(count/20000).toFixed(1)}万字`;
}

// ========== 进度提示 ==========

let progressModalElement = null;

function createProgressModal(taskName, wordCount, customMessage = '') {
    // 如果已有进度提示，先关闭
    if (progressModalElement) {
        closeProgressModal();
    }
    
    const estimatedTime = estimateGenerationTime(wordCount);
    const message = customMessage || `正在生成约${wordCount}字的内容，预计需要${estimatedTime}...`;
    
    // 使用非阻塞的浮动通知，而不是全屏模态框
    const toastHtml = `
        <div id="progressModal" style="
            position: fixed;
            top: 80px;
            right: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            padding: 20px;
            z-index: 9999;
            min-width: 320px;
            max-width: 400px;
            border-left: 4px solid #667eea;
            animation: slideInRight 0.3s ease;
        ">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <div class="loading active" style="flex-shrink: 0;">
                    <div class="spinner" style="width: 24px; height: 24px;"></div>
                </div>
                <div style="flex: 1;">
                    <h3 style="color: #667eea; margin: 0 0 8px 0; font-size: 16px;">⏳ ${taskName}</h3>
                    <p style="margin: 0 0 8px 0; color: #666; font-size: 14px; line-height: 1.5;">
                        ${message}
                    </p>
                    <div id="progressTimer" style="font-size: 13px; color: #999;">
                        已用时: 0秒
                    </div>
                </div>
                <button onclick="minimizeProgress()" style="
                    background: none;
                    border: none;
                    color: #999;
                    cursor: pointer;
                    font-size: 18px;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    flex-shrink: 0;
                " title="最小化">−</button>
            </div>
            <div style="margin-top: 12px; padding: 10px; background: #f0f4ff; border-radius: 6px; font-size: 12px; color: #5a67d8;">
                💡 提示：生成期间可以自由切换标签页
            </div>
        </div>
        <style>
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        </style>
    `;
    
    document.body.insertAdjacentHTML('beforeend', toastHtml);
    progressModalElement = document.getElementById('progressModal');
    
    // 启动计时器
    let seconds = 0;
    const timerId = setInterval(() => {
        seconds++;
        const timerElement = document.getElementById('progressTimer');
        if (timerElement) {
            timerElement.textContent = `已用时: ${seconds}秒`;
        } else {
            clearInterval(timerId);
        }
    }, 1000);
    
    // 保存计时器ID以便清除
    progressModalElement.timerId = timerId;
    
    return progressModalElement;
}

function minimizeProgress() {
    if (progressModalElement) {
        // 最小化为小图标
        progressModalElement.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: #667eea;
            color: white;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
            cursor: pointer;
            z-index: 9999;
            animation: pulse 2s infinite;
        `;
        progressModalElement.innerHTML = `
            <div class="loading active" style="margin: 0;">
                <div class="spinner" style="width: 24px; height: 24px; border-color: white white transparent transparent;"></div>
            </div>
            <style>
                @keyframes pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }
            </style>
        `;
        progressModalElement.onclick = () => {
            closeProgressModal();
            showAlert('生成任务正在后台运行中，请稍候...', 'info');
        };
    }
}

function closeProgressModal() {
    if (progressModalElement) {
        // 清除计时器
        if (progressModalElement.timerId) {
            clearInterval(progressModalElement.timerId);
        }
        progressModalElement.remove();
        progressModalElement = null;
    }
}

// ========== 章节生成状态轮询 ==========

async function startGenerationPolling(projectTitle) {
    // 清除之前的轮询
    if (generationPollingTimer) {
        clearInterval(generationPollingTimer);
    }
    
    // 每2秒轮询一次
    generationPollingTimer = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectTitle)}/generation-status`);
            const result = await response.json();
            
            if (result.success && result.data) {
                const status = result.data.status;
                const message = result.data.message;
                const progress = result.data.progress || 0;
                
                // 更新进度显示
                if (progressModalElement) {
                    const messageEl = progressModalElement.querySelector('.toast-message');
                    if (messageEl) {
                        messageEl.textContent = message || '正在生成...';
                    }
                }
                
                // 如果完成或出错，停止轮询
                if (status === 'completed') {
                    stopGenerationPolling();
                    closeProgressModal();
                    isGenerating = false;
                    
                    // 刷新项目列表（左侧边栏的项目信息）
                    await loadProjects();
                    
                    // 刷新当前项目详情
                    await selectProject(projectTitle);
                    
                    // 🔄 刷新大纲列表（如果在大纲模式）
                    if (currentOutlines && currentOutlines.length > 0) {
                        await loadOutlines();
                    }
                    
                    // 检查是否有新角色
                    const newCharacters = result.data.new_characters;
                    if (newCharacters && newCharacters.length > 0) {
                        // 显示新角色确认对话框
                        showNewCharactersDialog(newCharacters, projectTitle);
                        // 切换到章节标签（新角色对话框会在上层显示）
                        switchTab('chapters');
                    } else {
                        // 显示成功消息
                        showAlert('章节生成完成！📝', 'success');
                        // 切换到章节标签
                        switchTab('chapters');
                    }
                    
                } else if (status === 'error') {
                    stopGenerationPolling();
                    closeProgressModal();
                    isGenerating = false;
                    showAlert('生成失败: ' + message, 'error');
                }
            }
        } catch (error) {
            console.error('轮询状态失败:', error);
        }
    }, 2000); // 每2秒轮询一次
}

function stopGenerationPolling() {
    if (generationPollingTimer) {
        clearInterval(generationPollingTimer);
        generationPollingTimer = null;
    }
}

function estimateGenerationTime(wordCount) {
    if (wordCount <= 1000) return '30秒-1分钟';
    if (wordCount <= 2000) return '1-2分钟';
    if (wordCount <= 3000) return '2-3分钟';
    if (wordCount <= 4000) return '3-4分钟';
    return '4-5分钟';
}

// ========== API调用 ==========

async function apiCall(url, options = {}) {
    try {
        const response = await fetch(API_BASE + url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || '操作失败');
        }
        
        return data;
    } catch (error) {
        console.error('API调用失败:', error);
        throw error;
    }
}

async function checkAPIStatus() {
    try {
        const result = await apiCall('/api/health');
        if (!result.data.api_configured) {
            console.warn('API密钥未配置，AI功能将不可用');
        }
        
        // 加载API余额信息
        loadAPIBalance();
    } catch (error) {
        console.error('健康检查失败:', error);
    }
}

async function loadAPIBalance() {
    const balanceInfo = document.getElementById('balanceInfo');
    try {
        const result = await apiCall('/api/balance');
        if (result.success && result.data) {
            const data = result.data;
            if (data.available) {
                balanceInfo.innerHTML = `✅ ${data.message} (${data.model})`;
                balanceInfo.style.color = '#4caf50';
            } else {
                balanceInfo.innerHTML = `❌ ${data.message}`;
                balanceInfo.style.color = '#f44336';
            }
        }
    } catch (error) {
        balanceInfo.innerHTML = `⚠️ 无法获取API状态`;
        balanceInfo.style.color = '#ff9800';
        console.error('获取余额失败:', error);
    }
}

// ========== 项目管理 ==========

async function loadProjects() {
    try {
        showLoading('projectList');
        
        const result = await apiCall('/api/projects');
        projects = result.data;
        
        const projectList = document.getElementById('projectList');
        
        if (projects.length === 0) {
            projectList.innerHTML = '<p style="text-align:center;color:#999;padding:20px;">暂无项目</p>';
            return;
        }
        
        projectList.innerHTML = projects.map(project => `
            <div class="project-item" onclick="selectProject('${project.title}')">
                <h3>${project.title}</h3>
                <div class="meta">
                    ${project.genre || '未分类'} · ${project.chapter_count}章 · ${formatWordCount(project.total_words)}
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        document.getElementById('projectList').innerHTML = 
            '<p style="color:#dc3545;padding:20px;">加载失败</p>';
        console.error('加载项目失败:', error);
    }
}

async function selectProject(title) {
    try {
        const result = await apiCall(`/api/projects/${encodeURIComponent(title)}`);
        currentProject = result.data;
        
        // 更新UI
        document.querySelectorAll('.project-item').forEach(item => {
            item.classList.remove('active');
            if (item.textContent.includes(title)) {
                item.classList.add('active');
            }
        });
        
        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('projectContent').style.display = 'block';
        
        // 刷新各个标签页
        updateOverviewTab();
        updateCharactersTab();
        updateChaptersTab();
        updateCharacterTrackingSelect();
        
    } catch (error) {
        showAlert('加载项目失败: ' + error.message, 'error');
    }
}

function showCreateProjectModal() {
    document.getElementById('newProjectTitle').value = '';
    document.getElementById('newProjectGenre').value = '';
    document.getElementById('newProjectBackground').value = '';
    document.getElementById('newProjectOutline').value = '';
    showModal('createProjectModal');
}

async function createProject() {
    const title = document.getElementById('newProjectTitle').value.trim();
    const genre = document.getElementById('newProjectGenre').value.trim();
    const background = document.getElementById('newProjectBackground').value.trim();
    const plot_outline = document.getElementById('newProjectOutline').value.trim();
    
    if (!title) {
        alert('请输入项目标题');
        return;
    }
    
    try {
        await apiCall('/api/projects', {
            method: 'POST',
            body: JSON.stringify({ title, genre, background, plot_outline })
        });
        
        closeModal('createProjectModal');
        showAlert('项目创建成功！');
        await loadProjects();
        await selectProject(title);
        
    } catch (error) {
        alert('创建失败: ' + error.message);
    }
}

function showEditProjectModal() {
    if (!currentProject) return;
    
    document.getElementById('editProjectGenre').value = currentProject.genre || '';
    document.getElementById('editProjectBackground').value = currentProject.background || '';
    document.getElementById('editProjectOutline').value = currentProject.plot_outline || '';
    document.getElementById('editProjectStyle').value = currentProject.writing_style || '';
    
    showModal('editProjectModal');
}

async function updateProject() {
    if (!currentProject) return;
    
    const data = {
        genre: document.getElementById('editProjectGenre').value.trim(),
        background: document.getElementById('editProjectBackground').value.trim(),
        plot_outline: document.getElementById('editProjectOutline').value.trim(),
        writing_style: document.getElementById('editProjectStyle').value.trim()
    };
    
    try {
        await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        
        closeModal('editProjectModal');
        showAlert('项目更新成功！');
        await selectProject(currentProject.title);
        
    } catch (error) {
        alert('更新失败: ' + error.message);
    }
}

async function deleteProject() {
    if (!currentProject) return;
    
    if (!confirm(`确定要删除项目"${currentProject.title}"吗？此操作不可恢复！`)) {
        return;
    }
    
    try {
        await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}`, {
            method: 'DELETE'
        });
        
        showAlert('项目已删除');
        currentProject = null;
        document.getElementById('projectContent').style.display = 'none';
        document.getElementById('emptyState').style.display = 'block';
        await loadProjects();
        
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

async function analyzeProjectWithAI() {
    if (!currentProject) return;
    
    // 检查是否有章节 - 使用多种方式判断
    const hasChapters = currentProject.chapters && currentProject.chapters.length > 0;
    const chapterCount = currentProject.chapter_count || (currentProject.chapters ? currentProject.chapters.length : 0);
    
    if (!hasChapters && chapterCount === 0) {
        alert('项目中没有章节，无法进行AI分析。\n请先添加章节或导入小说。');
        return;
    }
    
    if (!confirm('AI将分析当前小说的所有章节内容，自动生成：\n• 小说类型\n• 背景设定\n• 故事大纲\n\n这将覆盖现有的项目信息，是否继续？')) {
        return;
    }
    
    // 显示进度提示
    const progressModal = createProgressModal('AI分析项目', 0, '正在分析小说内容，生成类型、背景和大纲...');
    
    try {
        const response = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/analyze`, {
            method: 'POST'
        });
        
        closeProgressModal();
        
        // 显示分析结果
        const data = response.data;
        const resultMessage = `✅ AI分析完成！\n\n` +
            `📚 类型：${data.genre}\n\n` +
            `🌍 背景：${data.background}\n\n` +
            `📖 大纲：${data.plot_outline.substring(0, 100)}...\n\n` +
            `⏱️ 用时：${data.elapsed_time}`;
        
        alert(resultMessage);
        
        // 重新加载项目信息
        await selectProject(currentProject.title);
        
    } catch (error) {
        closeProgressModal();
        alert('AI分析失败: ' + error.message);
    }
}

// ========== 小说导入 ==========

function showImportNovelModal() {
    // 清空输入
    document.getElementById('importProjectTitle').value = '';
    document.getElementById('importNovelContent').value = '';
    document.getElementById('importExtractCharacters').checked = true;
    document.getElementById('importPreview').style.display = 'none';
    document.getElementById('previewImportBtn').style.display = 'inline-block';
    document.getElementById('confirmImportBtn').style.display = 'none';
    updateImportContentSize();
    updateTrackingDisplay(); // 更新追踪选项显示
    
    showModal('importNovelModal');
}

function updateTrackingDisplay() {
    const checkbox = document.getElementById('importExtractCharacters');
    const optionalFeature = document.getElementById('trackingOptionalFeature');
    const card = document.getElementById('trackingOptionCard');
    
    if (checkbox.checked) {
        // 开启状态：显示完整功能，紫色渐变背景
        optionalFeature.style.opacity = '1';
        optionalFeature.innerHTML = `
            <span style="color: #667eea; margin-right: 6px; font-weight: 600;">✓</span>
            <small style="color: #34495e; font-weight: 500;">逐章追踪：角色经历、关系变化、性格发展</small>
            <small style="color: #e74c3c; margin-left: 6px; font-style: italic;">（需要较长时间）</small>
        `;
        card.style.background = 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)';
        card.style.borderColor = '#e1e8ed';
    } else {
        // 关闭状态：显示禁用的功能，灰色背景
        optionalFeature.style.opacity = '0.5';
        optionalFeature.innerHTML = `
            <span style="color: #95a5a6; margin-right: 6px; font-weight: 600;">✗</span>
            <small style="color: #7f8c8d; font-weight: 500; text-decoration: line-through;">逐章追踪：角色经历、关系变化、性格发展</small>
            <small style="color: #95a5a6; margin-left: 6px; font-style: italic;">（已跳过）</small>
        `;
        card.style.background = 'linear-gradient(135deg, #ecf0f1 0%, #bdc3c7 100%)';
        card.style.borderColor = '#95a5a6';
    }
}

function updateImportContentSize() {
    const content = document.getElementById('importNovelContent').value;
    const sizeElement = document.getElementById('importContentSize');
    
    const charCount = content.length;
    const byteSize = new Blob([content]).size;
    const kbSize = (byteSize / 1024).toFixed(2);
    const mbSize = (byteSize / (1024 * 1024)).toFixed(2);
    
    let sizeText;
    let colorStyle = '';
    
    if (byteSize > 1024 * 1024) {
        sizeText = `${charCount} 字符 (${mbSize} MB)`;
        colorStyle = 'color: #667eea;';  // 紫色，表示大文件但不限制
    } else {
        sizeText = `${charCount} 字符 (${kbSize} KB)`;
    }
    
    sizeElement.innerHTML = sizeText;
    sizeElement.style = colorStyle;
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        document.getElementById('importNovelContent').value = e.target.result;
        updateImportContentSize();
    };
    reader.readAsText(file, 'UTF-8');
}

async function previewImport() {
    const projectTitle = document.getElementById('importProjectTitle').value.trim();
    const content = document.getElementById('importNovelContent').value.trim();
    
    if (!projectTitle) {
        alert('请输入项目名称');
        return;
    }
    
    if (!content) {
        alert('请输入小说内容');
        return;
    }
    
    // 显示加载状态
    const previewBtn = document.getElementById('previewImportBtn');
    const originalText = previewBtn.textContent;
    previewBtn.disabled = true;
    previewBtn.textContent = '分析中...';
    
    try {
        // 调用API预览（实际上我们在前端简单分析）
        const lines = content.split('\n');
        const chapterPattern = /^(第[0-9零一二三四五六七八九十百千万]+[章回]|Chapter\s+\d+|[0-9]+[、\.])/i;
        
        let chapterCount = 0;
        const chapters = [];
        
        for (let line of lines) {
            const trimmed = line.trim();
            if (trimmed && chapterPattern.test(trimmed)) {
                chapterCount++;
                if (chapters.length < 10) {
                    chapters.push(trimmed);
                }
            }
        }
        
        // 显示预览
        const previewDiv = document.getElementById('importPreview');
        const previewContent = document.getElementById('importPreviewContent');
        
        const wordCount = content.length;
        const avgChapterWords = chapterCount > 0 ? Math.floor(wordCount / chapterCount) : 0;
        
        let previewHtml = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 15px;">
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 1.8em; color: #667eea; font-weight: bold;">${chapterCount}</div>
                    <div style="font-size: 0.9em; color: #666;">检测到章节</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 1.8em; color: #667eea; font-weight: bold;">${formatWordCount(wordCount)}</div>
                    <div style="font-size: 0.9em; color: #666;">总字数</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 1.8em; color: #667eea; font-weight: bold;">${formatWordCount(avgChapterWords)}</div>
                    <div style="font-size: 0.9em; color: #666;">平均每章</div>
                </div>
            </div>
        `;
        
        if (chapterCount === 0) {
            previewHtml += `
                <div style="background: #fff3cd; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #ffc107;">
                    ⚠️ 未检测到章节标题，将作为单章导入
                </div>
            `;
        } else if (chapters.length > 0) {
            previewHtml += `
                <div style="margin-top: 10px;">
                    <strong>前${Math.min(chapters.length, 10)}章标题：</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        ${chapters.map(ch => `<li>${ch}</li>`).join('')}
                    </ul>
                    ${chapterCount > 10 ? `<div style="color: #666; font-size: 0.9em;">...还有 ${chapterCount - 10} 章</div>` : ''}
                </div>
            `;
        }
        
        previewContent.innerHTML = previewHtml;
        previewDiv.style.display = 'block';
        
        // 显示确认导入按钮
        document.getElementById('previewImportBtn').style.display = 'none';
        document.getElementById('confirmImportBtn').style.display = 'inline-block';
        
    } catch (error) {
        alert('预览失败: ' + error.message);
    } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = originalText;
    }
}

async function confirmImport() {
    const projectTitle = document.getElementById('importProjectTitle').value.trim();
    const content = document.getElementById('importNovelContent').value.trim();
    const extractCharacters = document.getElementById('importExtractCharacters').checked;
    
    const confirmBtn = document.getElementById('confirmImportBtn');
    const originalText = confirmBtn.textContent;
    confirmBtn.disabled = true;
    confirmBtn.textContent = '导入中...';
    
    try {
        const response = await apiCall(`/api/projects/${encodeURIComponent(projectTitle)}/import-novel`, {
            method: 'POST',
            body: JSON.stringify({
                content: content,
                extract_characters: extractCharacters
            })
        });
        
        closeModal('importNovelModal');
        
        const summary = response.data.summary;
        let message = `成功导入 ${summary.chapter_count} 章，共 ${formatWordCount(summary.total_words)}`;
        
        if (extractCharacters) {
            message += '\n\n🔄 AI正在后台分析：\n';
            message += '  • 提取角色信息\n';
            message += '  • 分析角色经历\n';
            message += '  • 追踪关系变化\n';
            message += '  • 记录性格发展\n\n';
            message += '完成后可在"角色"和"角色追踪"标签页查看详细信息。';
        }
        
        showAlert(message);
        
        // 重新加载项目列表并选中导入的项目
        await loadProjects();
        await selectProject(projectTitle);
        
    } catch (error) {
        alert('导入失败: ' + error.message);
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
    }
}

// 监听内容变化，更新大小显示
document.addEventListener('DOMContentLoaded', () => {
    const contentArea = document.getElementById('importNovelContent');
    if (contentArea) {
        contentArea.addEventListener('input', updateImportContentSize);
    }
});

// ========== 标签页切换 ==========

function switchTab(tabName, event) {
    // 更新标签按钮
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    
    // 如果是通过点击事件触发，高亮对应的标签按钮
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // 如果是通过代码调用，根据 tabName 找到对应的标签按钮
        const tabButton = document.querySelector(`.tab[onclick*="${tabName}"]`);
        if (tabButton) {
            tabButton.classList.add('active');
        }
    }
    
    // 更新内容区域
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');
}

// ========== 概览标签 ==========

function updateOverviewTab() {
    if (!currentProject) return;
    
    const stats = currentProject.status;
    document.getElementById('stats').innerHTML = `
        <div class="stat-card">
            <div class="value">${stats.chapter_count}</div>
            <div class="label">章节数</div>
        </div>
        <div class="stat-card">
            <div class="value">${stats.character_count}</div>
            <div class="label">角色数</div>
        </div>
        <div class="stat-card">
            <div class="value">${formatWordCount(stats.total_words)}</div>
            <div class="label">总字数</div>
        </div>
        <div class="stat-card">
            <div class="value">${currentProject.context_analysis.usage_percent}%</div>
            <div class="label">上下文使用</div>
        </div>
    `;
    
    document.getElementById('projectInfo').innerHTML = `
        <p><strong>标题：</strong>${currentProject.title}</p>
        <p><strong>类型：</strong>${currentProject.genre || '未设置'}</p>
        <p><strong>背景：</strong>${currentProject.background || '未设置'}</p>
        <p><strong>大纲：</strong>${currentProject.plot_outline || '未设置'}</p>
        <p><strong>创建时间：</strong>${formatDate(stats.created_at)}</p>
        <p><strong>更新时间：</strong>${formatDate(stats.updated_at)}</p>
        ${currentProject.chapters.length > 0 ? `
            <div style="margin-top: 20px;">
                <button class="btn" onclick="openReader(1)" style="background: #2196F3;">
                    📖 开始阅读
                </button>
            </div>
        ` : ''}
    `;
}

// ========== 角色管理 ==========

function updateCharactersTab() {
    if (!currentProject) return;
    
    const characters = currentProject.characters;
    const characterList = document.getElementById('characterList');
    
    if (characters.length === 0) {
        characterList.innerHTML = '<div class="empty-state"><p>还没有添加角色</p></div>';
        return;
    }
    
    characterList.innerHTML = characters.map(char => {
        // 生成别名标签HTML
        let aliasesHtml = '';
        if (char.aliases && char.aliases.length > 0) {
            aliasesHtml = `
                <p><strong>别名：</strong>
                    <span class="aliases-container">
                        ${char.aliases.map(alias => `<span class="alias-tag">${alias}</span>`).join('')}
                    </span>
                </p>`;
        }
        
        return `
            <div class="card character-card">
                <div class="card-actions">
                    <button class="icon-btn" onclick="editCharacter('${char.name}')" title="编辑">✏️</button>
                    <button class="icon-btn" onclick="deleteCharacter('${char.name}')" title="删除">🗑️</button>
                </div>
                <h3>👤 ${char.name}</h3>
                ${aliasesHtml}
                <p><strong>描述：</strong>${char.description}</p>
                ${char.personality ? `<p><strong>性格：</strong>${char.personality}</p>` : ''}
                ${char.background ? `<p><strong>背景：</strong>${char.background}</p>` : ''}
            </div>
        `;
    }).join('');
}

function showAddCharacterModal() {
    document.getElementById('newCharName').value = '';
    document.getElementById('newCharDesc').value = '';
    document.getElementById('newCharPersonality').value = '';
    document.getElementById('newCharBackground').value = '';
    showModal('addCharacterModal');
}

async function addCharacter() {
    if (!currentProject) return;
    
    const data = {
        name: document.getElementById('newCharName').value.trim(),
        description: document.getElementById('newCharDesc').value.trim(),
        personality: document.getElementById('newCharPersonality').value.trim(),
        background: document.getElementById('newCharBackground').value.trim()
    };
    
    if (!data.name || !data.description) {
        alert('请填写角色名称和描述');
        return;
    }
    
    try {
        await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/characters`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        closeModal('addCharacterModal');
        showAlert('角色添加成功！');
        
        // 重新加载项目数据并切换到角色标签
        await selectProject(currentProject.title);
        switchTab('characters');
        
    } catch (error) {
        alert('添加失败: ' + error.message);
    }
}

function editCharacter(name) {
    if (!currentProject) return;
    
    const character = currentProject.characters.find(c => c.name === name);
    if (!character) return;
    
    document.getElementById('editCharName').value = character.name;
    document.getElementById('editCharDesc').value = character.description;
    document.getElementById('editCharPersonality').value = character.personality || '';
    document.getElementById('editCharBackground').value = character.background || '';
    
    showModal('editCharacterModal');
}

async function updateCharacter() {
    if (!currentProject) return;
    
    const oldName = document.getElementById('editCharName').value.trim();
    const data = {
        description: document.getElementById('editCharDesc').value.trim(),
        personality: document.getElementById('editCharPersonality').value.trim(),
        background: document.getElementById('editCharBackground').value.trim()
    };
    
    if (!data.description) {
        alert('请填写角色描述');
        return;
    }
    
    try {
        await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/characters/${encodeURIComponent(oldName)}`,
            {
                method: 'PUT',
                body: JSON.stringify(data)
            }
        );
        
        closeModal('editCharacterModal');
        showAlert('角色更新成功！');
        
        // 重新加载项目数据并切换到角色标签
        await selectProject(currentProject.title);
        switchTab('characters');
        
    } catch (error) {
        alert('更新失败: ' + error.message);
    }
}

async function deleteCharacter(name) {
    if (!confirm(`确定要删除角色"${name}"吗？`)) return;
    
    try {
        await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/characters/${encodeURIComponent(name)}`,
            { method: 'DELETE' }
        );
        
        showAlert('角色已删除');
        await selectProject(currentProject.title);
        
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

// ========== 新角色检测 ==========

function showNewCharactersDialog(newCharacters, projectTitle) {
    const charactersHtml = newCharacters.map((char, index) => `
        <div class="card" style="margin-bottom: 15px; padding: 15px;">
            <div style="display: flex; align-items: start; gap: 10px;">
                <input type="checkbox" id="newChar${index}" checked style="margin-top: 5px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0;">👤 ${char.name}</h4>
                    <p style="margin: 5px 0;"><strong>描述：</strong>${char.description}</p>
                    <p style="margin: 5px 0;"><strong>性格：</strong>${char.personality || '未知'}</p>
                </div>
            </div>
        </div>
    `).join('');
    
    const dialogHtml = `
        <div class="modal active" id="newCharactersDialog" style="z-index: 10000;">
            <div class="modal-content" style="max-width: 600px;">
                <span class="close" onclick="closeNewCharactersDialog()">&times;</span>
                <h2>🆕 发现新角色</h2>
                <p style="margin-bottom: 15px; color: #666;">
                    在新章节中检测到以下角色，是否添加到角色列表？
                </p>
                <div style="max-height: 400px; overflow-y: auto;">
                    ${charactersHtml}
                </div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button class="btn" onclick="addSelectedCharacters('${projectTitle}', ${JSON.stringify(newCharacters).replace(/"/g, '&quot;')})">
                        ✅ 添加选中的角色
                    </button>
                    <button class="btn" onclick="closeNewCharactersDialog()" style="background: #999;">
                        跳过
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', dialogHtml);
}

function closeNewCharactersDialog() {
    const dialog = document.getElementById('newCharactersDialog');
    if (dialog) {
        dialog.remove();
    }
    showAlert('章节生成完成！📝', 'success');
}

async function addSelectedCharacters(projectTitle, newCharacters) {
    const selectedChars = [];
    
    newCharacters.forEach((char, index) => {
        const checkbox = document.getElementById(`newChar${index}`);
        if (checkbox && checkbox.checked) {
            selectedChars.push(char);
        }
    });
    
    if (selectedChars.length === 0) {
        closeNewCharactersDialog();
        return;
    }
    
    try {
        // 批量添加角色
        for (const char of selectedChars) {
            await apiCall(`/api/projects/${encodeURIComponent(projectTitle)}/characters`, {
                method: 'POST',
                body: JSON.stringify({
                    name: char.name,
                    description: char.description,
                    personality: char.personality || '',
                    background: ''
                })
            });
        }
        
        closeNewCharactersDialog();
        showAlert(`成功添加 ${selectedChars.length} 个角色！🎉`, 'success');
        
        // 刷新项目并切换到角色标签
        await selectProject(projectTitle);
        switchTab('characters');
        
    } catch (error) {
        alert('添加角色失败: ' + error.message);
    }
}

// ========== 章节管理 ==========

function updateChaptersTab() {
    if (!currentProject) return;
    
    const chapters = currentProject.chapters;
    const chapterList = document.getElementById('chapterList');
    
    if (chapters.length === 0) {
        chapterList.innerHTML = '<div class="empty-state"><p>还没有添加章节</p></div>';
        return;
    }
    
    chapterList.innerHTML = chapters.map(chapter => {
        const isImported = chapter.source === 'imported';
        const sourceBadge = isImported 
            ? '<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.85em; margin-left: 8px;">📥 导入</span>'
            : '<span style="background: #667eea; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.85em; margin-left: 8px;">🤖 生成</span>';
        
        return `
        <div class="card chapter-card" data-chapter="${chapter.chapter_number}">
            <div class="card-actions">
                <button class="icon-btn" onclick="openReader(${chapter.chapter_number})" title="阅读模式">📖</button>
                <button class="icon-btn" onclick="viewChapterModal(${chapter.chapter_number})" title="查看/编辑">👁️</button>
                <button class="icon-btn" onclick="generateChapterSummaryFor(${chapter.chapter_number})" title="生成摘要">📝</button>
                <button class="icon-btn" onclick="analyzeChapterForTracking(${chapter.chapter_number})" title="分析角色动态">🔍</button>
            </div>
            <h3>📖 第${chapter.chapter_number}章：${chapter.title}${sourceBadge}</h3>
            <p><strong>字数：</strong>${chapter.word_count}字 | <strong>创建时间：</strong>${formatDate(chapter.created_at)}</p>
            ${chapter.summary ? `<p><strong>摘要：</strong>${chapter.summary}</p>` : ''}
            <div class="chapter-content" style="max-height: 150px; margin-top: 10px;">
                ${chapter.content}
            </div>
        </div>
        `;
    }).join('');
}

function showAddChapterModal() {
    document.getElementById('newChapterTitle').value = '';
    document.getElementById('newChapterContent').value = '';
    document.getElementById('newChapterSummary').value = '';
    showModal('addChapterModal');
}

async function addChapter() {
    if (!currentProject) return;
    
    const data = {
        title: document.getElementById('newChapterTitle').value.trim(),
        content: document.getElementById('newChapterContent').value.trim(),
        summary: document.getElementById('newChapterSummary').value.trim()
    };
    
    if (!data.title || !data.content) {
        alert('请填写章节标题和内容');
        return;
    }
    
    try {
        await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/chapters`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        closeModal('addChapterModal');
        showAlert('章节添加成功！');
        await selectProject(currentProject.title);
        switchTab('chapters');
        
    } catch (error) {
        alert('添加失败: ' + error.message);
    }
}

let currentEditingChapter = null;

function openReader(chapterNumber) {
    if (!currentProject) return;
    
    // 打开阅读器页面
    const url = `/reader?project=${encodeURIComponent(currentProject.title)}&chapter=${chapterNumber}`;
    window.open(url, '_blank');
}

function viewChapterModal(chapterNumber) {
    const chapter = currentProject.chapters.find(c => c.chapter_number === chapterNumber);
    if (!chapter) return;
    
    currentEditingChapter = chapterNumber;
    document.getElementById('viewChapterTitle').textContent = `第${chapter.chapter_number}章：${chapter.title}`;
    document.getElementById('editChapterContent').value = chapter.content;
    document.getElementById('editChapterSummary').value = chapter.summary || '';
    
    showModal('viewChapterModal');
}

async function updateChapter() {
    if (!currentProject || !currentEditingChapter) return;
    
    const data = {
        content: document.getElementById('editChapterContent').value.trim(),
        summary: document.getElementById('editChapterSummary').value.trim()
    };
    
    try {
        await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/chapters/${currentEditingChapter}`,
            {
                method: 'PUT',
                body: JSON.stringify(data)
            }
        );
        
        closeModal('viewChapterModal');
        showAlert('章节更新成功！');
        await selectProject(currentProject.title);
        
    } catch (error) {
        alert('更新失败: ' + error.message);
    }
}

async function generateChapterSummary() {
    if (!currentProject || !currentEditingChapter) return;
    
    try {
        const summaryTextarea = document.getElementById('editChapterSummary');
        summaryTextarea.value = '生成中...';
        
        const result = await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/chapters/${currentEditingChapter}/summary`,
            { method: 'POST' }
        );
        
        summaryTextarea.value = result.data.summary;
        showAlert('摘要生成成功！');
        
    } catch (error) {
        alert('生成摘要失败: ' + error.message);
        document.getElementById('editChapterSummary').value = '';
    }
}

async function generateChapterSummaryFor(chapterNumber) {
    if (!currentProject) return;
    
    if (!confirm('确定要为这一章生成摘要吗？')) return;
    
    try {
        await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/chapters/${chapterNumber}/summary`,
            { method: 'POST' }
        );
        
        showAlert('摘要生成成功！');
        await selectProject(currentProject.title);
        
    } catch (error) {
        alert('生成摘要失败: ' + error.message);
    }
}

// ========== AI创作 ==========

function confirmAndGenerate() {
    const length = parseInt(document.getElementById('aiChapterLength').value);
    const btn = document.getElementById('generateChapterBtn');
    
    // 第一次点击：显示确认状态
    if (btn.textContent.includes('🚀')) {
        btn.textContent = '✅ 确认生成';
        btn.style.background = '#f44336';
        setTimeout(() => {
            if (btn.textContent.includes('✅')) {
                btn.textContent = '🚀 生成章节';
                btn.style.background = '';
            }
        }, 3000);
    } else {
        // 第二次点击：确认生成
        btn.textContent = '🚀 生成章节';
        btn.style.background = '';
        generateChapter();
    }
}

async function generateChapter() {
    if (!currentProject) return;
    
    // 防止重复请求
    if (isGenerating) {
        showAlert('正在生成中，请勿重复操作！', 'warning');
        return;
    }
    
    const data = {
        title: document.getElementById('aiChapterTitle').value.trim(),
        prompt: document.getElementById('aiChapterPrompt').value.trim(),
        length: parseInt(document.getElementById('aiChapterLength').value),
        generate_summary: document.getElementById('aiGenerateSummary').checked
    };
    
    // 创建持久化的进度提示
    const progressModal = createProgressModal('生成新章节', data.length);
    
    try {
        isGenerating = true;
        
        // 启动状态轮询
        startGenerationPolling(currentProject.title);
        
        // 发送生成请求（不等待完成，因为有轮询）
        apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/generate-chapter`,
            {
                method: 'POST',
                body: JSON.stringify(data)
            }
        ).then(result => {
            // 生成完成后清空表单
            document.getElementById('aiChapterTitle').value = '';
            document.getElementById('aiChapterPrompt').value = '';
        }).catch(error => {
            stopGenerationPolling();
            closeProgressModal();
            showAlert('生成失败: ' + error.message, 'error');
            isGenerating = false;
        });
        
        // 注意：不在这里设置 isGenerating = false，由轮询完成后再设置
        
    } catch (error) {
        stopGenerationPolling();
        closeProgressModal();
        showAlert('发送请求失败: ' + error.message, 'error');
        isGenerating = false;
    }
}

async function generateChapterIdea() {
    if (!currentProject) return;
    
    const titleInput = document.getElementById('aiChapterTitle');
    const promptInput = document.getElementById('aiChapterPrompt');
    const btn = event.target;
    
    // 保存原始按钮文本
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ 生成中...';
    
    try {
        const result = await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/generate-chapter-idea`,
            { method: 'POST' }
        );
        
        const idea = result.data;
        
        // 填充到输入框
        if (idea.title) {
            titleInput.value = idea.title;
        }
        if (idea.prompt) {
            promptInput.value = idea.prompt;
        }
        
        showAlert('✨ 章节创意生成成功！', 'success');
        
    } catch (error) {
        showAlert('生成失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ========== 角色追踪系统 ==========

let selectedCharacter = null;

function updateCharacterTrackingSelect() {
    if (!currentProject) return;
    
    const dropdown = document.getElementById('characterDropdown');
    
    if (currentProject.characters.length === 0) {
        dropdown.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">暂无角色</div>';
        return;
    }
    
    dropdown.innerHTML = currentProject.characters.map(char => {
        // 生成别名显示
        let aliasesText = '';
        if (char.aliases && char.aliases.length > 0) {
            aliasesText = `<div class="aliases-text" style="font-size:0.85em; color:#999; margin-top:2px;">别名: ${char.aliases.join(', ')}</div>`;
        }
        
        return `
            <div class="character-option" onclick="selectCharacter('${char.name.replace(/'/g, "\\'")}', event)">
                <div class="avatar">👤</div>
                <div class="info">
                    <div class="name">${char.name}</div>
                    <div class="desc">${char.description || '暂无描述'}</div>
                    ${aliasesText}
                </div>
            </div>
        `;
    }).join('');
    
    // 自动选择第一个角色并加载数据
    if (currentProject.characters.length > 0) {
        selectCharacter(currentProject.characters[0].name);
    }
}

function toggleCharacterDropdown() {
    const dropdown = document.getElementById('characterDropdown');
    const button = document.getElementById('characterSelectorButton');
    
    dropdown.classList.toggle('active');
    button.classList.toggle('active');
}

function selectCharacter(characterName, event) {
    selectedCharacter = characterName;
    
    // 更新按钮文本
    document.getElementById('selectedCharacterText').textContent = characterName;
    
    // 更新选中状态
    document.querySelectorAll('.character-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    // 如果有 event，标记当前选中项
    if (event && event.target) {
        const clickedOption = event.target.closest('.character-option');
        if (clickedOption) {
            clickedOption.classList.add('selected');
        }
    }
    
    // 关闭下拉框
    document.getElementById('characterDropdown').classList.remove('active');
    document.getElementById('characterSelectorButton').classList.remove('active');
    
    // 加载角色追踪数据
    loadCharacterTracking();
}

// 点击外部关闭下拉框
document.addEventListener('click', function(event) {
    const selector = document.querySelector('.character-selector');
    if (selector && !selector.contains(event.target)) {
        document.getElementById('characterDropdown')?.classList.remove('active');
        document.getElementById('characterSelectorButton')?.classList.remove('active');
    }
});

function updateCharacterTrackingSelect_old() {
    if (!currentProject) return;
    
    const select = document.getElementById('trackingCharacterSelect');
    select.innerHTML = '<option value="">-- 请选择角色 --</option>' +
        currentProject.characters.map(char => 
            `<option value="${char.name}">${char.name}</option>`
        ).join('');
    
    // 自动选择第一个角色并加载数据
    if (currentProject.characters.length > 0) {
        select.value = currentProject.characters[0].name;
        loadCharacterTracking();
    }
}

function displayCharacterBasicInfo(characterName) {
    const container = document.getElementById('characterBasicInfo');
    
    // 找到当前角色
    const char = currentProject.characters.find(c => c.name === characterName);
    
    if (!char) {
        container.innerHTML = '<p style="color:#999;">角色信息未找到</p>';
        return;
    }
    
    // 生成别名显示
    let aliasesHtml = '';
    if (char.aliases && char.aliases.length > 0) {
        aliasesHtml = `
            <div style="margin-top: 12px;">
                <strong style="color: #555;">别名：</strong>
                <div class="aliases-container" style="display: inline-block;">
                    ${char.aliases.map(alias => `<span class="alias-tag">${alias}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = `
        <div style="line-height: 1.8;">
            <div><strong style="color: #555;">正式名称：</strong>${char.name}</div>
            ${aliasesHtml}
            ${char.description ? `<div style="margin-top: 12px;"><strong style="color: #555;">描述：</strong>${char.description}</div>` : ''}
            ${char.personality ? `<div style="margin-top: 12px;"><strong style="color: #555;">性格：</strong>${char.personality}</div>` : ''}
            ${char.background ? `<div style="margin-top: 12px;"><strong style="color: #555;">背景：</strong>${char.background}</div>` : ''}
        </div>
    `;
}

async function loadCharacterTracking() {
    const characterName = selectedCharacter;
    
    if (!characterName || !currentProject) {
        document.getElementById('trackingContent').style.display = 'none';
        return;
    }
    
    try {
        document.getElementById('trackingContent').style.display = 'block';
        
        const result = await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/character-tracker/${encodeURIComponent(characterName)}`
        );
        
        const data = result.data;
        
        // 保存当前角色追踪数据到全局变量，并添加角色名称
        currentCharacterTracking = {
            ...data,
            character_name: characterName
        };
        
        // 显示角色基本信息（包括别名）
        displayCharacterBasicInfo(characterName);
        
        // 显示关系网络
        displayRelationshipNetwork(data.relationships);
        
        // 显示性格特质
        displayPersonalityTraits(data.personality_traits, data.personality_evolution);
        
        // 显示成长分析
        displayGrowthAnalysis(data.growth_analysis);
        
        // 显示时间线
        displayTimeline(data.timeline);
        
    } catch (error) {
        showAlert('加载角色追踪数据失败: ' + error.message, 'error');
    }
}

function displayRelationshipNetwork(relationships) {
    const container = document.getElementById('relationshipNetwork');
    
    if (relationships.length === 0) {
        container.innerHTML = '<p style="color:#999;">暂无关系记录</p>';
        return;
    }
    
    // 创建关系图谱的可视化
    let html = '<div class="relationship-grid">';
    
    relationships.forEach(rel => {
        const intimacyColor = getIntimacyColor(rel.intimacy_level);
        const intimacyStatus = getIntimacyStatus(rel.intimacy_level);
        const typeIcon = getRelationshipIcon(rel.relationship_type);
        
        // 显示关系变化历史
        const evolutionCount = rel.evolution_history ? rel.evolution_history.length : 0;
        const latestEvolution = evolutionCount > 0 ? rel.evolution_history[evolutionCount - 1] : null;
        
        html += `
            <div class="relationship-card" style="border-left: 4px solid ${intimacyColor};">
                <div class="relationship-header">
                    <span class="relationship-icon">${typeIcon}</span>
                    <span class="relationship-target">${rel.target_character}</span>
                    <span class="relationship-badge rel-${rel.relationship_type}">
                        ${getRelationshipTypeName(rel.relationship_type)}
                    </span>
                </div>
                
                <div class="intimacy-section">
                    <div class="intimacy-label">
                        <span>亲密度</span>
                        <span class="intimacy-value" style="color: ${intimacyColor};">
                            ${rel.intimacy_level} <span style="font-size:0.85em;">${intimacyStatus}</span>
                        </span>
                    </div>
                    <div class="intimacy-bar-modern">
                        <div class="intimacy-fill-modern" style="width: ${rel.intimacy_level}%; background: ${intimacyColor};"></div>
                    </div>
                </div>
                
                ${rel.description ? `
                    <div class="relationship-desc">
                        <p>${rel.description}</p>
                    </div>
                ` : ''}
                
                ${latestEvolution ? `
                    <div class="relationship-evolution">
                        <small style="color:#999;">
                            📊 第${latestEvolution.chapter}章：亲密度 
                            ${latestEvolution.old_intimacy} → ${latestEvolution.new_intimacy}
                            ${latestEvolution.old_intimacy < latestEvolution.new_intimacy ? '📈' : '📉'}
                        </small>
                        ${latestEvolution.reason ? `<br><small style="color:#666;">${latestEvolution.reason}</small>` : ''}
                    </div>
                ` : ''}
                
                ${evolutionCount > 1 ? `
                    <div class="relationship-history">
                        <button class="btn-link" onclick='showRelationshipHistory("${rel.target_character.replace(/"/g, '&quot;')}")'>
                            查看完整历史 (${evolutionCount}次变化)
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function getIntimacyColor(level) {
    if (level >= 80) return '#e91e63'; // 深情
    if (level >= 60) return '#ff9800'; // 亲密
    if (level >= 40) return '#4caf50'; // 友好
    if (level >= 20) return '#2196f3'; // 普通
    return '#9e9e9e'; // 陌生
}

function getIntimacyStatus(level) {
    if (level >= 90) return '深情款款';
    if (level >= 75) return '情深意切';
    if (level >= 60) return '亲密无间';
    if (level >= 45) return '友好相处';
    if (level >= 30) return '有所交集';
    if (level >= 15) return '初步认识';
    return '形同陌路';
}

function getRelationshipIcon(type) {
    const icons = {
        'friend': '🤝',
        'enemy': '⚔️',
        'family': '👨‍👩‍👧',
        'lover': '💕',
        'mentor': '🎓',
        'rival': '🥊',
        'neutral': '🤷'
    };
    return icons[type] || '👤';
}

function showRelationshipHistory(characterName) {
    console.log('showRelationshipHistory 被调用，角色名:', characterName);
    console.log('currentCharacterTracking:', currentCharacterTracking);
    
    if (!currentCharacterTracking) {
        showAlert('请先选择角色', 'warning');
        return;
    }
    
    // 查找该角色的关系数据
    const relationship = currentCharacterTracking.relationships.find(
        rel => rel.target_character === characterName
    );
    
    console.log('找到的关系数据:', relationship);
    
    if (!relationship || !relationship.evolution_history || relationship.evolution_history.length === 0) {
        showAlert('暂无关系变化历史', 'info');
        return;
    }
    
    // 生成历史时间线HTML
    const history = relationship.evolution_history;
    const typeIcon = getRelationshipIcon(relationship.relationship_type);
    const typeName = getRelationshipTypeName(relationship.relationship_type);
    
    let html = `
        <div style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                <span style="font-size: 32px;">${typeIcon}</span>
                <div>
                    <h3 style="margin: 0;">${currentCharacterTracking.character_name} ↔ ${characterName}</h3>
                    <p style="margin: 5px 0 0 0; color: #666;">关系类型：${typeName}</p>
                </div>
            </div>
            <p style="color: #666; margin: 10px 0;">${relationship.description || '暂无描述'}</p>
        </div>
        
        <div class="history-timeline">
    `;
    
    // 按章节顺序显示历史（倒序，最新的在上）
    const sortedHistory = [...history].sort((a, b) => b.chapter - a.chapter);
    
    sortedHistory.forEach((item, index) => {
        const isIncrease = item.new_intimacy > item.old_intimacy;
        const trendClass = isIncrease ? 'history-trend-up' : 'history-trend-down';
        const trendIcon = isIncrease ? '📈' : '📉';
        const change = Math.abs(item.new_intimacy - item.old_intimacy);
        
        html += `
            <div class="history-item">
                <span class="history-chapter">第 ${item.chapter} 章</span>
                
                <div class="history-change">
                    <span class="history-value">${item.old_intimacy}</span>
                    <span class="history-arrow ${trendClass}">
                        ${isIncrease ? '→' : '→'} ${trendIcon}
                    </span>
                    <span class="history-value ${trendClass}">${item.new_intimacy}</span>
                    <span style="color: #999; font-size: 13px;">
                        (${isIncrease ? '+' : ''}${item.new_intimacy - item.old_intimacy})
                    </span>
                </div>
                
                ${item.reason ? `
                    <div class="history-reason">
                        <strong>变化原因：</strong>${item.reason}
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    
    // 添加统计信息
    const maxIntimacy = Math.max(...history.map(h => Math.max(h.old_intimacy, h.new_intimacy)));
    const minIntimacy = Math.min(...history.map(h => Math.min(h.old_intimacy, h.new_intimacy)));
    const totalChanges = history.length;
    
    html += `
        <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 12px;">
            <h4 style="margin-bottom: 10px;">📊 关系统计</h4>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; text-align: center;">
                <div>
                    <div style="font-size: 24px; font-weight: bold; color: #667eea;">${totalChanges}</div>
                    <div style="font-size: 12px; color: #999;">变化次数</div>
                </div>
                <div>
                    <div style="font-size: 24px; font-weight: bold; color: #4caf50;">${maxIntimacy}</div>
                    <div style="font-size: 12px; color: #999;">最高亲密度</div>
                </div>
                <div>
                    <div style="font-size: 24px; font-weight: bold; color: #f44336;">${minIntimacy}</div>
                    <div style="font-size: 12px; color: #999;">最低亲密度</div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('relationshipHistoryContent').innerHTML = html;
    showModal('relationshipHistoryModal');
}

function getRelationshipTypeName(type) {
    const names = {
        'friend': '朋友',
        'enemy': '敌人',
        'family': '家人',
        'lover': '恋人',
        'mentor': '导师',
        'rival': '对手',
        'neutral': '中立'
    };
    return names[type] || type;
}

function displayPersonalityTraits(traits, evolution) {
    const container = document.getElementById('personalityTraits');
    
    if (traits.length === 0) {
        container.innerHTML = '<p style="color:#999;">暂无性格特质记录</p>';
        return;
    }
    
    // 创建性格雷达图（文本版）
    let html = '<div class="personality-radar">';
    html += '<h4 style="margin-bottom:15px;">🎭 性格特质雷达</h4>';
    html += '<div class="personality-grid">';
    
    traits.forEach(trait => {
        const changes = evolution.filter(e => e.trait_name === trait.trait_name);
        const latestChange = changes.length > 0 ? changes[changes.length - 1] : null;
        const trend = latestChange ? 
            (latestChange.new_intensity > latestChange.old_intensity ? '📈' : '📉') : '━';
        const trendColor = latestChange ?
            (latestChange.new_intensity > latestChange.old_intensity ? '#4caf50' : '#f44336') : '#999';
        
        // 根据强度设置颜色
        const intensityColor = trait.intensity >= 70 ? '#e91e63' :
                              trait.intensity >= 50 ? '#ff9800' :
                              trait.intensity >= 30 ? '#2196f3' : '#9e9e9e';
        
        html += `
            <div class="trait-card">
                <div class="trait-header">
                    <span class="trait-name-modern">${trait.trait_name}</span>
                    <span class="trait-trend" style="color:${trendColor};">${trend}</span>
                </div>
                <div class="trait-visual">
                    <div class="trait-bar-modern">
                        <div class="trait-fill-modern" style="width: ${trait.intensity}%; background: ${intensityColor};"></div>
                    </div>
                    <span class="trait-value" style="color: ${intensityColor};">${trait.intensity}</span>
                </div>
                ${trait.description ? `
                    <div class="trait-desc">
                        <small>${trait.description}</small>
                    </div>
                ` : ''}
                ${latestChange ? `
                    <div class="trait-change">
                        <small style="color:#666;">
                            第${latestChange.chapter_number}章：${latestChange.old_intensity} → ${latestChange.new_intensity}
                        </small>
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div></div>';
    
    // 显示性格变化历史（时间线形式）
    if (evolution.length > 0) {
        html += `
            <div class="personality-evolution">
                <h4 style="margin:20px 0 15px 0;">📊 性格演变轨迹</h4>
                <div class="evolution-timeline">
        `;
        
        evolution.slice(-6).forEach((evo, index) => {
            const isIncrease = evo.new_intensity > evo.old_intensity;
            const change = Math.abs(evo.new_intensity - evo.old_intensity);
            
            html += `
                <div class="evolution-item ${isIncrease ? 'increase' : 'decrease'}">
                    <div class="evolution-chapter">第${evo.chapter_number}章</div>
                    <div class="evolution-content">
                        <div class="evolution-trait">${evo.trait_name}</div>
                        <div class="evolution-change">
                            <span class="old-value">${evo.old_intensity}</span>
                            <span class="arrow">${isIncrease ? '→' : '→'}</span>
                            <span class="new-value">${evo.new_intensity}</span>
                            <span class="change-value" style="color:${isIncrease ? '#4caf50' : '#f44336'};">
                                (${isIncrease ? '+' : ''}${change})
                            </span>
                        </div>
                        ${evo.reason ? `
                            <div class="evolution-reason">
                                <small>${evo.reason}</small>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function displayGrowthAnalysis(analysis) {
    const container = document.getElementById('growthAnalysis');
    
    container.innerHTML = `
        <div class="growth-stat">
            <span class="growth-stat-label">总经历数</span>
            <span class="growth-stat-value">${analysis.total_experiences}</span>
        </div>
        <div class="growth-stat">
            <span class="growth-stat-label">正面事件</span>
            <span class="growth-stat-value" style="color:#28a745;">${analysis.positive_events}</span>
        </div>
        <div class="growth-stat">
            <span class="growth-stat-label">负面事件</span>
            <span class="growth-stat-value" style="color:#dc3545;">${analysis.negative_events}</span>
        </div>
        <div class="growth-stat">
            <span class="growth-stat-label">性格变化次数</span>
            <span class="growth-stat-value">${analysis.personality_changes}</span>
        </div>
        ${analysis.most_changed_trait ? `
            <div class="growth-stat">
                <span class="growth-stat-label">变化最大特质</span>
                <span class="growth-stat-value">${analysis.most_changed_trait}</span>
            </div>
        ` : ''}
        
        ${Object.keys(analysis.experience_breakdown).length > 0 ? `
            <div style="margin-top:20px;padding-top:20px;border-top:2px solid #e0e0e0;">
                <h4 style="margin-bottom:10px;">经历类型分布</h4>
                ${Object.entries(analysis.experience_breakdown).map(([type, count]) => `
                    <div class="growth-stat">
                        <span class="growth-stat-label">${getEventTypeName(type)}</span>
                        <span class="growth-stat-value">${count}</span>
                    </div>
                `).join('')}
            </div>
        ` : ''}
    `;
}

function getEventTypeName(type) {
    const names = {
        'achievement': '成就',
        'conflict': '冲突',
        'relationship': '关系',
        'growth': '成长',
        'trauma': '创伤'
    };
    return names[type] || type;
}

function displayTimeline(timeline) {
    const container = document.getElementById('characterTimeline');
    
    if (timeline.length === 0) {
        container.innerHTML = '<p style="color:#999;">暂无时间线记录</p>';
        return;
    }
    
    container.innerHTML = timeline.map(item => {
        let typeClass = '';
        let typeText = '';
        
        if (item.type === 'experience') {
            typeClass = 'type-experience';
            typeText = getEventTypeName(item.event_type);
        } else if (item.type === 'relationship') {
            typeClass = 'type-relationship';
            typeText = '关系变化';
        } else if (item.type === 'personality') {
            typeClass = 'type-personality';
            typeText = '性格变化';
        }
        
        return `
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <div>
                        <span class="timeline-type ${typeClass}">${typeText}</span>
                        <span style="color:#999;font-size:0.9em;margin-left:10px;">第${item.chapter}章</span>
                    </div>
                    <p style="margin:10px 0 0 0;">${item.content}</p>
                    ${item.reason ? `<p style="margin:5px 0 0 0;color:#666;font-size:0.9em;">原因：${item.reason}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function analyzeChapterForTracking(chapterNumber) {
    if (!currentProject) return;
    
    // 防止重复请求
    if (isGenerating) {
        alert('正在生成中，请勿重复操作！');
        return;
    }
    
    if (!confirm('确定要用AI分析这一章的角色动态吗？这将自动更新角色经历、关系和性格变化。')) {
        return;
    }
    
    const progressModal = createProgressModal('分析角色动态', 0, '正在分析章节内容...');
    
    try {
        isGenerating = true;
        
        await apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/analyze-chapter/${chapterNumber}`,
            { method: 'POST' }
        );
        
        closeProgressModal();
        showAlert('章节分析完成！角色追踪数据已更新。');
        await selectProject(currentProject.title);
        
    } catch (error) {
        closeProgressModal();
        showAlert('分析失败: ' + error.message, 'error');
    } finally {
        isGenerating = false;
    }
}

// ========== 大纲模式管理 ==========

let currentOutlines = [];
let currentCreationMode = 'direct';

function switchCreationMode(mode) {
    currentCreationMode = mode;
    
    // 更新按钮状态
    document.getElementById('directModeBtn').classList.toggle('active', mode === 'direct');
    document.getElementById('outlineModeBtn').classList.toggle('active', mode === 'outline');
    
    // 切换内容
    document.getElementById('directMode').style.display = mode === 'direct' ? 'block' : 'none';
    document.getElementById('outlineMode').style.display = mode === 'outline' ? 'block' : 'none';
    
    // 如果切换到大纲模式，加载大纲
    if (mode === 'outline') {
        loadOutlines();
    }
}

async function loadOutlines() {
    if (!currentProject) return;
    
    try {
        const result = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/outlines`);
        currentOutlines = result.data.outlines;
        
        // 更新状态统计
        updateOutlineStatus(result.data);
        
        // 显示大纲列表
        displayOutlines();
        
        // 显示或隐藏"继续生成"按钮
        const appendBtn = document.getElementById('appendOutlineBtn');
        if (appendBtn) {
            appendBtn.style.display = currentOutlines.length > 0 ? 'inline-block' : 'none';
        }
        
    } catch (error) {
        showAlert('加载大纲失败: ' + error.message, 'error');
    }
}

function updateOutlineStatus(data) {
    const statusHtml = `
        <div class="outline-stats">
            <div class="stat-box">
                <div class="number">${data.total || 0}</div>
                <div class="label">总章节</div>
            </div>
            <div class="stat-box">
                <div class="number">${data.generated || 0}</div>
                <div class="label">已生成</div>
            </div>
            <div class="stat-box">
                <div class="number">${data.planned || 0}</div>
                <div class="label">待生成</div>
            </div>
        </div>
    `;
    
    document.getElementById('outlineStatus').innerHTML = statusHtml;
}

function displayOutlines() {
    const container = document.getElementById('outlineList');
    
    if (currentOutlines.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div style="text-align: center; padding: 40px; color: #999;">
                    <div style="font-size: 48px; margin-bottom: 15px;">📝</div>
                    <p style="font-size: 16px; margin-bottom: 20px;">还没有章节大纲</p>
                    <button class="btn" onclick="showGenerateOutlineDialog()">
                        ✨ AI生成完整大纲
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = currentOutlines.map(outline => {
        const statusClass = `status-${outline.status}`;
        const statusText = outline.status === 'completed' ? '已完成' : 
                          outline.status === 'generated' ? '已生成' : '待生成';
        const statusIcon = outline.status === 'completed' ? '✅' : 
                          outline.status === 'generated' ? '⏳' : '📝';
        
        return `
            <div class="outline-item ${statusClass}">
                <div class="outline-header">
                    <div class="outline-title">
                        <input type="checkbox" class="outline-checkbox" 
                               data-chapter="${outline.chapter_number}"
                               onchange="toggleOutlineSelection(${outline.chapter_number})"
                               style="margin-right: 10px; width: 18px; height: 18px; cursor: pointer;">
                        <span>${statusIcon}</span>
                        <span>第${outline.chapter_number}章: ${outline.title}</span>
                    </div>
                    <span class="outline-status-badge ${statusClass}">${statusText}</span>
                </div>
                
                <div class="outline-summary">${outline.summary}</div>
                
                ${outline.key_events && outline.key_events.length > 0 ? `
                    <div class="outline-events">
                        <h5>🎯 关键事件</h5>
                        <ul>
                            ${outline.key_events.map(event => `<li>${event}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px;">
                    <div style="font-size: 13px; color: #999;">
                        👥 ${outline.involved_characters.join(', ') || '待定'} · 
                        📝 目标字数: ${outline.target_length}
                    </div>
                    <div class="outline-actions">
                        ${outline.status === 'planned' ? `
                            <button class="btn btn-secondary" onclick="editOutline(${outline.chapter_number})">编辑</button>
                            <button class="btn" onclick="generateFromOutline(${outline.chapter_number})">
                                🚀 生成章节
                            </button>
                        ` : outline.status === 'generated' ? `
                            <button class="btn btn-secondary" onclick="viewChapter(${outline.chapter_number})">查看章节</button>
                        ` : `
                            <button class="btn btn-secondary" onclick="viewChapter(${outline.chapter_number})">查看章节</button>
                        `}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// 显示生成大纲配置对话框
function showGenerateOutlineDialog() {
    if (!currentProject) {
        showAlert('请先选择项目', 'warning');
        return;
    }
    
    // 显示或隐藏警告提示
    const warningDiv = document.getElementById('existingOutlineWarning');
    if (warningDiv) {
        if (currentOutlines && currentOutlines.length > 0) {
            warningDiv.style.display = 'block';
        } else {
            warningDiv.style.display = 'none';
        }
    }
    
    // 打开模态框
    showModal('generateOutlineModal');
    
    // 更新预计时间
    const countInput = document.getElementById('outlineChapterCount');
    countInput.addEventListener('input', updateEstimatedTime);
    updateEstimatedTime();
}

function updateEstimatedTime() {
    const count = parseInt(document.getElementById('outlineChapterCount').value) || 30;
    const minutes = Math.ceil(count / 15); // 约每15章1分钟
    document.getElementById('estimatedTime').textContent = `${minutes}-${minutes + 1}分钟`;
}

// 确认生成大纲
async function confirmGenerateOutline() {
    const totalChapters = parseInt(document.getElementById('outlineChapterCount').value);
    const avgLength = parseInt(document.getElementById('outlineChapterLength').value);
    const storyGoal = document.getElementById('outlineStoryGoal').value.trim();
    
    // 验证输入
    if (totalChapters < 1 || totalChapters > 100) {
        showAlert('章节数量必须在1-100之间', 'warning');
        return;
    }
    
    if (avgLength < 1000 || avgLength > 10000) {
        showAlert('章节字数必须在1000-10000之间', 'warning');
        return;
    }
    
    // 如果已有大纲，需要二次确认
    if (currentOutlines && currentOutlines.length > 0) {
        if (!confirm(`⚠️ 警告：当前已有 ${currentOutlines.length} 章大纲！\n\n重新生成将清空所有旧大纲数据，此操作不可撤销。\n\n是否确定要重新生成？`)) {
            return;
        }
    }
    
    // 关闭对话框
    closeModal('generateOutlineModal');
    
    // 调用生成函数
    await generateFullOutline(totalChapters, avgLength, storyGoal);
}

async function generateFullOutline(totalChapters = 30, avgLength = 3000, storyGoal = '') {
    if (!currentProject) {
        showAlert('请先选择项目', 'warning');
        return;
    }
    
    // 显示加载状态
    const statusDiv = document.getElementById('outlineStatus');
    const originalContent = statusDiv.innerHTML;
    statusDiv.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="spinner" style="margin: 0 auto 20px;"></div>
            <p style="color: #667eea; font-size: 16px; font-weight: 500;">AI 正在构思完整故事框架...</p>
            <p style="color: #999; font-size: 14px; margin-top: 10px;">正在生成 ${totalChapters} 章大纲，请耐心等待</p>
            ${storyGoal ? `<p style="color: #667eea; font-size: 14px; margin-top: 5px;">🎯 目标：${storyGoal}</p>` : ''}
        </div>
    `;
    
    // 禁用生成按钮
    const generateBtn = document.querySelector('#outlineStatusCard button');
    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = '生成中...';
    }
    
    try {
        const result = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/generate-outline`, {
            method: 'POST',
            body: JSON.stringify({
                total_chapters: totalChapters,
                avg_chapter_length: avgLength,
                story_goal: storyGoal
            })
        });
        
        showAlert(`大纲生成成功！共生成 ${result.data.outlines.length} 章`, 'success');
        
        // 重新加载项目数据
        await selectProject(currentProject.title);
        
        // 加载并显示大纲
        await loadOutlines();
        
    } catch (error) {
        console.error('生成大纲错误:', error);
        statusDiv.innerHTML = originalContent;
        showAlert('生成大纲失败: ' + error.message, 'error');
    } finally {
        // 恢复生成按钮
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.textContent = '✨ AI生成完整大纲';
        }
    }
}

async function generateFromOutline(chapterNumber) {
    if (!currentProject) return;
    
    if (isGenerating) {
        showAlert('已有章节正在生成中，请稍候', 'warning');
        return;
    }
    
    const outline = currentOutlines.find(o => o.chapter_number === chapterNumber);
    if (!outline) return;
    
    // 检查是否有未生成的前置章节
    const missingPrevChapters = [];
    for (let i = 1; i < chapterNumber; i++) {
        const prevOutline = currentOutlines.find(o => o.chapter_number === i);
        if (prevOutline && prevOutline.status === 'planned') {
            missingPrevChapters.push(i);
        }
    }
    
    // 如果有未生成的前置章节，给出警告
    if (missingPrevChapters.length > 0) {
        const warningMsg = `⚠️ 检测到以下章节尚未生成：\n第 ${missingPrevChapters.join('、')} 章\n\n` +
            `跳过前置章节直接生成第${chapterNumber}章可能导致剧情不连贯。\n\n` +
            `建议按顺序生成章节以确保故事逻辑性。\n\n是否仍要继续生成第${chapterNumber}章？`;
        
        if (!confirm(warningMsg)) {
            return;
        }
    }
    
    if (!confirm(`确定要根据大纲生成第${chapterNumber}章吗？\n\n标题：${outline.title}\n目标字数：${outline.target_length}\n\n生成时间约1-3分钟`)) {
        return;
    }
    
    try {
        isGenerating = true;
        
        // 创建进度提示模态框
        const progressModal = createProgressModal(
            `根据大纲生成第${chapterNumber}章`, 
            outline.target_length,
            `正在生成：${outline.title}`
        );
        
        // 启动状态轮询
        startGenerationPolling(currentProject.title);
        
        // 发送生成请求（不等待完成，因为有轮询）
        apiCall(
            `/api/projects/${encodeURIComponent(currentProject.title)}/generate-from-outline/${chapterNumber}`,
            {
                method: 'POST'
            }
        ).catch(error => {
            stopGenerationPolling();
            closeProgressModal();
            showAlert('生成失败: ' + error.message, 'error');
            isGenerating = false;
        });
        
        // 注意：不在这里设置 isGenerating = false，由轮询完成后再设置
        
    } catch (error) {
        isGenerating = false;
        showAlert('生成失败: ' + error.message, 'error');
    }
}

function editOutline(chapterNumber) {
    const outline = currentOutlines.find(o => o.chapter_number === chapterNumber);
    if (!outline) {
        showAlert('未找到该章节大纲', 'error');
        return;
    }
    
    // 填充编辑表单
    document.getElementById('editOutlineChapterNumber').value = chapterNumber;
    document.getElementById('editOutlineTitle').value = outline.title || '';
    document.getElementById('editOutlineSummary').value = outline.summary || '';
    document.getElementById('editOutlineKeyEvents').value = (outline.key_events || []).join('\n');
    document.getElementById('editOutlineCharacters').value = (outline.involved_characters || []).join(',');
    document.getElementById('editOutlineTargetLength').value = outline.target_length || 3000;
    document.getElementById('editOutlineNotes').value = outline.notes || '';
    
    // 打开模态框
    showModal('editOutlineModal');
}

async function saveOutlineEdit() {
    const chapterNumber = parseInt(document.getElementById('editOutlineChapterNumber').value);
    const title = document.getElementById('editOutlineTitle').value.trim();
    const summary = document.getElementById('editOutlineSummary').value.trim();
    const keyEventsText = document.getElementById('editOutlineKeyEvents').value.trim();
    const charactersText = document.getElementById('editOutlineCharacters').value.trim();
    const targetLength = parseInt(document.getElementById('editOutlineTargetLength').value);
    const notes = document.getElementById('editOutlineNotes').value.trim();
    
    // 验证输入
    if (!title) {
        showAlert('章节标题不能为空', 'warning');
        return;
    }
    
    if (!summary) {
        showAlert('章节概要不能为空', 'warning');
        return;
    }
    
    // 解析关键事件和角色
    const keyEvents = keyEventsText.split('\n').filter(e => e.trim()).map(e => e.trim());
    const characters = charactersText.split(',').filter(c => c.trim()).map(c => c.trim());
    
    if (keyEvents.length === 0) {
        showAlert('至少需要一个关键事件', 'warning');
        return;
    }
    
    try {
        const result = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/outlines`, {
            method: 'POST',
            body: JSON.stringify({
                action: 'update',
                chapter_number: chapterNumber,
                title,
                summary,
                key_events: keyEvents,
                involved_characters: characters,
                target_length: targetLength,
                notes
            })
        });
        
        showAlert('大纲修改成功！', 'success');
        closeModal('editOutlineModal');
        
        // 重新加载大纲列表
        await loadOutlines();
        
    } catch (error) {
        showAlert('保存失败: ' + error.message, 'error');
    }
}

function viewChapter(chapterNumber) {
    // 切换到章节标签并定位到指定章节
    switchTab('chapters');
    setTimeout(() => {
        const chapterCard = document.querySelector(`[data-chapter="${chapterNumber}"]`);
        if (chapterCard) {
            chapterCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            chapterCard.style.boxShadow = '0 0 20px rgba(102, 126, 234, 0.5)';
            setTimeout(() => {
                chapterCard.style.boxShadow = '';
            }, 2000);
        }
    }, 300);
}

// === 批量操作功能 ===

let selectedOutlines = new Set();

function toggleOutlineSelection(chapterNumber) {
    if (selectedOutlines.has(chapterNumber)) {
        selectedOutlines.delete(chapterNumber);
    } else {
        selectedOutlines.add(chapterNumber);
    }
    
    updateSelectionUI();
}

function updateSelectionUI() {
    // 更新选中状态的视觉反馈
    document.querySelectorAll('.outline-item').forEach(item => {
        const checkbox = item.querySelector('.outline-checkbox');
        if (checkbox) {
            const chapterNum = parseInt(checkbox.dataset.chapter);
            checkbox.checked = selectedOutlines.has(chapterNum);
            if (selectedOutlines.has(chapterNum)) {
                item.style.backgroundColor = '#f0f4ff';
                item.style.borderColor = '#667eea';
            } else {
                item.style.backgroundColor = '';
                item.style.borderColor = '';
            }
        }
    });
    
    // 更新批量操作栏
    const bulkBar = document.getElementById('bulkActionBar');
    const countSpan = document.getElementById('selectedCount');
    
    if (selectedOutlines.size > 0) {
        bulkBar.style.display = 'block';
        countSpan.textContent = `已选择 ${selectedOutlines.size} 章`;
    } else {
        bulkBar.style.display = 'none';
    }
}

function clearSelection() {
    selectedOutlines.clear();
    updateSelectionUI();
}

function showRegenerateRangeDialog() {
    if (selectedOutlines.size === 0) {
        showAlert('请先选择要重新生成的章节', 'warning');
        return;
    }
    
    const selectedArray = Array.from(selectedOutlines).sort((a, b) => a - b);
    const rangeText = selectedArray.length > 5 
        ? `第${selectedArray[0]}-${selectedArray[selectedArray.length - 1]}章 等${selectedArray.length}章`
        : `第${selectedArray.join('、')}章`;
    
    document.getElementById('regenerateChapterRange').textContent = rangeText;
    document.getElementById('regenerateChapterLength').value = 3000;
    document.getElementById('regenerateStageGoal').value = '';
    
    showModal('regenerateRangeModal');
}

async function confirmRegenerateRange() {
    const selectedArray = Array.from(selectedOutlines).sort((a, b) => a - b);
    const stageGoal = document.getElementById('regenerateStageGoal').value.trim();
    const avgLength = parseInt(document.getElementById('regenerateChapterLength').value);
    
    if (!confirm(`确定要重新生成第${selectedArray.join('、')}章的大纲吗？\n\n此操作将覆盖原有大纲，不可撤销！`)) {
        return;
    }
    
    closeModal('regenerateRangeModal');
    
    try {
        // 显示加载状态
        const statusDiv = document.getElementById('outlineStatus');
        const originalContent = statusDiv.innerHTML;
        statusDiv.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <div class="spinner" style="margin: 0 auto 20px;"></div>
                <p style="color: #667eea; font-size: 16px; font-weight: 500;">正在重新生成第${selectedArray.join('、')}章大纲...</p>
                <p style="color: #999; font-size: 14px; margin-top: 10px;">请稍候</p>
            </div>
        `;
        
        const result = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/regenerate-outline-range`, {
            method: 'POST',
            body: JSON.stringify({
                chapter_numbers: selectedArray,
                stage_goal: stageGoal,
                avg_chapter_length: avgLength
            })
        });
        
        showAlert(`成功重新生成 ${selectedArray.length} 章大纲！`, 'success');
        
        // 清空选择
        clearSelection();
        
        // 重新加载项目和大纲
        await selectProject(currentProject.title);
        await loadOutlines();
        
    } catch (error) {
        showAlert('重新生成失败: ' + error.message, 'error');
    }
}

function showAppendOutlineDialog() {
    if (!currentProject || currentOutlines.length === 0) {
        showAlert('请先生成初始大纲', 'warning');
        return;
    }
    
    document.getElementById('currentOutlineCount').textContent = currentOutlines.length;
    document.getElementById('appendChapterCount').value = 10;
    document.getElementById('appendChapterLength').value = 3000;
    document.getElementById('appendStoryGoal').value = currentProject.story_goal || '';
    
    showModal('appendOutlineModal');
}

async function confirmAppendOutline() {
    const appendCount = parseInt(document.getElementById('appendChapterCount').value);
    const newGoal = document.getElementById('appendStoryGoal').value.trim();
    const avgLength = parseInt(document.getElementById('appendChapterLength').value);
    
    if (appendCount < 1 || appendCount > 50) {
        showAlert('追加章节数必须在1-50之间', 'warning');
        return;
    }
    
    closeModal('appendOutlineModal');
    
    try {
        // 显示加载状态
        const statusDiv = document.getElementById('outlineStatus');
        const originalContent = statusDiv.innerHTML;
        statusDiv.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <div class="spinner" style="margin: 0 auto 20px;"></div>
                <p style="color: #667eea; font-size: 16px; font-weight: 500;">正在追加生成 ${appendCount} 章大纲...</p>
                <p style="color: #999; font-size: 14px; margin-top: 10px;">基于现有大纲续写中</p>
            </div>
        `;
        
        const result = await apiCall(`/api/projects/${encodeURIComponent(currentProject.title)}/append-outlines`, {
            method: 'POST',
            body: JSON.stringify({
                additional_chapters: appendCount,
                new_goal: newGoal,
                avg_chapter_length: avgLength
            })
        });
        
        showAlert(`成功追加 ${appendCount} 章大纲！`, 'success');
        
        // 重新加载项目和大纲
        await selectProject(currentProject.title);
        await loadOutlines();
        
    } catch (error) {
        showAlert('追加大纲失败: ' + error.message, 'error');
    }
}
