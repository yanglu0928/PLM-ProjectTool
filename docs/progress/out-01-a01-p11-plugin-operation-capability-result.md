# OUT-01-A01-P11：Plugin OperationCapability 只读Owner适配结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-008
- 代码提交：f66ef39085b7c165053b8443d384d97d05a1cea6（后续测试更正提交 b8df47719f8edcde5364bd84f5678adc7e643c4d、eed9a335e7d2b24e54ca65d4140932481ed4ac1c、22302fb67e81fa0ee0f59c3e51d9852e44d39b5c）
- Hosted run：[41777943851](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41777943851)

## 实现

- 新增 Plugin Owner-backed operation capability 只读查询与 Output adapter。Output 仅依赖 Plugin application projection，不直接读取 Plugin ORM。
- operation 必须唯一对应不可变 Manifest 声明；同 PluginId 恰有一个 ENABLED Installation；存在精确 EnabledOperation；最新 RuntimeValidation 为 COMPATIBLE 且快照匹配。
- trusted 只有在 Package 为 VERIFIED、最新 package verification 为 PASSED 且 check code 为 SIGNED_PACKAGE_VALID、签名者在当前 packaged publisher registry 中仍为 ACTIVE 时才为 true。
- Output capability 默认 enabled/trusted 均为 false。数据缺失、歧义、异常均失败关闭；不存在 HTTP API、Migration、公开组合挂载或插件执行变化。

## 验收证据

GitHub Actions hosted run 41777943851 的 14/14 jobs 成功：后端 3,975 项测试和 wheel、前端测试/typecheck/build、PostgreSQL 18.6/pgvector 0.8.6 生命周期、20,183 文件非发行父包、A17、A34、A35、A50。临时目录在 hosted runner D 盘；没有在用户本机运行程序或测试。

PG18 capability smoke 使用合成记录证明：完整 synthetic owner facts 可映射为 enabled/trusted 正向能力；当前正式 publisher registry 为空时同一包 trusted=false；追加最新 INCOMPATIBLE RuntimeValidation 后 enabled=false；同名 operation 分属两个 package 时 capability 缺失。该结果为合成端口验证，不是正式 signer 信任。

第一次托管尝试 41775475116 的单一失败，是测试对 trusted=false 负向事实的期望错误。失败已先记入 CR-OUT-008，再修正测试；生产适配器保持原 Fail-Closed 行为。最终 41777943851 全链成功。

## 限制

正式 publisher key 当前未配置，因此生产包不会返回 trusted=true，Output Resolver 将拒绝生成请求。未启动产品 API、未运行客户插件、未创建客户文件或外发数据。Pilot、Gate 3 和正式 Release 仍 NOT_READY。父包 SHA-256 为 dab444bbfb9bfabd913b24fd21a132b994e4e537884cbe07fc1ff423fb7af31b。
