# AUD-03-A03：导出意图与当前授权合同

日期2026-09-26；Phase2；版本0.1.0.dev0；结果INTERNAL_CONTRACT_PASS，不是权限实现/导出持久化/HTTP/Worker PASS。

## 编码前检查 / Changed / Files

输入冻结API-02导出、API-03任务、DM-02归档维护例外、A01导出设计和A02部署Job Scope补齐。前置满足，只固定一个内部合同：受控导出请求与Worker当前权限要求。涉及AuditExportSpec/AuthorityRequest，无Schema/公开API/角色/依赖变化。DEC-20260926-192，新增application/export_contract.py与8项unit。

Spec固定PROJECT/DEPLOYMENT、明确起止时间和已有安全过滤，最大31天；PROJECT非零项目ID，DEPLOYMENT无项目。不接受GLOBAL、cursor/page_size、自由字段列表/路径/厂商endpoint/Session/CSRF/payload。用途code：SECURITY_REVIEW、COMPLIANCE_REVIEW、PROJECT_GOVERNANCE、INCIDENT_INVESTIGATION；部署范围不接受项目治理用途。后续UI应提示选择对应原因，不要求客户填写技术信息，不把自由说明或可能含Secret内容复制进Audit/Job。格式JSONL_V1、投影AUDIT-EVENT-SAFE-V1、政策AUDIT-EXPORT-POLICY-V1由服务器固定，不是客户端选择模型/字段。

fingerprint包含全Spec、规范UTC/UUID及格式/投影/政策版本；等价时区不改变，同一请求任何筛选/目的/范围变化改变。它不是签名、授权或capture集合，实际请求必须另外绑定服务器核验的请求Actor和幂等namespace。actor_id筛选不是授权Actor。as_search固定内部batch size=200、无after，仅作后续读取工具，不可冒充snapshot。

AuthorityRequest只持ExportRef、原Actor、固定Scope/Project及CAPTURE/RENDER/PUBLISH阶段，不包含authorized bool/凭据。Port assert_current要求真实Auth/Project当前事实锁持至调用方事务结束，违例抛错；Port声明没有默认实现、成功fallback或可复用能力证明。

## 当前授权及归档设计（尚需后续实现验收）

1. 接受请求：真实Session/CSRF/User、License、部署Admin或项目当前PM/member/department，Scope来自路径；受审目的和固定search再验，同事务持久幂等/Audit/Job。归档项目导出是冻结维护例外，不允许普通新业务Job，不借更改Project状态实现。
2. Worker：先由Audit Owner绑定持久Export的真实原Actor/Scope，再使用Auth公开当前User事实Port与Project实时权限。锁实际启用User/当前部署角色或Project/member/department，必要账户/角色改变即拒；License与租约fencing/取消状态各自重验。历史UUID、purpose、Job lease和DTO不能证明当前访问。
3. 不将原始Session/CSRF/Token hash存Export或Job。登出/原Session自然过期不自动伪装为取消已受理Job；原Actor账户/业务权限撤销必须阻止后续处理和发布。用户取消由真实任务命令实现，不能假称已有接口。实际结果查询/下载仍每次核验新请求的实时Session和权限，Worker通过不授予结果访问。
4. 归档PM的export维护权限需独立操作策略与真实锁验证；本项不增加未经实际编排使用的授权条目。Auth当前User无Session Worker Port、实际assert_current适配、Owner固定绑定/再验在后续Task实现，不能用空Port/no-op合成通过权限Gate。
5. 所有政策/投影版本必须写入未来Export/capture metadata；未来变更新版本且保留旧读回规则，不用当前代码常量重写旧意图/指纹或幂等结果。格式版本不允许客户端任意化。

## Tests / Result / Migration / API / Compatibility

Win11/Python3.13后端805项无失败，2项既有符号链接权限跳过；8项新测试实际覆盖purpose/scope/UUID、31天/aware/filter、UTC等价、全部意图指纹绑定、冻结最小字段/腐损再验、Worker阶段/坐标合同。仅验证纯内部合同，没有新真实权限、数据库、HTTP或导出文件验收；不据此宣称权限coverage/Gate通过。

开发wheel构建PASS，SHA-256：`25a46e92b598ca135824a1691403531c4f92a9aa1b8d2f5371c5cb423b0b8dbd`；非正式可用包。无Migration/冻结API/角色/依赖变化，无数据升级动作；未装配可回退代码，原查询不变。Server2025未验、Debian13暂不验证，三平台目标保留。正式账户材料、完整业务Owner、AI质量/性能/Gate/UAT/可用包仍待。

## Next

AUD-03-A04 / CR-AUD-001：实施前记录不可变导出/capture集合Schema差异、迁移/回滚/验证，先根实体/来源固定与seal合同，之后真实请求和Worker授权/Job编排。POST保持关闭，不用分页查询代替固定集合。
