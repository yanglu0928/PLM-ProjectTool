# P04-P03-P05 瞬时失败重试Owner

日期：2026-09-27；状态：RETRY_OWNER_INTERNAL_VALIDATED / REMAINING_LIFECYCLE_PENDING。

编码前：Phase2；WBS AUD-03-A06-A04-P03-A07-P04-P03-P05；CR-AUD-004/ADR011、三次尝试/当前授权/强制Audit。前置caller-UOW失败Port、静止锁、SystemActor、当前权限与终态核验已验。涉及Audit重试Owner/Jobs owned当前执行事实Port；Job/Lease/Attempt/Audit，无Schema/API/依赖/权限扩张。

实施前政策补充：仅固定AUDIT_UNAVAILABLE基础故障允许有限重试，第一/第二次失败延迟5/15秒，第三次FAILED。自由正文/未知错误/权限License/内容损坏/上限/停止仍活跃不在重试白名单；不得把缺identity或数据库仍不可写当已调度。重试需要原User当前业务授权前后均有效，失效只走既有终止Owner（下一项接线）；SystemActor不是业务旁路。真实原Root/pair/当前Worker-fence活Lease事实选attempt→最小SYSTEM Audit→identity与当前权限后验→owned失败转换最后→commit。下一代重新claim且重新授权/capture/render，旧字节/尝试不覆盖。成功确认必须先经现有实际发布核验，重试Owner对SUCCEEDED拒绝，执行器尚未接线。

验收：两Scope实际PG延迟/下一代/三次上限/Audit同事务，第二/第三次新claim新文件ID且旧字节保留；权限/License/identity/旧代/取消/成功/到期拒绝，写后故障及后验权限整回滚。真实5/15秒等待，不用改数据库时钟制造PASS。回滚撤未装配Owner保历史；重试确认丢失核验/执行器主循环/HTTP/正式材料/Gate/完整Scope包仍待。

Changed/Files：Jobs failure.inspect_current只读当前代/实际pair/活Lease Port；Audit固定重试Owner；unit、独立PG验证脚本、CR/ADR/决策/状态/版本记录。Migration/API/依赖无变化、0042保留，无生产升级。

Tests/Result：6新unit（首延迟/第二与三次上限/错误白名单/后验授权/错claim与返回值/实际活心跳线程拒绝）；Windows11/Python3.13完整后端1037项无失败，2既有Windows权限环境跳过。真实PG18临时库、临时Windows Vault与合成文件，两Scope分别真正5/15秒等待、期间claim None、重新领取当前同Job新fence并重capture/render、三个新FileId/旧字节保持、第三次FAILED/RELEASED Lease/Attempt AUDIT_UNAVAILABLE和三条对应SYSTEM Audit一致。当前User停用/License撤销/后验identity丢失、Audit与实际retry转换写后/后验授权故障六表整回滚；错Worker/fence/Root/旧代/成功/取消/实际过期拒绝。实际过期案例以既有技术取消停止fixture参与后续claim，不代表新增取消Owner证明；原发布fixture回归通过。

开发wheel604903字节，SHA256 19375a80a541bc7aeb7b1f46ade4af1d84caa7e5bbc0f7d06ad811da10a217cd，构建通过；不是可用安装包。未运行真实网络断线/新Owner并发竞争/生产账户或三平台发行，不扩大断言。

Known Issues/Next：P05-P02补重试提交确认丢失原源只读核验；当前Owner不依据未知确认返回猜RETRY_WAIT/FAILED。主执行器应先实际核验已提交成功，再只在同步I/O返回/静止及当前权限有效时重试；接线/主循环/公开HTTP/正式材料/质量/Gate/全Scope最终可用包仍待。
