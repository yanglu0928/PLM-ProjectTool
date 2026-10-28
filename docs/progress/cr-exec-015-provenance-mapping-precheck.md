# CR-EXEC-015 编码前检查：A17 provenance 文件布局映射

- 日期：2026-10-28
- 唯一问题：A17 的精确隔离布局映射拒绝已保留在候选包中的 provenance 文件。
- 云端证据：run 40643422039 的 packaged A17 job 栈在 target_name 报 unmapped candidate payload family；父包与候选包 SHA、构建和临时 PG 检查已通过。
- 影响范围：只读的 Windows install rehearsal 源到临时目标布局；不改产品 API/Schema/依赖或候选 payload。
- 计划改动：显式映射 provenance/ 后代至 app/package-metadata/provenance/，保留 safe_name 检查、哈希检查、大小写碰撞拒绝和 unknown-family fail closed。
- 安全与数据：只处理仓库代码和合成数据；不会使用本机资料、秘密、License 私钥。
- 验收：定向映射/碰撞测试与 hosted A17 Edge/HTTPS/PG full flow；失败保留记录并修复。
- 回滚：移除单一映射及测试；仅触及隔离 runner 暂存。
