# Workboard 本地任务归档助手设计

## 目标

在保留 NAS 上唯一一套 Workboard 面板的前提下，补充任务编辑、处理结果、本地资料路径、双击打开目录和完成后安全归档能力。Windows 后台助手负责访问 `D:\01WorkBoard`；NAS Workboard 继续负责网页、任务数据、接收文件和最终归档状态。

## 范围

本次包含：

- 将页面顺序调整为任务面板、项目面板、提交热力图。
- 为任务增加 `result_description`（处理结果）、`local_path`（本地文件路径）和归档状态字段。
- 点击任务卡片打开详情编辑弹窗；双击卡片通过 `workboard://` 协议请求 Windows 助手打开目录。
- 点击完成后创建归档作业，由 Windows 助手上传资料、生成本地 TXT 记录并确认完成。
- 提供 Windows 助手的一键安装、卸载和登录后自动启动脚本。

本次不包含第二套 Workboard UI、NAS SSH 自动部署、任意盘符访问、跨任务文件去重和版本历史系统。

## 总体架构

系统由两个运行单元组成：

1. **NAS Workboard**：现有 Flask 服务，继续提供 UI、SQLite 数据、任务详情、归档队列和文件接收接口。默认数据目录仍为 `/volume1/docker/workboard/data`，已完成任务资料写入 `/volume1/docker/workboard/data/docs/Done/<任务目录>/files/`。
2. **Windows 本地助手**：无独立面板的 Python 后台程序。它轮询 NAS 的归档队列，读取 `D:\01WorkBoard` 内的任务目录，上传资料，并注册 `workboard://open?...` 自定义协议以打开资源管理器。

NAS 和助手使用独立的 `WORKBOARD_AGENT_TOKEN` 鉴权。该令牌只用于助手 API，不复用网页登录密码，不返回给网页前端。

## 页面与交互

主内容区从上到下排列：

1. 当前任务
2. 项目索引
3. 提交热力图

任务卡片保留完成、记录和截图入口，并增加归档状态提示。单击卡片空白区域打开详情弹窗；单击卡片内部按钮不触发弹窗。双击卡片调用：

```text
workboard://open?taskId=<id>&path=<URL 编码后的相对路径>
```

详情弹窗可编辑任务名称、所属项目、项目号、联系人、任务日期、截止时间、备注、处理结果和本地文件路径。截图沿用现有上传能力。编辑成功后即时刷新卡片。

本地路径规则：

- 根目录固定为 `D:\01WorkBoard`。
- 数据库存储相对路径；用户可输入绝对路径，但服务端/前端会规范为根目录内的相对路径。
- 空值代表根目录本身。
- Windows 助手解析后必须确认目标仍位于根目录内；拒绝 `..`、其他盘符、UNC 路径和符号链接逃逸。

## 任务状态与完成流程

任务状态扩展为：

- `todo`：处理中。
- `archive_pending`：用户已点击完成，等待 Windows 助手。
- `archiving`：助手已领取作业并正在上传。
- `archive_failed`：归档失败，可重试；任务资料不得删除。
- `done`：NAS 已确认接收，且本地 TXT 已生成。

完成流程：

1. 用户点击“完成”，NAS 将任务标为 `archive_pending`，不立即移动现有任务文档。
2. Windows 助手轮询并以带租约的方式领取一个作业，NAS 将其标为 `archiving`。超时租约允许同一助手安全重试。
3. 助手枚举本地任务目录，跳过根目录下的 `archive` 文件夹，不跟随符号链接。
4. 文件按相对路径逐个上传到 NAS 暂存目录。NAS 拒绝绝对路径、`..` 和超出任务暂存目录的路径。
5. 全部上传完成后，助手请求 NAS 提交归档；NAS 将暂存目录原子移动到 `/volume1/docker/workboard/data/docs/Done/<任务目录>/files/`，更新任务 Markdown 和状态。
6. NAS 提交成功后，助手在本地写入归档 TXT。TXT 成功落盘后，助手删除本地任务目录中的原资料，并向 NAS 确认本地清理完成。
7. 任一步骤失败时保留本地原资料；任务显示 `archive_failed` 或等待租约恢复，可手动重试。

为避免“NAS 已接收但本地 TXT 写入失败”造成数据丢失，助手只在 NAS 确认和 TXT 原子写入均成功后删除源文件。重复上传以 `任务 ID + 相对路径 + 文件大小 + SHA-256` 判断，接口保持幂等。

## 本地 TXT 归档

固定根目录：

```text
D:\01WorkBoard\archive\YYYY\YYYYMM\
```

文件名格式：

```text
<安全任务名>_<任务开始时间>.txt
```

开始时间取 `created_at`，格式为 `YYYYMMDD_HHmmss`。Windows 非法字符替换为下划线，重名时追加任务 ID。示例：

```text
D:\01WorkBoard\archive\2026\202608\石岩欣旺达-HL_20200910_纽扣电池定位打码项目_杨珂_20260825_101530.txt
```

TXT 使用 UTF-8，保存任务 ID、名称、状态、所属项目、项目号、联系人、任务日期、创建时间、截止时间、完成时间、本地相对路径、NAS 归档路径、备注和处理结果。截图内容及截图文件不写入本地 archive。

## 数据模型

`todos` 表通过兼容性迁移新增：

- `result_description TEXT NOT NULL DEFAULT ''`
- `local_path TEXT NOT NULL DEFAULT ''`
- `archive_status TEXT NOT NULL DEFAULT ''`
- `archive_error TEXT NOT NULL DEFAULT ''`
- `archive_lease_until TEXT`
- `archive_agent_id TEXT NOT NULL DEFAULT ''`
- `archive_completed_at TEXT`

任务原有 `status` 用于业务状态；`archive_status` 保存文件归档细节。旧数据自动获得默认值，不重建数据库。

## API

网页会话 API：

- `PATCH /api/todos/<id>`：更新完整任务详情，继续要求现有会话和 CSRF。
- `POST /api/todos/<id>/complete`：由立即完成改为创建归档作业；若无本地资料，也仍由助手生成 TXT 后完成。
- `POST /api/todos/<id>/archive/retry`：将失败作业重新置为等待状态。

助手 API 使用 `Authorization: Bearer <WORKBOARD_AGENT_TOKEN>`：

- `POST /api/agent/jobs/claim`：领取或续租归档作业。
- `PUT /api/agent/jobs/<id>/files`：multipart 上传单个文件及其相对路径、大小和 SHA-256。
- `POST /api/agent/jobs/<id>/commit`：校验清单并提交 NAS 归档。
- `POST /api/agent/jobs/<id>/finish`：报告本地 TXT 与清理成功，将任务最终标为 `done`。
- `POST /api/agent/jobs/<id>/fail`：记录可展示的失败原因。

所有助手端点实施固定时间令牌比较、上传大小限制、相对路径校验和任务级目录隔离。

## Windows 助手

助手放在 `workboard/local_agent/`，仅使用 Python 标准库，避免额外运行时依赖。配置文件位于用户目录之外的安装目录，至少包含 Workboard URL、代理令牌和根目录。日志不得记录令牌。

安装脚本执行：

- 创建本地虚拟环境或使用明确指定的 Python。
- 写入用户级 `workboard` URL Protocol 注册项。
- 创建仅当前用户的登录启动项。
- 创建默认目录和 `archive` 目录。

协议处理进程只负责校验并调用资源管理器；轮询进程负责归档。两者复用同一套路径安全函数。

## 错误处理与可恢复性

- 助手离线：任务停留在“等待归档”，网页可继续使用。
- 网络中断：保留本地文件；再次领取后按清单跳过已确认文件。
- NAS 空间不足或校验失败：任务显示失败原因，不删除本地文件。
- 本地目录不存在：仍生成 TXT，NAS 中保留任务记录，并在结果中注明“本地目录不存在”；任务可由用户确认后重试或无资料完成。
- 页面无法启动自定义协议：显示安装本地助手的提示，不影响任务编辑。
- 任何删除操作仅针对已解析且验证位于 `D:\01WorkBoard` 下的任务目录；根目录和 `archive` 永不递归删除。

## 测试与验收

服务端自动测试覆盖：

- SQLite 旧库迁移和新字段序列化。
- 任务详情更新、字段长度与路径验证。
- 完成动作只创建归档作业，不提前标记完成。
- 助手令牌鉴权、租约、重试和幂等上传。
- 路径穿越、超限文件、哈希不一致和提交清单缺失。
- 成功提交后的 NAS 目录结构及任务状态。

助手自动测试使用临时目录覆盖：

- 默认路径与相对路径解析。
- archive 排除、符号链接拒绝和根目录保护。
- TXT 年/月结构、文件名清理和字段内容。
- 上传失败、TXT 写入失败时不删除源资料。
- 完整成功流程后才清理源资料。

前端验收覆盖：

- 三个面板顺序正确。
- 单击编辑、双击打开与按钮点击互不冲突。
- 处理结果和本地路径可保存并重新加载。
- 等待、归档中、失败和完成状态文案清晰。

## 部署与交付

NAS 手动复制范围为 `server.py`、`static/` 以及必要的新服务端模块；不得覆盖 NAS 上的 `.env`、`docker-compose.yaml` 和 `data/`。NAS `.env` 需手动增加强随机 `WORKBOARD_AGENT_TOKEN` 后重建容器。

Windows 端单独复制本地助手目录，运行安装脚本并输入 Workboard URL 与同一代理令牌。令牌不提交到 Git，不写入归档 TXT。
