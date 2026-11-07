# OUT-01-A01-P20：OutputRequest详情GET显式Windows只读组合结果

- 日期：2026-11-04
- Change Request：CR-OUT-016
- 结果：PASS_SCOPE_LIMITED
- 分支：`feature/p51-a33-launcher-checksum-recovery`

## 交付

- 增加Windows OutputRequest read composition factory，复用当前Session读取、Project成员读取、License guard、固定详情SQL Repository与既有只读HTTP adapter。
- 只在显式 `include_secret_read` 组合挂载；默认、登录及无Secret read信任的组合保持未挂载。
- 无Schema、Migration或API契约修改；响应不含Context正文、存储路径、Secret或Artifact内容。

## 验收证据

- GitHub hosted run [41835015557](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41835015557)：13/13 jobs成功；后端4,021项/wheel、前端、PG18.6、父包、A17、A34、A35、A50均通过。
- hosted PG18.6实际HTTP合成验收：授权项目成员GET为200；非成员和跨项目GET为相同404；响应不包含Context正文标记和文档路径；数据库业务行计数保持不变；默认应用无GET路由。
- 非发行父包20,202文件，内部SHA-256：`8d24b79a138340dd02053baddb97a4364ddaf725254a20d9af4cf236bb999d70`。

## 边界

使用GitHub Windows runner D盘临时PG18.6与合成Session/License。此结果不证明Windows 11实机、真实License信任、Gate 3、Pilot或正式Release。
