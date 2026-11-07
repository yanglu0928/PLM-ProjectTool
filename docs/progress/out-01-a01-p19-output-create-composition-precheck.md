# OUT-01-A01-P19：OutputRequest Create HTTP显式Windows write组合编码前检查

- 日期：2026-11-04
- 结果：PASS_WITH_LIMITATION
- 变更：CR-OUT-015
- 前置：P18按CR-OUT-014限界完成；hosted run 41809547922 13/13成功
- 执行要求：仅GitHub hosted runner D盘临时目录运行项目程序/测试；不在用户本机或C盘运行

## 单一问题

把冻结OUTPUT_REQUEST_CREATE opt-in HTTP router接入显式Windows include_secret_write组合，同时确保默认、登录、只读App不挂载；空publisher key manifest时拒绝创建且无Request/Job/Outbox/Audit/receipt写入。

## 编码前检查证据

- P12已有严格字段/Session/CSRF/Origin/Idempotency的Create HTTP router，默认未挂载。
- P01/P02已有同UOW OutputRequest/context/Job/Outbox/Audit/receipt owner；P05 RequirementOutputSourceAdapter只消费固定RequirementVersion；P07/P09有不可变内置Template/Policy。
- P11 PluginOperation Adapter与PLG-02 SQL capability owner可复用，但查询必须有TrustedPluginSignerResolver。当前包内developer_keys.json的keys为空，因此trusted必须保持false。
- 冻结API-03 Create角色仅ProjectManager与ImplementationMember；当前ProjectAuthorization没有OUTPUT_REQUEST_CREATE policy，也无Create production Access。
- P18显式Windows write分支已提供Session/runtime/origin/license/audit/receipts组成范式，Create不得改变Cancel或默认模式。

## 选择与限制

按CR-OUT-015新增Create专用授权策略、同事务Session/CSRF Access和Windows composition factory，复用已验收Owner/adapter，只接Create endpoint。因publisher keys为空，产品路径应fail closed，不产生业务Job；合成测试不代表可信插件或正式生成。

## 编码前结论

PASS_WITH_LIMITATION。可实施显式组合和fail-closed边界；缺正式publisher trust/Output Worker/Win11实机不阻止该单项编码，但必须保留为后续Pilot/Release阻塞。
