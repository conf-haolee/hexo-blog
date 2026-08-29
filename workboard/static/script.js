class Workboard {
    constructor() {
        var meta = document.querySelector('meta[name="workboard-base-path"]');
        var basePath = meta ? meta.content.replace(/\/$/, '') : '';
        this.api = (basePath ? basePath : '') + '/api';
        this.projects = [];
        this.todos = { todo: [], done: [], limits: { maxTodoItems: 12 } };
        this.csrfToken = null;
        this.noticeTimer = null;
        this.todoScreenshotFile = null;
        this.editingTodo = null;
        this.todoClickTimer = null;
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
        document.getElementById('searchInput').addEventListener('input', () => this.renderProjects());
        document.getElementById('todoForm').addEventListener('submit', event => {
            event.preventDefault();
            this.createTodo();
        });
        document.getElementById('projectForm').addEventListener('submit', event => {
            event.preventDefault();
            this.createProject();
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
                this.request('/contributions')
            ]);
            this.csrfToken = results[0].csrfToken || null;
            this.projects = results[2];
            this.todos = results[3];
            this.contributions = results[4] || {};
            this.renderAll();
            this.setStatus('在线', true);
            document.getElementById('lastUpdated').textContent = '更新于 ' + new Date().toLocaleString('zh-CN');
        } catch (error) {
            this.setStatus('服务不可用', false);
            this.showNotice(error.message, true);
        }
    }

    renderAll() {
        this.renderStats();
        this.renderProjectSelect();
        this.renderProjects();
        this.renderTodos();
        this.renderHeatmap();
    }

    renderStats() {
        var projectCount = this.projects.length;
        var todoCount = Array.isArray(this.todos.todo) ? this.todos.todo.length : 0;
        var commitCount = this.projects.reduce((total, project) => {
            return total + (project.gitInfo && project.gitInfo.commits ? project.gitInfo.commits.length : 0);
        }, 0);
        document.getElementById('projectCount').textContent = projectCount;
        document.getElementById('todoCount').textContent = todoCount;
        document.getElementById('commitCount').textContent = commitCount;
        document.getElementById('todoLimit').textContent = todoCount + ' / ' + (this.todos.limits.maxTodoItems || 12);
        document.getElementById('todoProgress').style.width = Math.min(100, todoCount * 100 / (this.todos.limits.maxTodoItems || 12)) + '%';
    }

    setStatus(text, online) {
        document.getElementById('serverStatus').textContent = text;
        document.getElementById('serverStatusDot').className = 'status-dot ' + (online ? 'online' : 'offline');
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

    renderProjects() {
        var query = document.getElementById('searchInput').value.trim().toLowerCase();
        var filtered = this.projects.filter(project => {
            var text = [
                project.name,
                project.description,
                (project.tags || []).join(' '),
                (project.categories || []).join(' ')
            ].join(' ').toLowerCase();
            return !query || text.indexOf(query) >= 0;
        });
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
        var tags = (project.tags || []).map(tag => '<span class="tag">' + this.escape(tag) + '</span>').join('');
        var categories = (project.categories || []).map(tag => '<span class="category">' + this.escape(tag) + '</span>').join('');
        var commits = this.projectCommitList(project);
        if (project.localPath) {
            card.classList.add('openable');
            card.title = '双击打开本地路径：' + project.localPath;
        }
        card.innerHTML =
            '<div class="card-top"><span class="project-id">#' + project.id + '</span>' +
            '<span class="path-label">' + this.escape(project.pathLabel || '路径未配置') + '</span></div>' +
            '<h3>' + this.escape(project.name) + '</h3>' +
            '<p class="muted description">' + this.escape(project.description || '暂无描述') + '</p>' +
            '<div class="tag-row">' + tags + categories + '</div>' +
            '<div class="project-meta">' +
            '<span class="path-state ' + (pathStatus.nasExists ? 'good' : '') + '">NAS ' + (pathStatus.nasExists ? '可用' : '未连接') + '</span>' +
            '<span class="path-state ' + (git ? 'good' : '') + '">' + (git ? this.escape(git.branch) : '无 Git 信息') + '</span>' +
            '</div>' +
            commits;
        card.addEventListener('dblclick', event => {
            event.stopPropagation();
            this.openProjectFolder(project);
        });
        return card;
    }

    projectCommitList(project) {
        var gitInfo = project.gitInfo || {};
        var commits = gitInfo.commits ? gitInfo.commits.slice(0, 3) : [];
        if (!commits.length) return '';
        return '<div class="project-commit-list">' + commits.map(commit => {
            return '<div class="project-commit">' +
                '<span class="commit-message">' + this.escape(commit.message || '') + '</span>' +
                '<span class="commit-meta">' + this.escape(commit.relative_date || commit.date || '') +
                ' · ' + this.escape(commit.hash || '') + '</span>' +
                '</div>';
        }).join('') + '</div>';
    }

    renderTodos() {
        var container = document.getElementById('todos');
        container.innerHTML = '';
        var items = this.todos.todo || [];
        if (!items.length) {
            container.innerHTML = '<p class="empty">暂无任务。</p>';
            return;
        }
        items.forEach(item => {
            var card = document.createElement('article');
            card.className = 'todo-item';
            card.dataset.todoId = String(item.id);
            var due = item.dueAt ? '<span>截止 ' + this.escape(item.dueAt.replace('T', ' ')) + '</span>' : '';
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
                '<div><h3>' + this.escape(item.name) + '</h3><p class="muted">' + this.escape(projectName) +
                (item.projectNumber ? ' · ' + this.escape(item.projectNumber) : '') + '</p></div></div>' +
                '<div class="todo-detail-row"><span>联系人 ' + this.escape(item.contact || '未填写') + '</span><span>日期 ' + this.escape(item.taskDate || '-') + '</span></div>' +
                (item.localPath ? '<div class="todo-detail-row"><span>本地 ' + this.escape(item.localPath) + '</span></div>' : '') +
                (item.notes ? '<p class="todo-notes">' + this.escape(item.notes) + '</p>' : '') + screenshot +
                (archiveLabel ? '<div class="archive-status' + archiveClass + '">' + archiveLabel + '</div>' + archiveError : '') +
                '<div class="todo-actions"><span class="progress">' + item.progress + '%</span>' +
                '<button class="link-button document-button" type="button">记录</button>' +
                '<button class="link-button complete-button" type="button">完成</button>' +
                '</div><div class="todo-due muted small">' + due + '</div>';
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

