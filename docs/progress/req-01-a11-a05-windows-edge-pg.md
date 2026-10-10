# REQ-01-A11-A05：Windows 11 Edge + PostgreSQL 18 真实闭环

日期：2026-10-08。结论：`REQ_01_A11_A05_WINDOWS_EDGE_BROWSER_PASS`。下一项：
`REQ-01-A12` Requirement Workflow 资格。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A11-A05
输入基线：冻结Requirement API、A10 Windows生产组合、A11-A01～A04前端合同
前置任务：A10与A11-A01～A04 PASS
涉及模块：Requirement前端读写、Windows生产组合、真实Edge验证夹具
涉及实体：Requirement/Version/Source/Acceptance/Capability/Review/Evidence
涉及API：既有LIST/GET/CREATE/VALIDATE/SUBMIT_REVIEW/Evidence Viewer/Auth；不新增合同
涉及权限：真实Session、PROJECT成员、License、CSRF及服务端每次重证
验收标准：真实Edge读取、创建、校验、送审、Evidence定位、断网清旧/恢复、登出直达门禁
风险：原生fetch接收者不兼容；能力证据不闭合；测试夹具误把未评审能力当正式事实；撤权假阳性
```

## 实际验证

- Windows 11 本机真实 Microsoft Edge 一次性Profile访问构建后的Vue、生产FastAPI组合和本机
  PostgreSQL 18.6隔离数据库；实际完成Requirement列表/详情、结构化Draft创建、服务端校验、
  `REQ-03 + REQUIREMENT_ALL_V1`送审、Version详情和Evidence Viewer显式定位。
- Draft包含五要素验收与人工确认的`DIRECT`能力评估；每项能力评估强制且仅接受一条
  `STANDARD`及一条`PROJECT` Evidence，两者ID必须不同。浏览器通过已批准能力基线读链取得标准
  Evidence，不将AI建议或未评审Capability当正式事实。
- Edge断网后刷新显示安全错误并清除旧Version正文；恢复网络后重新读取成功。通过同一SPA内存中的
  CSRF执行正式登出得到HTTP 200，再直接访问原受保护页只显示“尚未读取当前身份”，未发起业务读取。
- 最终浏览器记录46个API请求/响应观察点；CREATE 201、VALIDATE 200、SUBMIT REVIEW 201、
  Evidence Viewer 200、logout 200。三张截图位于Git忽略的本地验证目录，不提交含合成会话材料的产物。
- 验证服务随后执行原夹具数据库断言并报告`SUR_01_A06_A05_P02_WINDOWS_BROWSER_PASS`及
  `...CLEANUP_PASS`；临时数据库、凭据、文件和Edge Profile均清理。
- 前端全量93个测试文件、1526项，typecheck与生产build通过；构建仅保留既有`>500 kB`单chunk警告。

## 偏差、修正与追溯

1. 首轮Edge读取未发出Requirement请求：原生`fetch`被作为对象方法调用，Windows Edge拒绝错误接收者。
   修正为先取出函数再无接收者调用，并新增真实接收者回归测试；不改变API或业务语义。
2. 初始合成Draft选择`STANDARD_FUNCTION`却没有Capability评估，服务端按设计返回
   `CLASSIFICATION_INCONSISTENT`；没有降低校验标准，改为在真实页面维护完整人工评估。
3. 页面初版能力区只维护一个Evidence，而冻结后端要求标准能力与项目事实双证据；修正UI和客户端，
   固定角色集合、数量与不同ID，在传输前失败关闭。
4. 初版验收夹具将Capability Version标为APPROVED但缺少正式Review/Round/Snapshot证明，创建返回422；
   夹具补齐GLOBAL `CAP-01`批准链，不修改生产校验器或伪造通过。
5. 登出验证先后发现缺幂等头、硬编码CSRF及整页刷新丢失内存CSRF；最终通过真实登录页动作执行登出，
   再直达受保护页验证门禁。所有失败尝试均未改动正式数据，且各隔离库已清理。

## 兼容、回滚与边界

- 无Schema/Migration、后端API、依赖、权限、Secret、客户数据或外发变化；修正前端调用边界、能力
  双Evidence校验及可重复验证脚本。回滚可撤前端修正和A05夹具，不影响已生成的合法Requirement历史。
- 本项只证明Windows 11 + Edge + PostgreSQL 18.6合成闭环。Windows Server 2025按后续发行矩阵另验；
  Debian 13依用户指令跳过。正式TLS/信任源、20并发、POC-03质量、Gate 3/UAT/发行仍未通过。
