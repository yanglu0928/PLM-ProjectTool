# SOL-03-A04-P03-P03-P06-A03-P05-A03：项目 GLOBAL 候选受权 Owner 与签名游标

日期：2026-10-09。结果：内部 Owner、专用项目策略与游标已在 Windows 11 隔离 PG18.6 验证；尚无 HTTP/Windows 生产路由，不等于项目页面可使用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate 2 API-04、CR-SOL-018、DEC-1152～1154、A02 内部扫描与当前来源证明。
- 单一问题：项目候选读取前必须以当前 Session、License 和项目角色授权，且翻页位置不能跨 Session/Project/页大小重放。
- 模块/实体/API/权限：Auth 当前 Session 端口、Project 专用 `SOL_GLOBAL_REFERENCE_CANDIDATE_LIST` 只读策略、Solution Owner/独立 HMAC 游标；不改 Schema/Migration/公开 API 或依赖。
- 验收：当前 ACTIVE 项目 PM/ImplementationMember 允许；客户角色、暂停成员、归档项目、跨项目、过期 Session/License 拒绝；游标篡改/跨范围/页大小变化拒绝；仅授权后调用 A02 Catalog。
- 风险：复用四角色普通 Reference 读权限或管理员 Session、未签名原始根导致重放、把历史标签当当前事实。以独立策略、固定签名族/32 字节密钥及同事务重证关闭；CREATE 仍独立重验。

## 实施与验证

新增专用 PM/ImplementationMember 只读策略（归档拒绝），`GlobalReferenceCandidateReadService` 先验证 License、当前 Auth Session 与项目成员，再解码游标并调用同事务 Catalog。游标独立 HMAC-SHA256 签名族，绑定 Session SHA-256、Project、页大小和 A02 已扫描原始根 ID；空可见页仍可继续翻页。成功结果只有 A02 最小候选与下一游标，不复用管理员 GlobalReferenceRead 详情。

单元定向 4 通过/9 子例，项目授权矩阵修正后关联定向 12 通过/753 子例，覆盖两允许角色、客户/暂停/归档/无 Session、License 和游标篡改/跨范围。Win11 隔离 PG18.6 真实 Auth Session/Project 成员/Document/Evidence/人工确认/发布账本脚本退出 0：PM 空第一页→第二页已发布候选、IM 正例、无成员项目/客户成员/暂停/归档拒绝、页大小不匹配拒绝。A02 合成来源夹具随后仍做原有来源篡改/撤权自验；此脚本不代表正式客户确认。首次后端全量发现策略精确计数测试仍为 160，修正为 161 并增加新策略角色/只读/归档断言后，全量 3490 通过、3 跳过、5375 子例通过。

兼容/升级/回滚：无数据库升级或公开 API 变更；新增项目策略和内部未挂载 Owner 可移除回滚，既有发布/Audit/收据历史保留。专用正式游标密钥尚未在目标服务账户 Vault 供给，A04 HTTP 与 A05 Windows 组合必须失败关闭地接线后才能对用户开放。Server2025、真实浏览器/性能、Gate3/发行未验；Debian13 实机按用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1152～1154 → A02 内部 Catalog → 本受权 Owner/游标 → A04 HTTP → A05 Windows。
