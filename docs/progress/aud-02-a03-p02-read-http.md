# AUD-02-A03-P02：可选审计 GET

日期2026-09-26；Phase2；版本0.1.0.dev0；结果OPT_IN_HTTP_PASS，非正式生产发行。

## 编码前检查 / Changed / Files

输入冻结API-01/02与A01受权读/A02签名cursor/A03-P01同事务解析；前置满足。一个问题：四个冻结GET的参数和安全响应接线。涉及AuditSearch/Position/View/Context、已有PM/Admin权限，不改Schema/角色。风险为Scope越权、默认窗口漂移、正文泄漏和过早生产装配。决策DEC-20260926-188、实施说明docs/api-contract/aud-02-read-http-implementation.md。

新增api/read_events.py，entrypoints/api.py可选audit_read_router；未注入依然404。严格Host/Cookie、筛选白名单/日期范围、同事务当前受权解析、签名next_cursor、安全投影/no-store与错误映射。现有page验证改classmethod以同一安全校验重核响应，不信任DTO代替权限；旧内部读合同保留。无POST/导出。

## Tests / Result

- Windows11/Python3.13后端790项无失败，2项既有Windows符号链接权限跳过。新增6项HTTP测试覆盖安全列表/详情、trace/no-store、非法日期/UUID/大小/重复未知筛选、Host/Cookie/默认404、失败映射、无写路由、签名双页/显式日期变更、部署Scope与unsafe source拒绝。
- validation/aud-02-a03-p02-read-http/verify.py：独立UUID PostgreSQL至0035，真实User/Session/PM/Admin、PROJECT三条两页无重漏、两Scope详情/列表与跨Scope404、Admin无项目旁路、签名改大小400、筛选/明确日期、合成License拒绝两Scope、撤销Session旧cursor401，Audit全表读取前后相同。仅清理本脚本临时库，无生产数据操作。
- A01五类授权事实锁/归档读取/撤权/安全投影回归PASS。开发wheel PASS：SHA256 `c19290039a947a332b77890f60a7c043ac1f9a59633af33dadc902b68342db7b`；不是可用正式安装包。

## Migration / API / Compatibility / Upgrade / Known Issues / Next

无Migration/Breaking API/角色/依赖改变，无升级动作；不注入Router可回退，审计历史不变。只Windows11实测，Server2025未验、Debian13暂不验证，目标保留。License为合成Guard，不能证明发行信任锚。正式Audit独立cursor key供给/恢复与Windows显式组合尚未完成，默认生产仍无四个路由。

下一项AUD-02-A04：Windows当前账户独立Audit cursor key安全来源与临时引用备份恢复，随后显式平台装配；后续导出/Review真实Owner/完整业务链与性能/Gate/UAT/可用包仍按原Scope实施。无普通人工决策待办。
