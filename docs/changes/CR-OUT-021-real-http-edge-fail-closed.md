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

## 首轮 hosted 偏差（修复前登记，2026-11-05）

- Run [41895767137](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41895767137) 中P25专用job在D盘runner temp完成前端与sidecar provenance、Node/Python语法检查和依赖安装后，sidecar包哈希/文件清单校验通过；随后Windows initdb.exe非零退出，未启动PostgreSQL、API或浏览器。P25 job失败，其他独立hosted作业继续中；无产品API修改、插件执行或数据写入。
- 首轮包装器为避免日志泄漏只报告命令名，未保留initdb标准错误，因此目前无法确定真实根因；不得假设为locale、路径或sidecar文件问题。
- 修复前方案：仅让P25 harness在命令失败时输出截断的initdb标准输出/错误尾部，并过滤临时绝对路径、用户名和控制字符；成功时保持静默。复核PG配置文件/共享库、初始化参数与D盘路径；保持密码/Secret不进入命令参数或日志。之后重跑P25及完整hosted链。此为测试诊断变更，不调整产品服务信任。


## 第二轮 hosted 偏差（修复前登记，2026-11-05）

- Run [41897161326](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41897161326) 的P25 job再次在initdb.exe启动前失败；P25脚本语法、依赖、同runPG18 sidecar完整性均通过。新增诊断显示initdb stdout/stderr均为空；当前日志尚未包括Windows进程退出码，因此根因仍未知。PostgreSQL服务、真实HTTP与Edge步骤未执行。
- 实施前方案：诊断helper仅增加进程退出码并在启动PG前依次调用包内pg_config.exe --version、postgres.exe --version，验证二进制可加载；命令失败时仍只保留截断、去runner-temp路径的标准输出/错误。复核PATH包含verified bin/lib及工作目录。不改产品代码、DB合同、Publisher信任或预期拒绝。诊断确认根因后，先记录再实施后续修复。


## 第三轮 hosted 根因证据与修正决定（实施前，2026-11-05）

- Run [41898332690](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41898332690) 的二进制版本探测均成功，但initdb正式初始化退出码为3221225781（0xC0000135，Windows STATUS_DLL_NOT_FOUND），stdout/stderr为空。证据指向初始化阶段的原生动态库加载失败；API/Edge尚未运行。
- 仓库现有PG18 hosted smoke采用同一重建sidecar、临时D盘数据目录、auth=trust/UTF8/locale=C，以poc_admin初始化，且不改写全局PATH。P25与该可复用路径的差异是使用postgres用户名并额外重写PATH。
- 最小修正：P25按已有PG smoke采用poc_admin及继承runner原PATH，保留版本探测和受限退出码/错误尾部；把D盘PG runtime/bin加入PATH只供该child process需要时再定位。该调整不改业务数据、Schema、License/Publisher信任或API。下轮若仍失败，先检查并输出隔离PG日志末尾的去路径摘要，再选后续修复。
