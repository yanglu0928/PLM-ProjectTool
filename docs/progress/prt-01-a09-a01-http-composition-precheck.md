# PRT-01-A09-A01：Prototype HTTP 与 Windows 组合前置核查

日期：2026-10-08。结论：`PRT_01_A09_A01_HTTP_PRECHECK_PASS`。下一项：
`PRT-01-A09-A02` PrototypePackage/Prototype Identity Read Owner。

## 冻结对账

API-04固定26个Prototype Operation，路径、角色和结果不变：

|资源族|数量|Operation|
|---|---:|---|
|Package|5|LIST、CREATE、GET、PATCH、SET_MEMBERS|
|Prototype Identity|6|LIST、CREATE、GET、PATCH、MARK_NOT_REQUIRED、ARCHIVE|
|Version/Review|5|VERSION_LIST、CREATE、GET、VALIDATE、SUBMIT_REVIEW|
|Template|6|PROJECT/GLOBAL LIST、CREATE、REVISE|
|Requirement Link|4|LIST、CREATE、REVOKE、SUPERSEDE|

现有A03～A08已具备22项写/版本/模板/Link业务Owner；但
`PRT_PACKAGE_LIST / PRT_PACKAGE_GET / PRT_LIST / PRT_GET`没有授权策略、读Service或Repository。写Service返回的
单次结果不能代替可撤权、项目隔离的当前读取。因此A09不能直接装配26个公开路由，必须先补A02；这属于原
CR-PRT-001既定HTTP接线的前置补全，不修改冻结Scope或API。

## HTTP 与安全边界

- 所有路由保持可选注入；默认应用与login-only模式继续404。Windows `--platform`只挂GET，
  `--platform-write`才挂全部26项，沿用正式License、Session、可信Host/Origin、HttpOnly Cookie和CSRF链。
- 写操作严格按冻结控制：带I的命令要求持久幂等键；带M的操作要求强`If-Match`，PATCH不由服务器伪造
  idempotency key。严格JSON、重复字段拒绝、正文有界、异常不暴露traceback，跨项目/未授权资源保持404。
- 六类LIST使用有完整性保护、Session/Scope/查询绑定的游标；五个资源族分别使用Package、Prototype、
  Version、Template、Link独立32字节密钥。PROJECT/GLOBAL Template共用Template密钥但把scope与project
  绑定进签名载荷，不与Requirement或其他资源游标复用。
- GLOBAL Template写继续只允许DeploymentAdmin，PROJECT Template写继续使用项目授权；项目成员能读取允许的
  GLOBAL模板不等于获得GLOBAL管理权限。HTTP投影不新增AI生成、脚本执行或原型沙箱。

## 实施拆分

1. A02：补Package/Prototype LIST/GET Owner、四项授权策略和PostgreSQL项目隔离证明。
2. A03：五个独立签名cursor合同及Windows KeyRef失败关闭边界。
3. A04：Package 5项HTTP合同。
4. A05：Prototype Identity 6项HTTP合同。
5. A06：Template 6项HTTP合同。
6. A07：Version/Review 5项HTTP合同。
7. A08：Requirement Link 4项HTTP合同。
8. A09：Windows显式只读/写组合、26项路由清单与真实PostgreSQL 18端到端。

各Router可独立撤装配；历史业务事实、Audit和receipt不删除。游标密钥只由既有Windows当前账户安全提供者
读取，不自动生成、不写Git；正式目标服务账户供给仍是Release约束。Server 2025不从Windows 11外推，
Debian 13按用户指令跳过。A10前端、A11 Workflow、Gate 3、UAT和发行不因本核查关闭。
