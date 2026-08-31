class Workboard {
    constructor() {
        var meta = document.querySelector('meta[name="workboard-base-path"]');
        var basePath = meta ? meta.content.replace(/\/$/, '') : '';
        this.api = (basePath ? basePath : '') + '/api';
        this.projects = [];
        this.knowledge = [];
        this.todos = { todo: [], done: [], limits: { maxTodoItems: 12 } };
        this.csrfToken = null;
        this.noticeTimer = null;
        this.todoScreenshotFile = null;
        this.editingTodo = null;
        this.editingProject = null;
        this.todoClickTimer = null;
        this.archiveExpanded = false;
        this.aiSettings = null;
        this.knowledgeTypes = [
            { value: 'internal_docs', label: '内部技术文档' },
            { value: 'skill_packages', label: 'skill 技能包' },
            { value: 'efficiency_software', label: '定制效率软件' }
        ];
        this.bind();
        this.load();
    }

    async request(path, options) {
        var requestOptions = options || {};
        var method = (requestOptions.method || 'GET').toUpperCase();
        var headers = Object.assign({}, requestOptions.headers || {});
        if (method !== 'GET' && this.csrfToken) {
            headers['X-CSRF-Token'] = this.csrfToken;
        }
        var response = await fetch(this.api + path, Object.assign({}, requestOptions, { headers: headers }));
        var data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }
        if (!response.ok) {
            throw new Error(data.error || ('请求失败: ' + response.status));
        }
        return data;
    }

    bind() {
        document.getElementById('refreshButton').addEventListener('click', () => this.load());
        document.getElementById('logoutButton').addEventListener('click', () => this.logout());
        document.getElementById('searchInput').addEventListener('input', () => this.renderSearchResults());
        document.getElementById('clearSearchButton').addEventListener('click', () => this.clearSearch());
        document.getElementById('archiveToggle').addEventListener('click', () => this.toggleArchiveTimeline());
        document.getElementById('settingsButton').addEventListener('click', () => this.openSettings());
        document.getElementById('closeSettings').addEventListener('click', () => {
            document.getElementById('settingsDialog').close();
        });
        document.getElementById('cancelSettings').addEventListener('click', () => {
            document.getElementById('settingsDialog').close();
        });
        document.getElementById('aiSettingsForm').addEventListener('submit', event => {
            event.preventDefault();
            this.saveAiSettings();
        });
        document.getElementById('localImportForm').addEventListener('submit', event => {
            event.preventDefault();
            this.importLocalTasks();
        });
        document.getElementById('todoForm').addEventListener('submit', event => {
            event.preventDefault();
            this.createTodo();
        });
        document.getElementById('projectForm').addEventListener('submit', event => {
            event.preventDefault();
            this.createProject();
        });
        document.getElementById('knowledgeForm').addEventListener('submit', event => {
            event.preventDefault();
            this.createKnowledgeItem();
        });
        document.querySelectorAll('.knowledge-expand-button').forEach(button => {
            button.addEventListener('click', () => this.openKnowledgeDialog(button.dataset.type));
        });
        document.getElementById('closeKnowledgeDialog').addEventListener('click', () => {
            document.getElementById('knowledgeDialog').close();
        });
        document.getElementById('summaryToday').addEventListener('click', () => this.generateSummary('today'));
        document.getElementById('summaryWeek').addEventListener('click', () => this.generateSummary('week'));
        document.getElementById('closeSummary').addEventListener('click', () => {
            document.getElementById('summaryDialog').close();
        });
        document.getElementById('closeTodoEdit').addEventListener('click', () => this.closeTodoEditor());
        document.getElementById('cancelTodoEdit').addEventListener('click', () => this.closeTodoEditor());
        document.getElementById('todoEditForm').addEventListener('submit', event => {
            event.preventDefault();
            this.saveTodoEdit();
        });
        document.getElementById('todoArchiveRetry').addEventListener('click', event => {
            event.stopPropagation();
            if (this.editingTodo) this.retryArchive(this.editingTodo.id);
        });
        document.getElementById('closeProjectEdit').addEventListener('click', () => this.closeProjectEditor());
        document.getElementById('cancelProjectEdit').addEventListener('click', () => this.closeProjectEditor());
        document.getElementById('projectEditForm').addEventListener('submit', event => {
            event.preventDefault();
            this.saveProjectEdit();
        });
        var today = new Date().toISOString().slice(0, 10);
        document.getElementById('projectCreated').value = today;
        document.getElementById('todoDate').value = today;
        var pasteZone = document.getElementById('todoPasteZone');
        var screenshotInput = document.getElementById('todoScreenshot');
        pasteZone.addEventListener('click', () => screenshotInput.click());
        pasteZone.addEventListener('paste', event => this.capturePastedScreenshot(event));
        screenshotInput.addEventListener('change', () => {
            this.setTodoScreenshot(screenshotInput.files && screenshotInput.files[0]);
        });
        document.getElementById('clearTodoScreenshot').addEventListener('click', () => {
            this.setTodoScreenshot(null);
        });
    }

    async load() {
        this.setStatus('正在加载...', false);
        try {
            var results = await Promise.all([
                this.request('/session'),
                this.request('/health'),
                this.request('/projects'),
                this.request('/todos'),
                this.request('/contributions'),
                this.request('/knowledge')
            ]);
            this.csrfToken = results[0].csrfToken || null;
            this.projects = results[2];
            this.todos = results[3];
            this.contributions = results[4] || {};
            this.knowledge = results[5] || [];
            this.renderAll();
            this.setStatus('在线', true);
            this.loadAiSettings();
            var lastUpdated = document.getElementById('lastUpdated');
            if (lastUpdated) {
                lastUpdated.textContent = '更新于 ' + new Date().toLocaleString('zh-CN');
            }
        } catch (error) {
            this.setStatus('服务不可用', false);
            this.showNotice(error.message, true);
        }
    }

    renderAll() {
        this.renderSearchStatus();
        this.renderStats();
        this.renderProjectSelect();
        this.renderProjects();
        this.renderKnowledge();
        this.renderTodos();
        this.renderArchiveTimeline();
        this.renderHeatmap();
    }

    renderStats() {
        var todoCount = this.filteredTodos('todo').length;
        var maxTodoItems = this.todos.limits.maxTodoItems || 12;
        document.getElementById('todoLimit').textContent = '当前任务 ' + todoCount + ' / ' + maxTodoItems;
    }

    setStatus(text, online) {
        var serverStatus = document.getElementById('serverStatus');
        var serverStatusDot = document.getElementById('serverStatusDot');
        if (!serverStatus || !serverStatusDot) return;
        serverStatus.textContent = text;
        serverStatusDot.className = 'status-dot ' + (online ? 'online' : 'offline');
    }

    renderProjectSelect() {
        this.populateProjectSelect(document.getElementById('todoProject'));
    }

    populateProjectSelect(select) {
        select.innerHTML = '<option value="">所属项目（可选）</option>';
        this.projects.forEach(project => {
            var option = document.createElement('option');
            option.value = String(project.id);
            option.textContent = project.name;
            select.appendChild(option);
        });
    }

    renderSearchResults() {
        this.renderSearchStatus();
        this.renderStats();
        this.renderProjects();
        this.renderKnowledge();
        this.renderTodos();
        this.renderArchiveTimeline();
    }

    renderSearchStatus() {
        var query = this.getSearchQuery();
        var status = document.getElementById('searchStatus');
        var text = document.getElementById('searchStatusText');
        if (!status || !text) return;
        status.hidden = !query;
        text.innerHTML = query ? '搜索中：' + this.highlightSearch(query) : '';
    }

    clearSearch() {
        var input = document.getElementById('searchInput');
        if (!input) return;
        input.value = '';
        this.renderSearchResults();
        input.focus();
    }

    getSearchQuery() {
        var input = document.getElementById('searchInput');
        return input ? input.value.trim().toLowerCase() : '';
    }

    textMatchesSearch(parts) {
        var query = this.getSearchQuery();
        if (!query) return true;
        var text = parts.filter(Boolean).join(' ').toLowerCase();
        return text.indexOf(query) >= 0;
    }

    projectMatchesSearch(project) {
        var gitInfo = project.gitInfo || {};
        var commits = gitInfo.commits || [];
        return this.textMatchesSearch([
            project.name,
            project.description,
            project.localPath,
            project.nasPath,
            project.gitRepo,
            project.pathLabel,
            gitInfo.branch,
            (project.tags || []).join(' '),
            (project.categories || []).join(' '),
            commits.map(commit => [
                commit.message,
                commit.hash,
                commit.date,
                commit.relative_date
            ].filter(Boolean).join(' ')).join(' ')
        ]);
    }

    todoMatchesSearch(item) {
        return this.textMatchesSearch([
            item.name,
            item.projectName,
            item.projectNumber,
            item.contact,
            item.notes,
            item.taskDate,
            item.dueAt,
            item.completedAt,
            item.resultDescription,
            item.localPath,
            this.archiveStatusLabel(item.archiveStatus)
        ]);
    }

    knowledgeMatchesSearch(item) {
        return this.textMatchesSearch([
            item.name,
            item.type,
            item.typeLabel,
            item.localPath
        ]);
    }

    knowledgeItemsForType(type) {
        return (this.knowledge || []).filter(item => item.type === type && this.knowledgeMatchesSearch(item));
    }

    filteredTodos(status) {
        return (this.todos[status] || []).filter(item => this.todoMatchesSearch(item));
    }

    escapeRegExp(value) {
        return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    highlightSearch(value) {
        var text = value == null ? '' : String(value);
        var query = this.getSearchQuery();
        if (!query) return this.escape(text);
        var pattern = new RegExp('(' + this.escapeRegExp(query) + ')', 'ig');
        var result = '';
        var lastIndex = 0;
        text.replace(pattern, (match, _group, offset) => {
            result += this.escape(text.slice(lastIndex, offset));
            result += '<mark class="search-highlight">' + this.escape(match) + '</mark>';
            lastIndex = offset + match.length;
            return match;
        });
        result += this.escape(text.slice(lastIndex));
        return result;
    }

    renderProjects() {
        var filtered = this.projects.filter(project => this.projectMatchesSearch(project));
        document.getElementById('projectResultCount').textContent = filtered.length + ' 个结果';
        var container = document.getElementById('projects');
        container.innerHTML = '';
        if (!filtered.length) {
            container.innerHTML = '<p class="empty">没有匹配的项目。</p>';
            return;
        }
        filtered.forEach(project => container.appendChild(this.projectCard(project)));
    }

    projectCard(project) {
        var card = document.createElement('article');
        card.className = 'project-card';
        var git = project.gitInfo;
        var pathStatus = project.pathStatus || {};
        var tags = (project.tags || []).map(tag => '<span class="tag">' + this.highlightSearch(tag) + '</span>').join('');
        var categories = (project.categories || []).map(tag => '<span class="category">' + this.highlightSearch(tag) + '</span>').join('');
        var commits = this.projectCommitList(project);
        var nasState = 'NAS ' + (pathStatus.nasExists ? '可用' : '未连接');
        var gitState = git ? git.branch : '无 Git 信息';
        card.classList.add('openable');
        card.title = project.localPath ? '双击打开本地路径：' + project.localPath : '双击提示配置本地路径';
        card.innerHTML =
            '<div class="card-top"><span class="project-id">#' + project.id + '</span>' +
            '<div class="project-card-actions"><span class="path-label">' + this.highlightSearch(project.pathLabel || '路径未配置') + '</span>' +
            '<button class="link-button project-edit-button" type="button">编辑</button></div></div>' +
            '<h3>' + this.highlightSearch(project.name) + '</h3>' +
            '<p class="muted description">' + this.highlightSearch(project.description || '暂无描述') + '</p>' +
            '<div class="tag-row">' + tags + categories + '</div>' +
            '<div class="project-meta">' +
            '<span class="path-state ' + (pathStatus.nasExists ? 'good' : '') + '">' + this.highlightSearch(nasState) + '</span>' +
            '<span class="path-state ' + (git ? 'good' : '') + '">' + this.highlightSearch(gitState) + '</span>' +
            '</div>' +
            commits;
        card.addEventListener('dblclick', event => {
            event.stopPropagation();
            this.openProjectFolder(project);
        });
        card.querySelector('.project-edit-button').addEventListener('click', event => {
            event.stopPropagation();
            this.openProjectEditor(project);
        });
        return card;
    }

    projectCommitList(project) {
        var gitInfo = project.gitInfo || {};
        var commits = gitInfo.commits ? gitInfo.commits.slice(0, 3) : [];
        if (!commits.length) return '';
        return '<div class="project-commit-list">' + commits.map(commit => {
            var meta = (commit.relative_date || commit.date || '') + ' · ' + (commit.hash || '');
            return '<div class="project-commit">' +
                '<span class="commit-message">' + this.highlightSearch(commit.message || '') + '</span>' +
                '<span class="commit-meta">' + this.highlightSearch(meta) + '</span>' +
                '</div>';
        }).join('') + '</div>';
    }

    async openProjectEditor(project) {
        try {
            var details = await this.request('/projects/' + project.id);
            this.editingProject = details;
            document.getElementById('projectEditName').value = details.name || '';
            document.getElementById('projectEditNasPath').value = details.nasPath || '';
            document.getElementById('projectEditLocalPath').value = details.localPath || '';
            document.getElementById('projectEditGitRepo').value = details.gitRepo || '';
            document.getElementById('projectEditCreated').value = details.created || new Date().toISOString().slice(0, 10);
            document.getElementById('projectEditTags').value = (details.tags || []).join(', ');
            document.getElementById('projectEditCategories').value = (details.categories || []).join(', ');
            document.getElementById('projectEditDescription').value = details.description || '';
            document.getElementById('projectEditDialog').showModal();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    closeProjectEditor() {
        var dialog = document.getElementById('projectEditDialog');
        if (dialog.open) dialog.close();
        this.editingProject = null;
    }

    async saveProjectEdit() {
        if (!this.editingProject) return;
        var payload = {
            name: document.getElementById('projectEditName').value.trim(),
            nasPath: document.getElementById('projectEditNasPath').value.trim(),
            localPath: document.getElementById('projectEditLocalPath').value.trim(),
            gitRepo: document.getElementById('projectEditGitRepo').value.trim(),
            created: document.getElementById('projectEditCreated').value,
            tags: document.getElementById('projectEditTags').value,
            categories: document.getElementById('projectEditCategories').value,
            description: document.getElementById('projectEditDescription').value.trim()
        };
        try {
            await this.request('/projects/' + this.editingProject.id, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            this.showNotice('项目信息已更新');
            this.closeProjectEditor();
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    renderKnowledge() {
        var total = 0;
        this.knowledgeTypes.forEach(typeInfo => {
            var type = typeInfo.value;
            var items = this.knowledgeItemsForType(type);
            total += items.length;
            var container = document.getElementById('knowledgeList-' + type);
            if (!container) return;
            container.innerHTML = '';
            var visibleItems = this.knowledgeItemsForType(type).slice(0, 5);
            if (!visibleItems.length) {
                container.innerHTML = '<p class="empty small">暂无内容。</p>';
            } else {
                visibleItems.forEach(item => container.appendChild(this.knowledgeRow(item)));
            }
            var button = document.querySelector('.knowledge-expand-button[data-type="' + type + '"]');
            if (button) {
                button.textContent = items.length > 5 ? '展开全部 ' + items.length : '查看全部';
            }
        });
        var resultCount = document.getElementById('knowledgeResultCount');
        if (resultCount) resultCount.textContent = total + ' 个结果';
    }

    knowledgeRow(item) {
        var row = document.createElement('div');
        row.className = 'knowledge-row';
        var localExists = item.pathStatus && item.pathStatus.localExists;
        row.innerHTML =
            '<div class="knowledge-row-main">' +
            '<strong>' + this.highlightSearch(item.name) + '</strong>' +
            '<span class="muted small">' + this.highlightSearch(item.localPath || '') + '</span>' +
            '</div>' +
            '<div class="knowledge-row-actions">' +
            '<span class="path-state ' + (localExists ? 'good' : '') + '">' + (localExists ? '本地可用' : '路径待确认') + '</span>' +
            '<button class="link-button knowledge-open-button" type="button">打开</button>' +
            '</div>';
        row.querySelector('.knowledge-open-button').addEventListener('click', event => {
            event.stopPropagation();
            this.openKnowledgeItem(item);
        });
        return row;
    }

    openKnowledgeDialog(type) {
        var typeInfo = this.knowledgeTypes.find(item => item.value === type);
        if (!typeInfo) return;
        var items = this.knowledgeItemsForType(type);
        document.getElementById('knowledgeDialogTitle').textContent = typeInfo.label + '（' + items.length + '）';
        var container = document.getElementById('knowledgeDialogList');
        container.innerHTML = '';
        if (!items.length) {
            container.innerHTML = '<p class="empty">暂无内容。</p>';
        } else {
            items.forEach(item => container.appendChild(this.knowledgeRow(item)));
        }
        document.getElementById('knowledgeDialog').showModal();
    }

    async openKnowledgeItem(item) {
        try {
            await this.request('/knowledge/' + item.id + '/open', { method: 'POST' });
            this.showNotice('已请求打开知识库路径');
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    renderTodos() {
        var container = document.getElementById('todos');
        container.innerHTML = '';
        var items = this.filteredTodos('todo');
        if (!items.length) {
            container.innerHTML = '<p class="empty">' + (this.getSearchQuery() ? '没有匹配的任务。' : '暂无任务。') + '</p>';
            return;
        }
        items.forEach(item => {
            var card = document.createElement('article');
            card.className = 'todo-item';
            card.dataset.todoId = String(item.id);
            var dueText = item.dueAt ? '截止 ' + item.dueAt.replace('T', ' ') : '';
            var projectName = item.projectName === 'Temporary work' ? '临时工作' : (item.projectName || '临时工作');
            var screenshot = item.screenshotUrl
                ? '<button class="todo-shot" type="button" aria-label="查看任务截图"><img src="' + this.api + '/todos/' + item.id + '/screenshot" alt="任务截图"></button>'
                : '';
            var archiveLabel = this.archiveStatusLabel(item.archiveStatus);
            var archiveClass = item.archiveStatus ? ' archive-' + item.archiveStatus : '';
            var archiveError = item.archiveStatus === 'failed' && item.archiveError
                ? '<p class="archive-error">' + this.escape(item.archiveError) + '</p>'
                : '';
            card.innerHTML =
                '<div class="todo-card-top"><span class="project-id">TASK #' + item.id + '</span><span class="progress">' + item.progress + '%</span></div>' +
                '<div class="todo-main"><button class="check" type="button" aria-label="完成任务"></button>' +
                '<div><h3>' + this.highlightSearch(item.name) + '</h3><p class="muted">' + this.highlightSearch(projectName) +
                (item.projectNumber ? ' · ' + this.highlightSearch(item.projectNumber) : '') + '</p></div></div>' +
                '<div class="todo-detail-row"><span>联系人 ' + this.highlightSearch(item.contact || '未填写') + '</span><span>日期 ' + this.highlightSearch(item.taskDate || '-') + '</span></div>' +
                (item.localPath ? '<div class="todo-detail-row"><span>本地 ' + this.highlightSearch(item.localPath) + '</span></div>' : '') +
                (item.notes ? '<p class="todo-notes">' + this.highlightSearch(item.notes) + '</p>' : '') + screenshot +
                (archiveLabel ? '<div class="archive-status' + archiveClass + '">' + this.highlightSearch(archiveLabel) + '</div>' + archiveError : '') +
                '<div class="todo-actions"><span class="progress">' + item.progress + '%</span>' +
                '<button class="link-button document-button" type="button">记录</button>' +
                '<button class="link-button complete-button" type="button">完成</button>' +
                '</div><div class="todo-due muted small">' + (dueText ? '<span>' + this.highlightSearch(dueText) + '</span>' : '') + '</div>';
            card.addEventListener('click', () => {
                clearTimeout(this.todoClickTimer);
                this.todoClickTimer = setTimeout(() => this.openTodoEditor(item), 180);
            });
            card.addEventListener('dblclick', () => {
                clearTimeout(this.todoClickTimer);
                this.openTodoFolder(item);
            });
            card.querySelector('.document-button').addEventListener('click', event => {
                event.stopPropagation();
                window.open(this.api + '/todos/' + item.id + '/document', '_blank', 'noopener,noreferrer');
            });
            card.querySelector('.complete-button').addEventListener('click', event => {
                event.stopPropagation();
                this.completeTodo(item.id);
            });
            card.querySelector('.check').addEventListener('click', event => {
                event.stopPropagation();
                this.completeTodo(item.id);
            });
            if (item.screenshotUrl) {
                card.querySelector('.todo-shot').addEventListener('click', event => {
                    event.stopPropagation();
                    window.open(this.api + '/todos/' + item.id + '/screenshot', '_blank', 'noopener,noreferrer');
                });
            }
            container.appendChild(card);
        });
    }

    archiveStatusLabel(status) {
        return {
            pending: '等待归档',
            claimed: '正在归档',
            committed: '正在归档',
            failed: '归档失败',
            complete: '已完成'
        }[status] || '';
    }

    toggleArchiveTimeline() {
        this.archiveExpanded = !this.archiveExpanded;
        this.renderArchiveTimeline();
    }

    renderArchiveTimeline() {
        var container = document.getElementById('archiveTimeline');
        var button = document.getElementById('archiveToggle');
        if (!container || !button) return;
        var items = this.filteredTodos('done').slice().sort((left, right) => {
            return String(right.completedAt || '').localeCompare(String(left.completedAt || ''));
        });
        button.textContent = this.archiveExpanded ? '收起归档' : '归档任务 ' + items.length;
        button.setAttribute('aria-expanded', this.archiveExpanded ? 'true' : 'false');
        container.hidden = !this.archiveExpanded;
        if (!this.archiveExpanded) return;
        if (!items.length) {
            container.innerHTML = '<p class="empty">' + (this.getSearchQuery() ? '没有匹配的归档任务。' : '暂无归档任务。') + '</p>';
            return;
        }
        container.innerHTML = '<div class="archive-timeline-list">' + items.map(item => {
            var completedAt = item.completedAt ? item.completedAt.replace('T', ' ').slice(0, 16) : '完成时间未记录';
            var projectName = item.projectName === 'Temporary work' ? '临时工作' : (item.projectName || '临时工作');
            var projectMeta = projectName + (item.projectNumber ? ' · ' + item.projectNumber : '');
            return '<article class="archive-timeline-item">' +
                '<time class="archive-timeline-time">' + this.highlightSearch(completedAt) + '</time>' +
                '<h3>' + this.highlightSearch(item.name || '未命名任务') + '</h3>' +
                '<p class="archive-timeline-meta">' + this.highlightSearch(projectMeta) + '</p>' +
                '<p class="archive-timeline-summary">' + this.highlightSearch(this.archiveSummary(item)) + '</p>' +
                '</article>';
        }).join('') + '</div>';
    }

    archiveSummary(item) {
        var source = item.resultDescription || item.notes || item.name || '';
        source = source.replace(/\s+/g, ' ').trim();
        if (!source) return '任务已完成并归档。';
        return source.length > 72 ? source.slice(0, 72) + '…' : source;
    }

    openTodoEditor(item) {
        this.editingTodo = item;
        this.populateProjectSelect(document.getElementById('todoEditProject'));
        document.getElementById('todoEditName').value = item.name || '';
        document.getElementById('todoEditProject').value = item.projectId ? String(item.projectId) : '';
        document.getElementById('todoEditProjectName').value = item.projectName === 'Temporary work' ? '' : (item.projectName || '');
        document.getElementById('todoEditProjectNumber').value = item.projectNumber || '';
        document.getElementById('todoEditContact').value = item.contact || '';
        document.getElementById('todoEditDate').value = item.taskDate || '';
        document.getElementById('todoEditDue').value = item.dueAt || '';
        document.getElementById('todoEditProgress').value = item.progress == null ? 0 : item.progress;
        document.getElementById('todoEditLocalPath').value = item.localPath || '';
        document.getElementById('todoEditNotes').value = item.notes || '';
        document.getElementById('todoEditResultDescription').value = item.resultDescription || '';
        var archiveArea = document.getElementById('todoArchiveArea');
        var archiveLabel = this.archiveStatusLabel(item.archiveStatus);
        archiveArea.hidden = !archiveLabel && !item.archiveError;
        document.getElementById('todoArchiveStatus').textContent = archiveLabel;
        document.getElementById('todoArchiveError').textContent = item.archiveError || '';
        document.getElementById('todoArchiveRetry').hidden = item.archiveStatus !== 'failed';
        document.getElementById('todoEditDialog').showModal();
    }

    closeTodoEditor() {
        document.getElementById('todoEditDialog').close();
        this.editingTodo = null;
    }

    openTodoFolder(item) {
        var query = '?todoId=' + encodeURIComponent(item.id) + '&path=' + encodeURIComponent(item.localPath || '');
        window.location.href = 'workboard://open' + query;
    }

    async openProjectFolder(project) {
        if (!project.localPath) {
            this.showNotice('项目未配置本地路径', true);
            return;
        }
        try {
            await this.request('/project/' + project.id + '/open', { method: 'POST' });
            this.showNotice('已请求打开本地项目路径');
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    async saveTodoEdit() {
        if (!this.editingTodo) return;
        var payload = {
            name: document.getElementById('todoEditName').value.trim(),
            projectId: document.getElementById('todoEditProject').value,
            projectName: document.getElementById('todoEditProjectName').value.trim(),
            projectNumber: document.getElementById('todoEditProjectNumber').value.trim(),
            contact: document.getElementById('todoEditContact').value.trim(),
            taskDate: document.getElementById('todoEditDate').value,
            dueAt: document.getElementById('todoEditDue').value,
            progress: document.getElementById('todoEditProgress').value,
            localPath: document.getElementById('todoEditLocalPath').value.trim(),
            notes: document.getElementById('todoEditNotes').value.trim(),
            resultDescription: document.getElementById('todoEditResultDescription').value.trim()
        };
        try {
            await this.request('/todos/' + this.editingTodo.id, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            this.closeTodoEditor();
            this.showNotice('任务已保存');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    async retryArchive(id) {
        try {
            await this.request('/todos/' + id + '/archive/retry', { method: 'POST' });
            this.closeTodoEditor();
            this.showNotice('已重新加入归档队列');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    renderHeatmap() {
        var container = document.getElementById('heatmap');
        container.innerHTML = '';
        var today = new Date();
        for (var index = 364; index >= 0; index -= 1) {
            var date = new Date(today);
            date.setDate(today.getDate() - index);
            var key = date.toISOString().slice(0, 10);
            var count = Number(this.contributions[key] || 0);
            var cell = document.createElement('span');
            cell.className = 'heat-cell level-' + Math.min(count, 4);
            cell.title = key + ': ' + count + ' commits';
            container.appendChild(cell);
        }
    }

    async createTodo() {
        var formData = new FormData();
        formData.append('name', document.getElementById('todoName').value.trim());
        formData.append('projectId', document.getElementById('todoProject').value);
        formData.append('projectNumber', document.getElementById('todoProjectNumber').value.trim());
        formData.append('contact', document.getElementById('todoContact').value.trim());
        formData.append('notes', document.getElementById('todoNotes').value.trim());
        formData.append('taskDate', document.getElementById('todoDate').value);
        formData.append('dueAt', document.getElementById('todoDue').value);
        formData.append('progress', '0');
        if (this.todoScreenshotFile) {
            formData.append('screenshot', this.todoScreenshotFile, this.todoScreenshotFile.name || 'clipboard.png');
        }
        try {
            await this.request('/todos', {
                method: 'POST',
                body: formData
            });
            document.getElementById('todoForm').reset();
            document.getElementById('todoDate').value = new Date().toISOString().slice(0, 10);
            this.setTodoScreenshot(null);
            this.showNotice('任务已创建');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    async importLocalTasks() {
        var rootInput = document.getElementById('localImportRoot');
        var result = document.getElementById('localImportResult');
        var rootPath = rootInput.value.trim();
        result.textContent = '正在导入...';
        try {
            var response = await this.request('/import/local-tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rootPath: rootPath })
            });
            result.textContent = '已导入 ' + response.imported + ' 个，跳过重复 ' + response.skipped + ' 个。';
            this.showNotice('历史任务导入完成');
            await this.load();
        } catch (error) {
            result.textContent = error.message;
            this.showNotice(error.message, true);
        }
    }

    capturePastedScreenshot(event) {
        var items = event.clipboardData && event.clipboardData.items;
        if (!items) return;
        for (var index = 0; index < items.length; index += 1) {
            if (items[index].type.indexOf('image/') === 0) {
                event.preventDefault();
                this.setTodoScreenshot(items[index].getAsFile());
                return;
            }
        }
        this.showNotice('剪贴板中没有图片', true);
    }

    setTodoScreenshot(file) {
        var preview = document.getElementById('todoScreenshotPreview');
        var hint = document.getElementById('todoPasteHint');
        var clearButton = document.getElementById('clearTodoScreenshot');
        var input = document.getElementById('todoScreenshot');
        this.todoScreenshotFile = file || null;
        if (!file) {
            preview.hidden = true;
            preview.removeAttribute('src');
            hint.hidden = false;
            clearButton.hidden = true;
            input.value = '';
            return;
        }
        if (file.type.indexOf('image/') !== 0) {
            this.showNotice('请选择图片文件', true);
            return;
        }
        preview.src = URL.createObjectURL(file);
        preview.hidden = false;
        hint.hidden = true;
        clearButton.hidden = false;
    }

    async completeTodo(id) {
        try {
            await this.request('/todos/' + id + '/complete', { method: 'POST' });
            this.showNotice('任务已完成');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    async createProject() {
        var payload = {
            name: document.getElementById('projectName').value.trim(),
            nasPath: document.getElementById('projectNasPath').value.trim(),
            localPath: document.getElementById('projectLocalPath').value.trim(),
            gitRepo: document.getElementById('projectGitRepo').value.trim(),
            created: document.getElementById('projectCreated').value,
            tags: document.getElementById('projectTags').value,
            categories: document.getElementById('projectCategories').value,
            description: document.getElementById('projectDescription').value.trim()
        };
        try {
            await this.request('/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            document.getElementById('projectForm').reset();
            document.getElementById('projectCreated').value = new Date().toISOString().slice(0, 10);
            this.showNotice('项目已保存');
            await this.load();
        } catch (error) {
            var message = error.message;
            if (/project name already exists/i.test(message) || /项目.*已.*存在/.test(message)) {
                message += '。如果项目不可见，请清空搜索条件。';
            }
            this.showNotice(message, true);
        }
    }

    async createKnowledgeItem() {
        var payload = {
            name: document.getElementById('knowledgeName').value.trim(),
            type: document.getElementById('knowledgeType').value,
            localPath: document.getElementById('knowledgeLocalPath').value.trim()
        };
        try {
            await this.request('/knowledge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            document.getElementById('knowledgeForm').reset();
            this.showNotice('知识库已保存');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
    }

    async generateSummary(period) {
        var dialog = document.getElementById('summaryDialog');
        var content = document.getElementById('summaryContent');
        document.getElementById('summaryTitle').textContent = period === 'week' ? '本周工作总结' : '今日工作总结';
        document.getElementById('summaryMeta').textContent = '正在整理任务和项目活动...';
        content.textContent = '生成中...';
        dialog.showModal();
        try {
            var result = await this.request('/summary/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ period: period })
            });
            document.getElementById('summaryMeta').textContent = result.basis.join(' · ');
            content.textContent = result.summary;
        } catch (error) {
            content.textContent = error.message;
        }
    }

    async loadAiSettings() {
        try {
            this.aiSettings = await this.request('/settings/ai');
            this.renderAiSettings();
        } catch (error) {
            this.aiSettings = null;
        }
    }

    renderAiSettings() {
        var settings = this.aiSettings || {};
        var status = document.getElementById('aiSettingsStatus');
        var apiKey = document.getElementById('aiApiKey');
        var baseUrl = document.getElementById('aiBaseUrl');
        var model = document.getElementById('aiModel');
        if (!status || !apiKey || !baseUrl || !model) return;
        apiKey.value = '';
        apiKey.placeholder = settings.hasApiKey
            ? '已配置 ' + settings.keyPreview + '，留空则不修改'
            : 'DeepSeek API Key';
        baseUrl.value = settings.baseUrl || 'https://api.deepseek.com/v1';
        model.value = settings.model || 'deepseek-chat';
        status.textContent = settings.hasApiKey
            ? 'AI 已配置：' + settings.provider + ' / ' + settings.model + ' / ' + settings.keyPreview
            : 'AI 未配置。今日总结、本周总结需要 DeepSeek API Key。';
    }

    async openSettings() {
        await this.loadAiSettings();
        document.getElementById('settingsDialog').showModal();
    }

    async saveAiSettings() {
        var payload = {
            apiKey: document.getElementById('aiApiKey').value.trim(),
            baseUrl: document.getElementById('aiBaseUrl').value.trim(),
            model: document.getElementById('aiModel').value.trim()
        };
        try {
            var result = await this.request('/settings/ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            this.aiSettings = result.settings;
            this.renderAiSettings();
            this.showNotice('AI 设置已保存');
        } catch (error) {
            document.getElementById('aiSettingsStatus').textContent = error.message;
            this.showNotice(error.message, true);
        }
    }

    async logout() {
        try {
            var response = await fetch('/logout', {
                method: 'POST',
                headers: this.csrfToken ? { 'X-CSRF-Token': this.csrfToken } : {}
            });
            if (!response.ok) {
                throw new Error('退出登录失败');
            }
        } finally {
            window.location.assign('/login');
        }
    }

    showNotice(message, isError) {
        var notice = document.getElementById('notice');
        notice.textContent = message;
        notice.className = 'notice visible ' + (isError ? 'error' : '');
        clearTimeout(this.noticeTimer);
        this.noticeTimer = setTimeout(() => {
            notice.className = 'notice';
        }, 3200);
    }

    escape(value) {
        var element = document.createElement('span');
        element.textContent = value == null ? '' : String(value);
        return element.innerHTML;
    }
}

new Workboard();

