# P06-P13-P07：保留拒绝游标与有界回绕

2026-09-27/Phase2，CR-AUD-005。编码前：Audit isolated Admission/Sweep窗口状态，实体/权限/API/Schema/依赖不变。输入P06实际91steps/78rejected/12executed，两轮有限健康完成但坏head每成功claim后重复重扫。

选择：正常claim/原证明完成后保留最近拒绝cursor，而不是立即清除；当前scan返回None才清除/从首部回绕。为避免前方修复/新高优先任务长期不可见，每32次有结果的调度动作强制仅重置技术cursor/counter，下次从首部重读，SQL原priority/available_at/JobId排序不改。仍每次一个候选、32是内部有界窗口非成功/权限证据；不保排除名单/不写坏Job。DB/identity/commit异常不推进窗口，原确认恢复与STOP不变。该窗口不承诺无限流优先级公平或32秒时间保证，执行中的命令可能耗时。

验收：保留cursor、32动作回绕/末尾回绕、Unknown fault不推进unit；同原真实混排测试计数下降、坏行不动/STOPPED；真实新高优先任务在cursor前插入后最迟窗口刷新可领取，仍原完整Root/identity/claim绑定。回滚撤窗口保留旧清cursor行为；无Migration/升级，正式Scope/性能/Gate待。

真实增量验收设计：每个Scope放置1个合成坏来源与40个正常任务，第一次正常完成后通过原提交入口插入priority=200的新任务；仅隔离验证库修改priority，记录它在原40任务耗尽前、最多32个正常完成动作内被领取。原坏行/Lease/Attempt保持不变，全部正常任务完成后正常STOP；还原坏来源后通过同一实例末尾回绕完成。既有隔离回归增加显式末尾空扫描，反映保留cursor后修复队首不会立即越过当前窗口的新语义。

## 已取得证据

- Windows11/Python3.13：后端1132项无失败，2项既有权限跳过；新增Admission与Sweep保留游标/32动作刷新测试。
- `validation/aud-p06-p13-scan-window/verify.py`：真实隔离PG双Scope，各40正常+新增1高优先任务；新队首在31个原正常任务完成后执行，均44steps/2rejected/41executed并STOPPED，坏Job/Lease/Attempt全行不变。停止实例不可重启，清理修复源通过新Worker发布；同实例末尾回绕由旧queue-isolation回归验证（纠正设计文字中的清理安排）。明确合成License/测试优先级，非正式平台验收。
- 原mixed-loop两轮均25steps/12rejected/12executed，对比旧91/78/12，仅此固定数据集调度步数下降，不宣称吞吐/无限流公平PASS。queue-isolation补显式末尾空扫描，无写回绕后旧任务发布；原发布回归通过。
- 新脚本首次运行引用错误的ExecutionOutcome属性而失败；对照实际类型修正为kind/command.job_id后通过，未据此修改产品或抹去失败。开发wheel构建成功；随后查询错文件名失败，使用实际构建文件名核对。
- wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` 635273 bytes，SHA256 `dfedc2b42364c3513218d6269bd0233cad525e12606628326b3e9095e4f35ceb`，仅开发wheel，非最终可用安装包。
- 本轮重跑真实claim-confirmation提交前回滚/提交后lost-ack、Windows独立CLI子进程发布/缺正式公钥关闭/外部停止单次排空、真实反向锁序8次40P01和2次55P03矩阵，全部通过，各自旧发布回归同时通过。没有据此关闭跨进程未知命令恢复或正式环境验收。

无Migration/API/依赖/升级变化；回滚撤本轮游标保留/32窗口实现与相应回归，保留原历史。CR-AUD-005仍打开，Acceptance真实损坏/复杂Lease/预检竞争、正式公钥与账户材料、Server2025/完整Scope/Gate3/最终包仍待。下一P13-P08收口已覆盖的调度验收与残留风险，然后推进公开Jobs HTTP前置，避免无界拆分内部测试。
