# PLT-PKG-01-A09-P05：Windows离线安装入口缺口与实施切分

日期：2026-10-01；状态：`READ_ONLY_GAP_REVIEW / NEXT_IMPLEMENTATION_DEFINED`。

当前Phase/WBS：Phase 2 / 本项。输入为发行规则、A09-P02统一非发行ZIP、A09-P03路径实测、A09-P04根路径前置工具、现有服务注册入口。仅做只读核查和任务切分，不改产品、数据、API/Schema/权限、系统服务或客户资产。验收为列明已有/缺失、不可越过的门禁及可独立实施的下一任务；本项没有安装PASS。回滚可撤此规划记录，不影响历史候选。

| 交付环节 | 当前可复核资产 | 缺口/本阶段门禁 |
|---|---|---|
| 候选文件 | A09-P02 ZIP：内嵌Python、前端dist、OCR原生资产、模型与19,449件Hash清单；ASCII路径四合成版面通过 | 非发行状态；包内没有正式License、公钥供给/签名链、完整NOTICE/对应源码、离线PostgreSQL18/pgvector与受控安装器 |
| 安装根 | `tools/windows_install_root_preflight.py`可在复制前拒绝非ASCII/不安全路径 | 尚未接入正式安装器；当前Tesseract在中文路径失败，不能允许任意安装路径 |
| 服务 | `apps/backend/src/plm_assistant/entrypoints/service_install_windows.py`仅对单角色显式SCM注册，既有名称不覆盖、不启动；服务计划/运行入口已存在 | 无三服务统一安装编排、目标账户/ACL/HTTPS配置与现场验证；不得把合成Windows11组合等同生产安装 |
| 数据库/升级 | Alembic至0051、隔离PG18验证及合成备份恢复；升级预检/维护锁工具 | 正式目标库/账户、人工备份与恢复、三服务/旧进程静止证据缺失；Migration放行仍关闭 |
| 发行验收 | Windows11本机合成运行记录 | Server2025正式目标账户、用户暂缓的Debian13、真实文档质量、性能/权限/License/Plugin/UAT/Gate未闭合 |

下一独立任务 `PLT-PKG-01-A09-P06`：实现**非发行候选的只读安装计划**，必须先验证安装根、固定ZIP身份、manifest与全量Hash，再给出计划/缺项；默认不复制、不注册服务、不跑Migration，不把计划视为正式安装。后续再拆为安全暂存、离线依赖/配置供给、三服务注册、重启/健康/业务验收等WBS；每步有目标账户及环境证据才授权现场操作。正式发行还须关闭许可与对应源码、签名、License及全部Release Gate。`release_eligible=false`。
