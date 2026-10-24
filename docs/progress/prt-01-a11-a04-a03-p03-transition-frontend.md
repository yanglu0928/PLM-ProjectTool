# PRT-01-A11-A04-A03-P03：Prototype 阶段推进前端客户端

日期：2026-10-08。状态：客户端合同通过；页面按钮与生产服务仍关闭。

编码前检查：依据 Gate 2 冻结 Workflow Transition 合同、`CR-PRT-005` 和 A04-A02 可选后端组合。本项仅扩展固定相邻阶段的前端推进入口，不改 Schema、服务端、角色或固定请求。前端两项 PASS 只是必要前置，提交事务中仍由服务端重证真实 Owner。风险是过早在未验收生产实例显示推进按钮，因此本项同步保留页面旧阶段白名单。

实现：Transition客户端只新增 PROTOTYPE→SOLUTION 映射，要求当前 PROTOTYPE ACTIVE 且两项均 PASS；请求仍仅含目标阶段、规范理由和空 GateRef 集，携带原强 ETag/幂等 Key。首回执严格校验来源/目标、版本+1、理由与身份，`is_current_state_proof=false`。页面按钮尚不对 PROTOTYPE 开放。

验证：客户端/页面定向 39 项，前端全量 101 文件/1603 项、typecheck、220 模块构建通过。真实 Windows 11/PG/HTTP/文件与性能未验，不宣称真实 Gate PASS。

兼容性/升级/回滚：无迁移或新依赖，重新构建前端即可；撤新增固定映射可回滚，历史不变。下一项 P04 页面接线、A05 真实验收并决定生产显式启用。

TraceLink：`CR-PRT-005` → A04-A02 后端可选组合 → A03-P01/P02 前端资格与Checklist → A03-P03 推进客户端 → P04/A05。
