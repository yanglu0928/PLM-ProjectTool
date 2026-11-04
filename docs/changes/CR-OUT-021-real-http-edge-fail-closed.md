# CR-OUT-021：真实 Output Create HTTP 与 hosted Edge 失败关闭集成

- 日期：2026-11-05
- 状态：编码前检查PASS_WITH_LIMITATION；hosted实现与复验待执行
- 来源：CR-OUT-015/P19真实PG18 API失败关闭证据、CR-OUT-020/P24 Edge模拟API证据
- 基线：冻结 API Contract V1 OUTPUT_REQUEST_CREATE、已批准Windows显式write组合；不改冻结合同/Schema/Migration/默认挂载

## 观察到的证据缺口

P19验证了真实Windows Create HTTP组合在Publisher manifest空时失败关闭且没有持久副作用；P24验证了真实production build的Edge请求交互，但POST由浏览器harness模拟。这两者尚未证明浏览器请求能到达真实组合、真实拒绝能以安全方式呈现在页面并保持数据库无写入。

## 选择的最小补足

在CR-OUT-021下新增仅Hosted使用的P25桥接：GitHub hosted Windows Server 2025/D盘临时目录启动隔离PG18与合成账户/Project，真实建造显式Windows Create HTTP组合并绑定loopback；Edge加载同run前端production build。登录和需求读取保持合成fixture；同源Create POST由harness通过loopback转发到真实后端，沿用浏览器Origin、Session Cookie、CSRF、Idempotency与请求体。对OutputRequest/Job/Outbox/Audit/Idempotency相关表做请求前后计数对比。

服务器Publisher manifest保持空。预期真实HTTP安全拒绝、页面提示可见、无受理回执/自动重试、持久计数不变。若HTTP意外接受或有任何写入，P25应失败关闭并调查，不伪造验收结果。

## 方案比较与差异

- 重复P19的ASGI直调：实现简单，但无法验证浏览器到HTTP、Cookie/Origin/CSRF及UI错误映射的组合，不足以补P24边界。
- 使用真实Publisher或配置测试签名钥匙：可模拟接受路径，但会引入信任/签名生成器和插件执行边界，不适合当前未具备正式信任的包。
- 选择同源Edge到真实HTTP的合成失败关闭：最小连通性补足，保留当前包真实的空信任状态，不伪造生产信任或生成文件。方案记作可回滚测试基础设施与有限客户端错误呈现调整。

## 风险、回滚、迁移与验证

- 风险：loopback转发会遮蔽部分浏览器到服务边界；通过仅POST代理与可检查的真实API端口/请求合同限制。登录/Requirement mock仍不能代表生产认证/读取组合。
- 数据影响：仅一次性runner临时合成数据库，无业务迁移；验证完成后销毁临时数据库。
- 回滚：移除P25 runner job、Node/Python bridge和临时HTTP fixture；若客户端错误映射变化则恢复对应映射。保留P19/P24各自既有证据。
- 验证：P25定向检查之后执行GitHub hosted全链（前后端、PG18/pgvector、wheel、父包/A17/A34/A35/A50、Edge），仅以PASS_SCOPE_LIMITED关闭。
- 隐私：无客户数据、外部API、厂商AI、正式秘密、真实Publisher key、插件执行或文件生成；runner temp必须D盘，用户本机及C盘不运行项目代码/测试。