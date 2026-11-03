undefined

## A08首段实现与偏差记录（实施后代码复核，2026-11-03）

- 首段实现提交：f116604885d942fb9f2fa7d3d471d03c9652c9f9；GitHub hosted run [41597429890](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41597429890) 13/13 jobs成功，含后端全量/wheel、前端、PG18父包及A35/A17/A34既有集成链。
- 独立分层复核发现：Plugin Application 的 package_import_spool.py 直接导入 Document.infrastructure.LocalFileStorage/LocalStorageError。测试通过但违反模块边界；应用层不能反向依赖其他业务模块基础设施。
- 修复前计划：先定义Plugin自身的 staging storage Protocol/port，让Application层只依赖该抽象；生产Document storage可在组合根通过结构化adapter注入。若无法维持依赖方向，改用平台通用端口，不能保留跨业务层具体依赖。
- 影响：不改变API、DB Schema、包格式、文件路径/内容校验行为；仅依赖方向和构造验证调整。无需数据迁移。
- 回滚：保留旧提交历史；若修正导致验收失败，回滚新适配改动至有边界问题的内部实现并保持A08未完成（不可将其装入默认生产组合）。
- 验证：修复后运行新增定向测试、全后端/wheel与完整hosted云验收；继续确认runner只用D盘临时工作区。
