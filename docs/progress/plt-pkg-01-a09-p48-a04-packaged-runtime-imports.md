# PLT-PKG-01-A09-P48-A04：当前候选包内依赖与模块导入矩阵

日期：2026-10-02；Phase 2；结果：`CURRENT_APP_BUNDLED_RUNTIME_IMPORT_PASS / RELEASE_OPEN`。

编码前检查：输入 SHA 固定的 P47 当前候选、D 盘独立 ASCII 清洁暂存与 P47-A04 实际随包迁移。仅新增一次性包内只读审计工具和失败关闭单元测试；不改产品模块/实体/API/权限/Schema、现有库、服务或正式安装。验收是当前候选/暂存来源及21,178载荷全哈希复核、包内 Python `-I -B` 中激活依赖版本匹配和应用模块导入零失败；风险是把 Alembic 上下文入口误判普通模块、导入时读取开发机环境或把导入成功外推完整功能，故清理 `PLM_*`/Python环境变量、使用子进程超时并单列上下文专用入口。

真实运行 `tools/audit_current_app_packaged_runtime.py` 退出0：包 SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`、21,178载荷读回一致；自有后端版本 `0.1.0.dev0`，18条 `Requires-Dist` 声明中17条在无 extra 环境激活，包内分发版本全部满足，缺失/不匹配0；枚举586应用模块，585个普通模块导入错误0。`plm_assistant.migrations.env` 是唯一精确排除项：首次将其当普通模块导入时报 `AttributeError`，原因是 Alembic 在执行环境中注入 `context.config`；P47-A04 已用同一随包 Python 执行0051/0052真实迁移链，因此该排除不掩盖迁移失败。修正审计边界后重跑通过，定向错误身份测试1/1。

本测试不调用真实客户数据库、不启动服务，也不证明业务授权、AI/OCR运行质量、真实浏览器、正式信任、三平台安装升级或发行法律审查。兼容性：只读审计工具；Migration/API：无变化；回滚：弃用工具。下一独立任务应执行当前候选的受权 Evidence 业务链或其他未覆盖运行场景；`release_eligible=false`。
