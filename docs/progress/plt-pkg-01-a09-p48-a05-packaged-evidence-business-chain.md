# PLT-PKG-01-A09-P48-A05：当前候选随包 Evidence 资格业务链

日期：2026-10-02；Phase 2；结果：`SYNTHETIC_CURRENT_APP_PACKAGED_EVIDENCE_PASS`。

编码前检查：当前候选 SHA/清洁暂存、P47-A04 随包PG18迁移及既有 `EVD-01-A04-P03-A05` 合成资格验证可复用。范围只给原验证脚本增加可选的随包PG来源并新增哈希/暂存/清理包装器，不改产品模块、实体、API、权限或Migration；验收是包内 Python 真正加载应用、包内 PG18 在一次性库验证 Evidence 资格/收据/隔离/审计，现有数据不触及。风险是误使用源码包/旧PoC数据库或把 ASGI TestClient 当真实浏览器，所以可选模式核 `plm_assistant.__file__` 位于候选包内、PG来源指向清洁暂存，明确标合成范围。

真实运行 `tools/smoke_current_app_packaged_evidence.py` 退出0：先核候选 SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`、21,178载荷及暂存 manifest，随后由 `payload/runtime/python.exe -I -B` 执行既有验证脚本，复制 `payload/pgsql` 到新 D 盘 Temp 一次性集群。原脚本验证合成 Document 来源、项目 Evidence 人工资格、HTTP/ASGI 同 Key 重放与原操作号只读回查、并发单胜者、模板/跨项目/撤销/License 拒绝、Audit失败回滚和角色撤权；输出既定 PASS 标记。包装器核新临时 PG 目录清理与候选 SHA 前后不变。新增错误候选身份单元1/1；默认旧 PoC 运行方式保持不变。

这只证明包内后端/PG在合成授权替身与 TestClient 下可跑对应链；不证明正式 License、真实网络/浏览器 UI、客户数据、Windows Server 2025/Debian 13、AI质量、法律、安装升级或 UAT/Gate。兼容性：只改验证工具，无产品 API/Schema；Migration：原0052随包应用但本项无新变更；回滚：撤去可选参数/包装器，固定候选不变。`release_eligible=false`。下一项宜核对当前候选的更多端到端业务路径或回到 Phase 2 未完成模块。
