# P04-P03-P03 失败提交原源核验

日期：2026-09-26；状态：INTERNAL_FAILURE_PROOF_PASS / RUNNER_WIRING_PENDING。

编码前检查：Phase2/P04-P03-P03；输入CR-AUD-004/ADR011，前置实际原Root/acceptance/pair、Jobs终止Port及Owner同UOW失败已验。涉及Jobs owned终态只读证明与Audit owned固定失败事件核验，不跨Owner访问表，无Schema/API/依赖/权限扩张。安全权限为当前SystemActor+相同Supervisor静止锁，仅核验失败，不读内容/恢复成果/复活Job。

目标：不能根据STALE、单一FAILED或异常文字猜提交成功。严格同Job/fence/Worker/Attempt与RELEASED Lease、固定原pair/Scope/trace/载荷、一致完成时间/原因、原SYSTEM失败Audit唯一完整字段及发生时间，再当前identity重核。核验无写/不commit；缺失/矛盾/重复证明拒绝；通用claim耗尽FAILED无Owner审计拒绝。Owner提交确认丢失后只按此完整来源确认，不重复terminate。

验收：实际双Scope true commit后raise一次核验原失败/多次核验表快照无写；未commit rollback/无Audit technical FAILED/错原因或旧代/成功取消活跃过期缺证明拒绝。原终止回归/全后端/wheel；无生产变更，三平台/正式材料/取消/主循环/质量/Gate/安装包待。

Changed/Files：Jobs `failure_proof.py` DTO/Lease owned `check_failed`/原failure Port `assert_failed`，Audit owned `export_failure_proof.py`/`verify_termination.py`，4新unit与独立验证脚本。没有自commit/写状态/写Audit；没有跨OwnerSQL或正文/文件读取。

Tests/Result：实际临时PG/Vault双Scope真正tx.commit后raise确认丢失，完整原源核验返回同一失败/Audit ID；重复3次八表快照无写。RUNNING/已成功/错Worker/fence/Root/错原因、真实技术FAILED缺Audit、实际错误Audit、重复Audit均拒绝。原P02终止/原发布全回归通过，其取消/过期/真实接管旧代/写后异常回滚证据保留；本轮没有额外执行verify取消/到期/新代竞争矩阵，不把旧证据当新矩阵。缺失证明与后验identity变更unit拒绝。首次unit Mock assert方法未声明修复spec后4项完整重跑。

Windows11/Python3.13后端1008项无失败（2既有环境权限跳过）。开发wheel 591927 bytes，SHA256 `bd35962198b4f0a24d01d2c30e566817303578fbf7284bfe5900c91c3db96848`。无Migration/API/依赖，head0042，无生产升级，撤未装配核验入口保历史可回滚。

Known issues/Next：这是内部只读证明，不自动吞异常/重写终态，也不使提交执行器已接线；生产trust/三平台/质量/Gate/可用安装包待。下一项取消安全Owner，随后瞬时错误retry/单次执行器明确失败结果和主循环。
