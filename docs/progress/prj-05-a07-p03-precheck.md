# PRJ-05-A07-P03 成员创建页面前置核查

2026-09-28 / PRECONDITION_BLOCKED（页面未实施）。

编码前检查：当前Phase2，Gate2/Phase1通过；输入冻结`PROJECT_MEMBER_CREATE`、已完成的PRJ-05-A07-P01/P02、现有Project Department GET。涉及ProjectManager成员创建页面、Auth目标User候选、Project部门；原POST权限不变，新增候选读取须有独立增量合同/权限。验收为非技术用户可用的目标用户/ACTIVE部门选择、服务端实时权限、单次提交和未知结果原Key恢复。风险为目标UUID无安全来源及扩大管理目录权限。

事实：`AUTH_USER_LIST` 仅DeploymentAdmin，当前ProjectManager无可用候选源；用文本UUID表单会将技术标识交由用户手填，达不到本项可用性要求。依据Skill前置未完成时停止受影响页面编码；已登记CR-PRJ-006，不修改冻结原版。下一步先做P03-A01最小受权候选解析及真实权限测试，再做现有部门GET前端选择与页面。无代码/Schema/API运行变更；本次仅形成设计和阻塞记录，不标页面PASS。
