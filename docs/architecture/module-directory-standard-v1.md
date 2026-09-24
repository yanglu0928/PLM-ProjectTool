# 模块目录规范 V1

## 状态

`WBS-1.01_PASS / DIRECTORY_STANDARD_V1 / GATE_2_BASELINES_ENFORCED / NO_RUNTIME_CODE`

|字段|值|
|---|---|
|WBS|`1.01 定义模块目录规范`|
|日期|2026-09-23|
|架构基线|`ARCH-CANDIDATE-V1`，Gate 2 冻结内容提交 `64cdf09`|
|数据/API 输入|`DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1`、`API-CONTRACT-CANDIDATE-V1`|
|机器目录|`module-directory-manifest-v1.json`|
|下一 WBS|`1.02 FastAPI app factory`|

本规范只固定仓库目录、Python 命名空间、模块层次、依赖入口和测试镜像，不创建 FastAPI App、Vue App、ORM、Migration、Router 或业务实现。

## 顶层布局

```text
apps/
├─ backend/
│  ├─ src/plm_assistant/
│  │  ├─ entrypoints/          # API / Worker 进程入口；不得承载业务规则
│  │  ├─ modules/              # 22 个客户运行模块
│  │  └─ shared/               # 最小技术内核与跨模块 Contract；禁止共享业务模型
│  └─ tests/
│     ├─ unit/
│     ├─ contract/
│     ├─ integration/
│     ├─ permission/
│     └─ architecture/
├─ frontend/
│  └─ src/
│     ├─ app/                  # 路由、启动和全局 Provider
│     ├─ modules/              # 按业务能力组织的页面与交互
│     └─ shared/               # 无业务所有权的 UI 基础设施
tools/
└─ developer-workbench/        # License/Plugin 签名和 Release 工具；物理隔离
```

`apps/backend` 是一个可安装 Python `src` layout 包；FastAPI 与 Worker 只拥有不同 entrypoint，共用 Application/Domain，不复制第二套业务模块。`apps/frontend` 只能通过冻结的 REST/JSON、multipart 与 SSE Contract 访问后端。`tools/developer-workbench` 不属于客户运行包、不得访问客户运行数据库或项目资料。

## 后端模块模板

每个客户运行模块按需创建以下固定目录；未进入实现 WBS 的模块不创建空占位包：

```text
apps/backend/src/plm_assistant/modules/<module>/
├─ api/                         # Router、请求/响应映射；只调用本模块 Application
├─ application/
│  ├─ commands/                # 写用例
│  ├─ queries/                 # 读用例
│  ├─ ports/                   # Repository/Gateway 抽象
│  └─ public/                  # 唯一允许跨模块导入的 Application Contract
├─ domain/                      # Aggregate、Value Object、Domain Service/Event
└─ infrastructure/             # SQLAlchemy、文件、Provider、子进程等 Port Adapter
```

Python 导入根固定为 `plm_assistant`。模块内依赖规则：

```text
api → application → domain
infrastructure → application ports + domain
entrypoints/platform composition root → api + infrastructure
domain → 不依赖 API、ORM、FastAPI、厂商 SDK 或其他模块内部实现
```

跨模块只允许导入目标模块的 `application.public` 或冻结的共享 Contract；禁止导入目标模块的 `domain`、`infrastructure`、ORM 或私有 Application 实现。Repository/Gateway 抽象位于本模块 `application.ports`，实现位于本模块 `infrastructure`。

## 客户运行模块

目录名与 Owner 名固定为以下 22 个 ASCII `snake_case` 名称：

```text
platform auth project workflow document evidence review trace audit jobs
ai rag capability handover survey requirement prototype solution plan
output plugin license
```

依赖白名单以 `module-directory-manifest-v1.json` 为机器规范，内容必须与冻结 Architecture 的“允许依赖矩阵”一致。未列出的依赖全部禁止。`developer_workbench` 不计入 22 个运行模块，也不能被运行模块导入。

## shared 边界

`plm_assistant.shared` 只允许放置：

- 与业务无关的类型、时间/UUID 抽象和进程内 Contract 基础；
- 统一错误、Trace Context、分页/幂等等冻结公共协议的基础表示；
- 无模块所有权、无数据库写权限、无业务状态的技术工具。

禁止把 Aggregate、Repository 实现、业务枚举、权限规则或“大家都要用”的业务 Service 移入 shared。存在 Owner 的概念必须归属 Owner 模块并通过 `application.public` 暴露。

## 前端目录边界

- `src/app` 负责启动、路由、错误边界与全局 Provider，不保存业务事实。
- `src/modules/<feature>` 按用户能力组织，不要求与数据库表或后端内部类一一对应。
- `src/shared` 只包含通用组件、HTTP/SSE Client、格式化与设计 Token。
- 前端不得访问数据库、文件系统、AI Provider 或 Plugin stdio；不得复制后端权限判断作为可信安全边界。

## 测试镜像

后端测试按行为类型分层，并在需要时镜像模块名：

```text
tests/unit/<module>/
tests/contract/<module>/
tests/integration/<module>/
tests/permission/<module>/
tests/architecture/
```

`architecture` 测试负责模块名单、依赖白名单、禁止导入、Developer Workbench 隔离和实际 OpenAPI/Contract diff。测试不得通过跨模块 ORM fixture 绕过公开 Application Port。

## 命名与 Windows 兼容

- 仓库目录、Python package 和 TypeScript module 使用小写 ASCII `snake_case`；Vue 组件文件可使用 `PascalCase.vue`。
- Git 中禁止只依赖大小写区分的同名路径；导入大小写必须与磁盘一致。
- 禁止 Windows 设备名 `CON`、`PRN`、`AUX`、`NUL`、`COM1`～`COM9`、`LPT1`～`LPT9`。
- 单个目录名不超过 40 字符；受控源码路径建议不超过 220 字符，避免安装和打包环境的路径兼容问题。
- 机器 manifest 中统一使用 `/`，运行时才由 `pathlib` 转换为平台路径；不得手工拼接 `\\`。

## 创建规则

1. 只有进入对应 WBS 时才创建模块 package，不提交 22 组空目录或空 `__init__.py`。
2. 新模块不属于普通目录调整；它会改变冻结 Architecture/Scope，必须走 L3 Change Request。
3. 模块内新增子目录属于 L2，可登记后执行，但不能改变固定层次方向或公开边界。
4. `api`、`application`、`domain`、`infrastructure` 中不得出现客户数据、Secret、本地绝对路径或运行日志。
5. 正式实现提交必须同时包含对应测试目录；Schema/API 变更继续遵守冻结基线和各自变更规则。

## 1.01 验收

- 顶层 backend/frontend/developer-workbench 信任区清晰且已有可追溯入口：PASS。
- 22 个客户运行模块与冻结 Architecture、65 Root 的 API Owner 集合一致：PASS。
- 模块模板与 `API → Application → Domain / Infrastructure Adapter` 依赖方向明确：PASS。
- 允许依赖矩阵完整、无未知模块、自依赖或环：PASS。
- Developer Workbench 与客户运行包物理隔离：PASS。
- 测试镜像、Windows 路径和大小写规则明确：PASS。
- 机器校验 6/6 PASS，未创建运行代码、API、Migration 或外部调用：PASS。
