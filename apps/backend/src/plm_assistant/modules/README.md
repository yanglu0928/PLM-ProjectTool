# Runtime modules

客户运行模块在进入对应 WBS 时创建为 `plm_assistant.modules.<module>`。每个模块使用 `api/application/domain/infrastructure` 固定层次；跨模块只可导入目标模块的 `application.public`。

22 个模块及允许依赖以 `docs/architecture/module-directory-manifest-v1.json` 为机器规范。不得创建未进入冻结 Architecture 的新模块。
