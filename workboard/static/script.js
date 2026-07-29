class Workboard {
    constructor() {
        var meta = document.querySelector('meta[name="workboard-base-path"]');
        var basePath = meta ? meta.content.replace(/\/$/, '') : '';
        this.api = (basePath ? basePath : '') + '/api';
        this.projects = [];
        this.todos = { todo: [], done: [], limits: { maxTodoItems: 12 } };
        this.csrfToken = null;
        this.noticeTimer = null;
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
        document.getElementById('projectCreated').value = new Date().toISOString().slice(0, 10);
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
        var select = document.getElementById('todoProject');
        select.innerHTML = '<option value="">临时工作</option>';
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
            (git ? '<div class="commit-line">' + this.escape(git.last_commit.message) + '<span>' + this.escape(git.last_commit.relative_date) + '</span></div>' : '');
        return card;
    }

    renderTodos() {
        var container = document.getElementById('todos');
        container.innerHTML = '';
        var items = (this.todos.todo || []).concat(this.todos.done || []);
        if (!items.length) {
            container.innerHTML = '<p class="empty">暂无任务。</p>';
            return;
        }
        items.forEach(item => {
            var card = document.createElement('article');
            card.className = 'todo-item ' + (item.status === 'done' ? 'done' : '');
            var due = item.dueAt ? '<span>截止 ' + this.escape(item.dueAt.replace('T', ' ')) + '</span>' : '';
            card.innerHTML =
                '<div class="todo-main"><button class="check" type="button" aria-label="完成任务">' + (item.status === 'done' ? '✓' : '') + '</button>' +
                '<div><h3>' + this.escape(item.name) + '</h3><p class="muted">' + this.escape(item.projectName || '临时工作') + '</p></div></div>' +
                '<div class="todo-actions"><span class="progress">' + item.progress + '%</span>' +
                '<button class="link-button document-button" type="button">记录</button>' +
                (item.status === 'done' ? '' : '<button class="link-button complete-button" type="button">完成</button>') +
                '</div><div class="todo-due muted small">' + due + '</div>';
            card.querySelector('.document-button').addEventListener('click', () => {
                window.open(this.api + '/todos/' + item.id + '/document', '_blank', 'noopener,noreferrer');
            });
            if (item.status !== 'done') {
                card.querySelector('.complete-button').addEventListener('click', () => this.completeTodo(item.id));
                card.querySelector('.check').addEventListener('click', () => this.completeTodo(item.id));
            }
            container.appendChild(card);
        });
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
        var name = document.getElementById('todoName').value.trim();
        var projectId = document.getElementById('todoProject').value;
        var dueAt = document.getElementById('todoDue').value;
        try {
            await this.request('/todos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, projectId: projectId || null, dueAt: dueAt || null, progress: 0 })
            });
            document.getElementById('todoForm').reset();
            this.showNotice('任务已创建');
            await this.load();
        } catch (error) {
            this.showNotice(error.message, true);
        }
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

