# PRT-01-A09-A09 Windows Prototype生产组合

日期：2026-10-08。阶段：Phase 2 Platform Core。状态：PASS。Gate 3保持BLOCKED。

编码前检查：A02～A08的26项冻结Operation内部Owner、五类独立cursor及可选Router均已通过；本项只接
Windows显式平台组合、统一Review Registry和真实PG验收，不改变实体、Schema、冻结API、角色、依赖或
AI外发。默认/login-only必须继续404；只读模式不得构造写入口。

实现：新增`windows_prototype.py`，集中组合Package、Prototype、Template、Version、Review Submission和
RequirementPrototypeLink。`--platform`仅投影九项GET，`--platform-write`装配全部26项；五类cursor从
既有固定KeyRef解析，任一缺失/错误/重复均失败关闭。统一PROJECT Review组合注册`PRT-03`真实Subject Owner，
其Current Validator和Approval Trace Owner与业务送审使用同一规则。

验证：组合单元覆盖9/26 Operation、密钥和非法模式失败关闭；生产入口/Review相关合同共38项通过。
Windows 11/PG18.6随机隔离库完成默认404、只读GET/405、写模式真实Session/CSRF/License/Project权限、
Package/Prototype创建读取、成员设置、v0→v2强ETag修改、两Scope Template、Version/Link读取、Audit/receipt
与Alembic drift，最终标记`PRT_01_A09_A09_WINDOWS_COMPOSITION_PASS`。验收脚本前两次仅分别修正错误导入路径
和旧成员表名，失败库均由finally清理，第三次全新库完整通过；未修改产品规则。

全后端3210项通过、3项既有环境跳过；compileall与`git diff --check`通过。开发wheel含1229项，SHA-256
`6e4fa209cf57994b86e79069782307506d2da9e34e309a9171c4c3a319ffe725`，已确认包含Windows Prototype组合。

兼容/回滚：无Migration、依赖、权限、公开路径、Secret内容或外发变化；Schema head保持0134。撤除生产
Router注入与`PRT-03` Registry登记即可关闭新入口，已经提交的业务/Audit/receipt历史保留。正向License和
cursor密钥为显式合成测试注入，不代表正式服务账户Key/发行信任；Server2025、A10前端、A11 Workflow、
Gate3/UAT/发行仍待，Debian13按用户指令跳过。下一项`PRT-01-A10-A01`前端范围与安全交互前置核查。
