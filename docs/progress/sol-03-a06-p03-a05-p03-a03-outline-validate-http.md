# SOL-03-A06-P03-A05-P03-A03：Outline VALIDATE HTTP 合同

日期：2026-10-24。状态：`HTTP_CONTRACT_PASS`（仅可选装配）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A03 |
| 输入基线 | 冻结 API-04 `SOL_OUTLINE_VERSION_VALIDATE` 路径/角色/200三维报告；A02已验内部命令；既有 SectionVersion VALIDATE 公开合同 |
| 前置 | Outline内部命令、Session/Origin/CSRF/幂等头、统一错误映射和可选router装配机制齐全 |
| 涉及模块 | solution API 和应用入口；不涉及DB/Review/License政策修改 |
| 验收标准 | 默认404；显式装配后冻结路径200并映射order/source/coverage、固定版本/首次观察；回放区分请求Trace与观察Trace；无可信Session/Origin/CSRF/Key、非法路径/查询/正文失败关闭；服务错误与错资源结果不泄漏；定向合同与全量回归 |
| 风险/回滚 | 只开可选路由参数，Windows运行组合尚不传入；撤路由装配可回滚。旧Audit/收据不删除，旧API无变化 |

本片不把合成事实或HTTP合同结果认作真实三维PG组合、客户批准、Gate 3或Pilot通过。

## 验证

- Outline/Section关联HTTP定向8通过、26子例：默认404、显式200及三维投影、旧观察Trace/新请求Trace、Session/Origin/CSRF/幂等键、非法路径/查询/正文、服务错误和错项目结果关闭。
- 后端全量4012通过、3跳过、6097子例。无新迁移、实际PG或浏览器验证；Windows组合仍未传入新Router。
