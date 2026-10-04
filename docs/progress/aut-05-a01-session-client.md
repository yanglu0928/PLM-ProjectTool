# AUT-05-A01：Web Auth Session 客户端

2026-09-27；0.1.0.dev0；状态CLIENT_CONTRACT_PASS / PAGE_AND_LIVE_BROWSER_PENDING。

## 编码前检查

- Phase2 / AUT-05-A01；正式实施方案Phase2 Auth和SYS-001登录，分解新增客户端子任务，不扩大Scope。
- 输入：冻结API01/02、CR-AUT007受限Session、现有login.py/session.py/session_view.py，Vue基础壳。
- 前置：实际Windows登录/查询/续期/注销已验，允许独立开发客户端；正式信任/性能/Gate不能据此通过。
- 模块：frontend/modules/auth；实体仅安全SessionView内存投影，无DB/ORM/Migration。
- API：POST login、GET session、POST session:renew、POST logout，原路径/字段/CSRF/Key不变。
- 权限：后端始终最终授权；受限true必须NONE+空项目；未知枚举或畸形响应失败关闭，不从UI授予真实权利。
- 本次目标：实现可复用客户端，不同时实现页面、改密或管理UI。
- 验收：same-origin相对路径/Cookie浏览器自动携带；CSRF仅实例私有内存；写请求互斥、无自动重试、固定安全错误、不回显服务器message或transport异常；正常/受限/畸形/超时/续期/注销/刷新失CSRF测试；前端全测试/typecheck/build。
- 风险：GET不返回CSRF，刷新后不能虚构或从Cookie/持久存储恢复；renew超时可能已旋转Cookie；logout故障可能已生效。所有失败清客户端身份/CSRF，必要时重新登录，不冒充服务器撤销。浏览器字符串无法保证物理擦除，仅不保留密码；限制请求超时，不声称取消服务器提交。
- 差异决策：A01仅使用既有合同，无新安全机制/依赖/接口，无CR。刷新仅恢复只读身份，renew/logout缺CSRF本地拒绝，页面后续明确重新登录；如要免重新登录获取CSRF须另CR，不静默改GET。
- 迁移/回滚：无需DB升级；撤客户端文件恢复壳，已存在server会话不因此撤销。生产同源部署/浏览器真实链、CSRF刷新体验、页面/改密/包仍待后续任务。

预计文件：sessionClient.ts及spec、本进度/报告/决策/STATUS/版本说明。正式实现前以上检查已记录，按持续授权直接执行。

## 执行结果

新增SessionClient及43个客户端参数化用例；四固定相对路径、Cookie浏览器携带、no-store/redirect:error、有界Abort、实例互斥。安全SessionView只返回已校验字段且深度冻结（对象/项目列表/项目项），CSRF使用JS私有字段，不回给组件、不读写Cookie或Storage；密码不在实例内保留，但JS字符串/浏览器传输无法承诺物理擦除。续期必须同一User并更新CSRF，注销必须caller原Key/严格revoked=true；异常不自动重试，所有状态不确定失败清本地投影/CSRF而非伪造服务端撤销。

UTC时间校验实际日期/格式/idle≤absolute，UUID非零、角色严格原运行枚举、受限true必须NONE及空项目；项目去重与附加字段剥离。固定安全错误与对应HTTP状态，不显示服务端message、details或transport异常。current调用清CSRF并只恢复只读身份，下一页面必须提示重登，不能把canSubmit作为权限判断。

Windows11 Node24.17.0/pnpm11.19.0：完整前端52/52 PASS（原9+新43），typecheck/build PASS。初轮50/50与build通过后增加续期错User及错误码/HTTP状态不一致两项，完整重跑52/52/typecheck/build通过。无新增依赖/锁文件/API/Schema/后端变更。

build仍32modules/JS88832bytes/CSS3434bytes，因为客户端尚未被页面导入；**不能称登录界面已可用或客户端已进入产物**。后端unit/PG/19链coverage/HTTP性能/wheel未重跑，本批全部fetch是契约测试模拟，不冒充真实后端或浏览器验证。既有coverage、性能FAIL、正式trust/Gate不改写。

下一AUT-05-A02：登录/当前身份页面及中文重登/错误/受限状态，与客户端接线、单提交、表单密码清理；同源开发代理需保留Origin/Host并核实际设置，不添加生产CORS/测试信任回退。实际后端/浏览器/正式部署验证独立后续任务。
