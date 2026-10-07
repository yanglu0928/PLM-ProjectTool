# REQ-01-A12-A07：Windows 11 Edge Requirement Workflow闭环

日期：2026-10-08。结论：`REQ_01_A12_A07_WORKFLOW_EDGE_PASS_WITH_AUTOMATION_ALTERNATIVE`。
`REQ-01-A12`收口；下一项：`PRT-01-A01` Prototype运行前核查。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A07
输入基线：CR-REQ-004、A05真实Owner/PG闭环、A06前端构建
前置任务：REQ-01-A12-A06 PASS
涉及模块：只新增/扩展隔离Edge验收夹具；正式产品代码不变
涉及实体：合成浏览器资格，真实Workflow/Checklist/Transition/Audit/receipt写入临时PG库
涉及API/权限：构建后Vue、生产FastAPI、真实登录Session/CSRF和Project Manager边界
验收标准：真实Edge顺序完成六项PASS、三次推进，到达PROTOTYPE/v10；无UUID泄漏与页面错误
风险：浏览器控制器不可用；测试代理被误述为真实Requirement批准；验收资源残留
```

## 验证结果

- 隔离Microsoft Edge profile从真实登录页开始，经构建后Vue和生产FastAPI完成START、Handover/Survey/
  Requirement六项PASS以及三次阶段推进，最终独立刷新确认`PROTOTYPE/v10`。
- 浏览器网络观察30项；要求的START、六个Record和三次Transition均返回2xx，页面可见错误和运行时异常为0。
- PostgreSQL 18.6核对六个PASS、三条Transition、六个Gate item、精确Audit和十个已完成幂等receipt；
  Alembic无漂移，数据库、测试凭据、服务、临时目录及Edge profile全部清理。
- Requirement确认页检查为“2个正式需求版本、2个真实批准轮次”，UUID未出现在确认文本；最终截图保存在
  Git忽略的`artifacts/req-01-a12-a07-workflow-edge/`，不提交运行证据中的本地信息。

## 替代、兼容与回滚

- 按`computer-use` Skill首选真实UI控制器；初始化及重置后重试均失败，原始错误为
  `failed to write kernel assets: 系统找不到指定的路径 (os error 3)`。依据持续授权，改用仓库既有的
  独立Edge/CDP驱动；仍为真实Edge进程，但不宣称是人工或Computer Use交互。
- A07使用两个Subject的固定聚合代理专门验证前端复数交互；真实Requirement来源、能力、Review、Owner、
  PostgreSQL和HTTP写链由A05独立证明。两份证据必须合并解读，A07代理不能成为业务批准事实。
- 为复用既有Survey夹具，旧驱动增加可选`requirement`模式，默认Survey模式和既有预期不变；生产代码、
  Schema/API/依赖/权限/客户数据/外发均无变化。删除A07目录并撤可选参数即可回滚。
- Windows Server 2025未执行本轮浏览器闭环，Debian 13按用户指令跳过；Gate 3仍受既有AI质量、信任、
  性能及后续Prototype/Solution/Plan真实Owner阻塞，不能因REQ-01完成而关闭。
