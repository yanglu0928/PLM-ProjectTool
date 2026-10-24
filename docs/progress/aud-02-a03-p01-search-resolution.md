# AUD-02-A03-P01：同事务受权游标解析

日期2026-09-26；Phase 2；版本0.1.0.dev0；结果INTERNAL_RESOLUTION_PASS。公开HTTP/正式密钥/发行未完成。

## 编码前检查 / Changed / Files

输入冻结API-01分页、API-02审计范围、A01当前受权读、A02完整性游标。前置已通过。一个问题：解码必须绑定本次事务核验的真实Actor，不能独立事务查身份再读。涉及AuditSearch/Position/ListContext，不变更数据库或权限角色。风险是默认窗口语义、解码错误泄漏与适配器替换查询；验收必须先权限后解析、再校验查询、最后repository读取。记录DEC-20260926-187。

authorized_read新增内部list_resolved与有效search上下文；API层search_resolver只注入独立codec/token/日期是否全部省略，不查身份、不赋予权限。License、真实Session/User和当前Project PM或DeploymentAdmin检查后，仍在同UOW中将actual Actor/Session/Scope传给解析Port。不能输入unsigned after；解析结果必须是有效AuditSearch、筛选/page_size保持、after处于有效窗口，错误拒绝且不查询。只将明确REQUEST_MALFORMED转换为安全400语义，其余依赖异常为AUDIT_UNAVAILABLE，不泄漏细节。返回有效窗口以供后续续页签名；签名时仍需移除已消费after。

## Tests / Result

- Windows11/Python3.13后端784项无失败，2项既有符号链接环境跳过；新增6项：同UOW顺序/actual绑定、拒权不解析、坏游标不查询、解析Port筛选或位置替换拒绝、签名默认窗口传给真实查询及响应、错误输入/未知异常关闭。
- validation/aud-02-a03-p01-search-resolution/verify.py复用A02真实隔离数据库种子，在受权事务中实际调用codec解析：PROJECT/DEPLOYMENT两页、默认窗口/旧范围新事件排除、会话/成员撤权仍拒绝、Audit前后不变PASS。License合成；非公开HTTP、非MVCC导出快照。
- A01五类授权事实锁与安全读取回归PASS；全量覆盖A02 codec单元合同。
- 开发wheel构建PASS，SHA256 `f75bc5db8a3499072fcc0c6dc18d1e9c4f6e2382c37df0c75fd3ec95a697a5eb`，非正式安装程序。

## Migration / API / Compatibility / Upgrade / Known Issues / Next

无Migration/冻结API/新角色/依赖变化；旧内部list/get保持。新内部上下文增加有效search，尚无外部消费者/持久数据，无数据升级动作；不装配新解析适配可回退。Windows11实测，Server2025未验、Debian13暂不验证，三平台兼容目标保留。

AUD-02-A03-P02可选GET仍待：参数白名单/默认UTC窗口/显式日期判定、Cookie错误、safe view与分页响应、错误映射、真实HTTP数据库权限验收。正式Audit专用key供给/恢复、显式平台组合、导出、完整业务Owner、Gate3/性能/UAT/可用包未完成。当前无普通人工决策待办，继续原Scope。
