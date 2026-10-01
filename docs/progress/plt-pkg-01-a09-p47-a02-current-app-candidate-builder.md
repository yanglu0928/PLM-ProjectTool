# PLT-PKG-01-A09-P47-A02：当前应用非发行候选派生构建器

日期：2026-10-02；Phase 2 独立打包技术任务；结果：`BUILDER_CONTRACT_PASS / REAL_CANDIDATE_OPEN`。

编码前检查：输入 CR-PKG-008、SHA 固定 P45 父 ZIP、当前后端 wheel/前端 dist 构建流程。只新增非发行派生工具及单元测试，不修改产品运行代码、API、ORM、Migration、正式安装/升级或原 ZIP。父包和 wheel 路径、逐件清单、保留第三方载荷、Git 来源与失败关闭为验收核心；`release_eligible`、`legal_clearance`、`formal_tls_material_included` 永远为 false。

工具拒绝错误父哈希、清单缺失/不一致、危险或大小写冲突路径、意外 wheel 文件、缺当前 Evidence 回查/`0052`、不匹配 wheel 版本、前端 symlink/额外文件与未在 HTML 引用的资产。输出新的唯一 `NOT-FOR-RELEASE` ZIP，完全移除旧应用和旧前端文件后替换当前 wheel/dist；保留的父包第三方/运行时载荷逐件与旧清单比对，输出又逐件验证，并记录父哈希、Git commit、wheel/dist 哈希及文件数。CLI 只接受干净 HEAD 匹配的来源提交。

定向合成 3 项和原统一构建器回归 4 项均 PASS（7/7）。测试证明替换范围、未变第三方字节、恶意路径/父载荷篡改/缺 Migration/无效前端均失败关闭。没有运行真实 652 MB 父包构建，因此尚不能声称新候选已经存在、依赖兼容或随包启动成功。下一项必须先提交本工具并在干净 HEAD 上重建 wheel/dist，再生成实际非发行候选与清洁解包/PG18 烟测。

兼容：新增开发工具，无迁移。回滚弃用工具及后续派生候选，原 P45 ZIP 不变。发行法律审阅、正式信任源、三平台安装升级、AI 质量和 Gate 3～7 仍独立阻断。
