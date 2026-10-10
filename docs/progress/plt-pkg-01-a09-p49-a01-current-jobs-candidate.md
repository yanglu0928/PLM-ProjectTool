# P49-A01：当前 Jobs 前端非发行 Windows 候选

2026-10-02 / Phase 2 / `NON_RELEASE_BUILD_EXTRACT_IMPORT_MIGRATION_PASS`。输入：`CR-PKG-008` 可追溯派生方案，固定 P45 父ZIP SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，干净源码提交 `2f888b5d2e726b8b7bf2d028eb1db4bf8435b5c6`；新增项目/Admin Jobs 只读列表与详情，原 P47 ZIP 因前端资产旧而不再代表当前应用。正式 Gate/Release 未关闭。

编码前检查：仅重建后端wheel/前端dist，并用 P47 已验证构建器从固定父包派生新的 Windows11 **非发行** ZIP；不改产品实体、API、Schema、权限、License 机制、正式安装根、服务或既有数据库。验收是来源提交与构建物固定、父载荷逐项保留、新包唯一ID/哈希、清洁解包全量读回、包内 Jobs 路由与前端资产一致、随包依赖/模块导入及0052临时库升级。风险是版号仍 `0.1.0.dev0` 而内容变化，故须以唯一候选ID/SHA区别，保留历史包；不上传未审法律材料或秘密。

输出 ZIP 位于本地 Git 忽略区 `artifacts/package-prep/windows11/current-app-candidate-c34e03648b8c/NOT-FOR-RELEASE-windows11-current-app.zip`，652,192,292字节，SHA-256 `26cf6c7c5b4eb2c63673c4f792aee273ff5169a3c3431c8cf5c65d566a87878d`。后端wheel SHA `5da379b688ccd85f8b7f4273d5d2c07fbb5c2e939bf9e440213b1f15b096edbd`；新包21,178载荷、20,573父包非应用文件保留。前端 JS/CSS 为 `index-DtQS-oM2.js` / `index-BRxCxxXE.css`。新包 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`。

独立清洁解包于 `D:\PLMTemp\plm-current-app-stage-p49c34e03648b8c`，完整SHA与文件全集读回退出0、原ZIP SHA保持；候选及暂存未用于正式安装。包内Python `-I -B` 导入原Jobs列表/详情路由，前端index/JS/CSS三项与当前构建逐项同Hash、编译JS有Jobs路由/页面标记、两份后端Jobs路由与当前源码同Hash，迁移0052存在。包内18条依赖声明/17条激活依赖版本匹配、586模块中585普通导入无错误（Alembic专用env按上下文排除）。包内Python/PG18在一次性临时库执行0051→0052保留已有配置、0052→0051→0052及空库直升，pgvector 0.8.6，既有库未动。构建器定向3/3、清洁解包边界1/1；前端全量1126/typecheck/build与上一项一致，P07真实PG Jobs读链另有独立证据。

Changed/Files：仅新非发行候选和暂存（均Git忽略）及本进度/STATUS/CHANGELOG。Migration/API/依赖变更：本项无，候选包含既有0052；升级不得将候选直接覆盖正式根，需独立备份/维护/安装验收。回滚为弃用新候选，P45/P47历史包不变。

尚未验证本候选的合成HTTPS/License运行链、真实浏览器/正式信任、产品LICENSE/NOTICE法律审阅、Windows Server2025/Debian13安装、AI质量、性能/UAT和Gate3～Release。下一项 P49-A02 在隔离副本执行随包HTTPS/License与Jobs只读路由 smoke，仍不得冒充正式发行。
