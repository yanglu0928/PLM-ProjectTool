# AUD-03-A06-A02-P02-A02：内部协作取消与到期收口

日期2026-09-26；版本0.1.0.dev0；Phase2；结果OWNED_CANCELLATION_INTERNAL_PASS。不代表当前用户受权命令或完整Worker/Artifact验收。

## 编码前检查 / Changed / Files

输入冻结DM-04/API-03、CR-JOB-002/0039、A02-P01租约检查。实施前DEC-20260926-200；前置满足。模块Jobs；既有Job/Lease/Attempt/Outbox；只处理可信Owner事务内取消请求、当前Worker协作确认、失联到期恢复。新增audit_export_cancel.py公共合同与服务、owned repository、6项unit和独立数据库验证。无Schema/API/角色/依赖变化。

每次通过Jobs own Queue lookup固定原ExportRef/Scope/Project/Actor/Trace/策略与完整pair，精确匹配首次Job/Event refs；缺边、替换或错Scope拒绝，不enqueue修复。Queue advisory→Job→Outbox，随后Lease→Attempt保持锁到caller事务结束；不读Audit私表，不创建UOW/commit/鉴权。Owner必须先绑定实际持久Export/acceptance及当前权限；坐标/申请人FK不是授权。

PENDING/RETRY_WAIT无ACTIVE lease和错误终态信息才可同事务REQUESTED→CANCELLED。RUNNING核对当前Job/Lease/Attempt一致性，登记REQUESTED保留租约；当前同worker/token且未到期才可ack，释放Lease并完成Attempt为JOB_CANCELLED。失联后仅真实数据库到期允许恢复EXPIRED，完成Attempt/Job；重复恢复已CANCELLED无写。request重复保留首次申请人/原因/时点；已SUCCEEDED/FAILED返回原终态且changed=False，不复活或伪装副作用回滚。旧取消态无原信息拒绝，不猜回填。已完成后旧ack拒绝STALE_LEASE，重放状态由request/recovery安全读回，不授予发布能力。

原因1～1024字符，拒绝空/前后空白/Unicode控制或格式字符；不放Job payload、公共结果或Audit自由正文。该校验不能保证合法文本没有Secret，公开Owner输入和投影仍须安全处理。异常固定code，不把SQL细节送调用方；仍不提供HTTP。

## Tests / Result

Win11/Python3.13/PostgreSQL18独立UUID库实际Queue pair/两Scope、待执行直接取消/重复首信息保持、真实并发首次只有一项changed、caller模拟后续Audit异常全回滚、实际RUNNING取消及当前Worker确认/错worker与token拒绝/确认失败回滚、RETRY_WAIT取消保留旧Attempt、真实1秒租约到期及双恢复竞争仅一次changed、EXPIRED历史与取消后不再claim，通过。

真实取消→finish与finish→取消竞争：竞争连接pg_blocking_pids证实等待持锁，先取消拒绝finish/无marker，先完成保留已提交数据库marker并返回原SUCCEEDED；marker仅隔离库合成发布记录，不是真实Artifact或文件。FAILED不复活，错首次ID/Actor/Scope、缺Outbox、旧无来源取消态拒绝且不修复。Export Root/当前业务权限/正式License/Audit/receipt未在本脚本接入，不拿可信调用方冒充端到端客户命令。finally清理独立库，无客户数据或生产操作。

后端866项无失败，2项既有Windows符号链接权限跳过；6项新unit覆盖caller事务、规范输入/嵌套再验、返回身份/终态、ack/recovery状态、安全错误和无默认依赖。取消Schema及完整受权原子提交回归通过（后者License合成）。开发wheel通过，SHA-256 `492c66dabfb4dc8462f2829c31484d57403b3b06a6fb9008adb9d9e03c212967`，非正式安装包。

## Migration / API / Compatibility / Known Issues / Next

无新Migration/API/依赖，需既有0039，升级无新动作；有取消信息不能down，不删历史绕过。Server2025未验，Debian13暂缓但目标保留。锁内取消不停止外部文件I/O或回滚已发布不可变成果；真正文件临时结果清理/崩溃对账/安全发布另验。当前无自动恢复调度、受权取消HTTP或完整Worker；正式信任材料、质量、实际业务Owner、性能、Gate3/UAT及完整程序包仍待，Scope不缩减。

下一项AUD-03-A06-A03：将实际持久Root/acceptance/原Job pair、A01当前权限、A02租约与A04 capture接入可信Worker短事务；验证撤权、取消、旧Worker和整事务锁序/死锁。取消用户命令/receipt/Audit随后按冻结Job API当前权限接入，未满足前不公开。
