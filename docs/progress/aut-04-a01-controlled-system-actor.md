# AUT-04-A01 受控系统身份来源

## 编码前检查

- 当前Phase：Phase2 Platform Core。
- 当前WBS：AUT-04-A01，AUD原子发布独立前置。
- 输入基线：冻结64cdf09 / ADR007 / CR-AUT-004 / 已验证Windows Vault和加密备份。
- 前置任务：上述来源与生命周期已具备；原子发布暂停至此Port验证，不以假身份绕过。
- 涉及模块：Platform Application/Infrastructure、Windows entrypoint。
- 涉及实体：只读SystemActor UUID，无User/Schema变更。
- 涉及API：内部assert_current；无HTTP、Job载荷或冻结API变更。
- 涉及权限：当前Windows运行账户Vault；系统UUID不是业务授权，原actor权限必须另验。
- 验收标准：稳定固定域/引用、缺失变化关闭、实际临时Vault丢失/加密恢复保原身份、单元回归与wheel。
- 风险：正式运行账户材料、账户隔离与三平台仍待；不能声称完整发布/可用安装包。

## 执行结果

限定范围PASS：新增Platform Application `SystemActorPort.assert_current()`、只读Windows adapter和显式factory。固定专用引用/域，UUID由材料稳定派生，每次核完整摘要，缺失/换材料/异常关闭。不存原材料、无业务授权、不自动供给或装配Worker。

Windows11/Python3.13执行4项新增测试，含真实唯一临时Vault provision、重复install拒绝、删除后旧source与新启动均拒绝、错误口令拒绝、正确加密恢复原身份、替换后旧进程source拒绝；仅清理自身临时引用/文件。测试factory使用固定生产引用映射到临时Vault，未创建或访问正式生产引用。固定domain预期字节/稳定UUID/错型长度/源异常均通过。

全后端934项无失败，2项既有Windows符号链接权限环境跳过。开发wheel `0.1.0.dev0` 565154bytes，SHA256 `ca9d1e912d4aa49fb29b0a9e102460eb380fabb0e1134fbb6673ec443bc36110`，构建成功；这是开发wheel不是安装包。不增加Migration/HTTP/依赖，head0042不变。

## 部署供给与剩余项

部署者在实际Worker运行账户交互终端调用现有`plm_assistant.entrypoints.secret_key_recovery`：provision/export专用引用`worker-system-actor-v1`并给出绝对加密备份路径，restore仅给加密备份路径；口令隐式输入，独立离线保管。停Worker后恢复原材料，不自动替换已有引用。不得打包凭据、备份、口令或日志。当前没有替操作者生成正式材料。

源UUID本身不是原始业务actor，发布Audit须SYSTEM源UUID+original_actor_id/trace/purpose；UUID不绕过License/Scope/当前原User权限/Lease。现有Schema不能独立证明受控来源，下一Owner必须调用此公开Port后再发布。正式目标账户供给/异账户灾备、Server2025/Debian、原子发布/HTTP/完整包/Gate均未验证。

Next：恢复AUD-03-A06-A04-P03-A04-P03实际Document/结果/Audit/Job原子发布；使用本Port，不伪造User或SYSTEM身份。
