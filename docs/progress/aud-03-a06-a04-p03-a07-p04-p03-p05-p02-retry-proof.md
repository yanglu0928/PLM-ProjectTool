# P05-P02 重试确认丢失核验

日期：2026-09-27；状态：INTERNAL_VALIDATED / RUNNER_WIRING_PENDING。

编码前：Phase2/P04-P03-P05-P02；CR-AUD-004/ADR011/5与15秒三次政策，前置重试Owner/真实Job-Lease-Attempt与当前权限已验。涉及Jobs owned只读执行转换证明和Audit唯一执行时间窗口事件/核验Owner；无新DB/API/依赖/权限。

方案/验收：原pair与指定Worker/fence的实际RELEASED租约、AUDIT_UNAVAILABLE完成Attempt、固定退避事实；当前仍RETRY_WAIT检查available_at，下一代已claim则检查实际下一Attempt启动不早于原退避期限。历史收据是当次转换结果，不反映当前状态、不授新代修改权。第三次必须实际FAILED/完成一致。Audit仅允许原scope/actor/trace/当前identity与该Attempt执行时间窗口内唯一retry/失败事件；当前权限前后均有效。真实commit后确认故障→多次无写核验、下一代已claim仍原收据；缺错重复源/绑定/identity/权限拒绝，无文件I/O或commit。保留原冻结/所有历史，撤未装配只读核验可回滚，整体包/Gate/主循环尚待。

Changed/Files：Jobs owned历史执行转换Proof/Lease Repository/原pair Port、Audit owned执行窗口唯一来源/核验Owner、两unit文件、独立实际验证脚本及追溯记录。Schema/Migration/API/依赖无变化，0042保留，无生产升级；固定延迟仍5/15秒，三次上限不改。当前旧代已RETRY_WAIT后被即时取消，原重试收据仅证明历史转换，不宣称当前仍等待。新代启动须早于或等于当前Job实际代次、晚于退避期限；不是假定下一代运行事实。

Tests/Result：5新unit（Owner3/事件字段与唯一性窗口2），Windows11/Python3.13完整后端1042项无失败、2既有权限环境跳过。真实PG18临时库/Vault两Scope，每次真正commit后raise确认故障，三次均按实际RELEASED Lease/Attempt/原pair与唯一SYSTEM源恢复收据；真实5/15秒等待后实际下一代claim及最终FAILED，所有旧收据仍一致，每次四读八表完整snapshot无写。RUNNING/成功、错Worker/fence/root/attempt、缺SYSTEM源/同一实际转换前重复SYSTEM源、User停用/License失效/第二identity丢失拒绝；原发布fixture通过。缺源/重复源样本以既有技术即时取消清理fixture参与资格，仅临时测试，不宣称生产删除或取消Owner新验收。

开发wheel608693字节，SHA256 7dc04473c0687c019a3c7c7a3a6e5aa6dc7c7eb552b0950d594348cf118a89ab，构建通过；不是可用安装包。未执行实际网络断线/新Owner并发竞争/生产账号/三平台发行，模拟commit后的返回确认故障不等同所有网络故障已覆盖。

Known Issues/Next：P04-P03-P06将实际成功恢复/终止/取消/重试与来源核验接入单命令执行器，再主循环/公开Jobs HTTP。当前无自动runner接线，不因内部子项证明而关闭CR/Gate。正式信任源、目标账户/质量/全Scope可用包仍待，目标保持active。
