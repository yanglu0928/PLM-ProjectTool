# AUD-02-A02：审计列表签名游标

日期：2026-09-26；Phase 2；版本：0.1.0.dev0；结果：CURSOR_INTERNAL_PASS，不代表公开 HTTP、生产供给或正式程序包通过。

## 编码前检查与实现

输入：冻结 API-01 分页/API-02 审计 Scope、AUD-02-A01 当前受权查询。前置：实际 Session/当前 PM 或部署管理员、同事务 Scope 与安全投影已验证。仅处理一个问题：公共分页位置必须具有完整性和上下文绑定。决策 DEC-20260926-186。无 Schema、冻结 API、角色或技术依赖变更，无需迁移；原内部 list/get 合同保留。

新增独立 32 字节 HMAC-SHA256 key 的 AuditListCursorCodec，独立域和资源族。绑定实际受权 Actor、Session 摘要、PROJECT/DEPLOYMENT、具体项目、全部筛选/page_size、UTC 搜索窗口与末项 `(occurred_at, audit_event_id)`。严格无填充 base64url、完整字段、规范 JSON/UUID/UTC、恒定时间 MAC 校验；禁止跨族、跨 Scope、改窗口/筛选/主体重用。拒绝未签名 after 输入，错误仅 REQUEST_MALFORMED，不泄漏游标正文。

新增内部 list_with_actor，只有当前同事务实际授权完成后返回 Actor/Scope/安全页；此元数据不能作为以后请求的授权凭据。原 list 返回值不变。每一页必须重新检查当前 Session、成员和角色；签名不等于授权。

明确日期走 decode，必须一致。只有未来 HTTP 调用方证明日期全部未显式提供时才允许 decode_saved_window，保留首请求的搜索窗口，其他参数仍绑定。不能借此忽略用户改过的明确日期。固定查询窗口不是数据库 MVCC/导出快照；后提交或回填窗口内记录仍可能影响分页。HMAC 不是加密，ID/时间等元数据可解码，但不含正文、原始 Session、Key 或 actor_hint_digest。

## 验证

- Windows 11/Python 3.13：后端 778 项测试无失败，2 项既有 Windows 符号链接权限跳过。新增 7 项覆盖 UTC 等价、身份/Scope/密钥/筛选绑定、默认窗口恢复、篡改/非规范/错误字段、输入形状、非加密边界。
- validation/aud-02-a02-list-cursor/verify.py：独立 UUID PostgreSQL 库迁移至 0035，真实 User/Session/PM/部署管理员、PROJECT/DEPLOYMENT 三条两页无重漏；窗口外新事件不进入旧窗口，参数篡改拒绝；签名仍有效但成员暂停/Session 撤销后实际读取拒绝。读取前后 Audit 全表一致。仅清理本脚本创建的库。
- AUD-02-A01 五类授权锁与安全读取、RVW-02-A09-P02 受权幂等/真实死锁恢复回归通过。
- 开发 wheel 构建通过，SHA256：`22783ba297e70748e2ce37350186168ffed9f10a921fbae3dba2376a4417958f`。不是用户可安装的正式发行包。

License 为合成 Guard；本项不证明真实发行公钥或目标运行账户密钥。Server 2025 未验，Debian 13 暂不验证，三平台目标不变。

## 升级、回滚与下一项

无数据库/公开 API 升级操作；未公开的新 codec 可按代码版本回退，不改冻结历史。正式 Audit 专用密钥来源、恢复和 HTTP 日期判定尚未接线，禁止复用其他资源游标/License/Secret key。后续 AUD-02-A03 先同事务绑定实际 Actor 的 decode 适配再可选 GET；默认生产路由未开放。导出、真实业务 Review Owner、Gate 3、性能/UAT 和可用程序包仍待，不缩减原 Scope。
