# RVW-01-A05 内部 PROJECT Review 受权读服务

2026-09-26；0.1.0.dev0；结果 WINDOWS_INTERNAL_AUTHORIZED_READ_PASS（Owner/License 协议合成）；实际 Subject Owner/HTTP/Gate 尚未通过。

## 编码前检查

Phase 2；输入冻结 API-02 REVIEW_GET/角色矩阵、AF-02/DM-02、CR-RVW-001、0034 与 A03/A04 设计。前置内部固定查询/两层授权设计具备；只解决内部 PROJECT 读取编排，不实现创建/审批或主题 Owner。实体 Review/Round/Assignment/Decision/Snapshot 与只读 Project 当前事实；权限四类有效 Project 成员 + 真实 Owner 身份/固定旧版读取授权，部署管理员不旁路。无 Migration/公开 API/新增角色/依赖/架构变化。

验收：Session/License/Project 先校验、同事务授权锁、固定历史权限独立、错误证明/缺 Owner 拒绝、查询不改变 Review；风险：真实 Owner 尚未实现，不能通过协议合成验收开放生产。公开路径继续保持不挂载。

## Changed / Files

- `review/application/read_service.py`：内部 Query、窄 Subject Owner Port、绑定身份/固定版本的授权结果与只读服务；Session token 不进入 repr，异常只返回安全内部错误码，不暴露 traceback/SQL/路径。
- `project/application/authorization.py`：REVIEW_GET 四角色/锁读策略，归档受权只读，Project/成员/部门事实复用真实 Repository。
- `review/application/read_snapshot.py`、`review/infrastructure/read_repository.py`：增加在 Review 共享锁下定位固定不可变 Version 的窄方法，Owner 授权后才锁 Round/加载 Assignment/Decision/依据，遵循 Project→Review→Owner→Round 相对顺序。
- `tests/unit/test_review_read_service.py`：12 项单位矩阵；Project 策略测试同步精确数量/四角色锁读语义。
- `validation/rvw-01-a05-authorized-read/verify.py`：只使用脚本自建随机临时库，真实 Session/Project/Review 与合成 Owner/License，结束自有库清理。

## Tests / Result

Windows 11/Python 3.13 后端 **704 项无失败，2 项既有符号链接环境跳过**。12 项新增单位验收覆盖四角色、同事务调用、身份查询不加载决定、缺 Owner/错误证明/未知主体拒绝、旧版权限独立、Session/License 拒绝、跨 Scope/Project/版本/固定快照异常、时间源错误与安全脱敏。

PostgreSQL 18.6 隔离验收 PASS：真实 Session/当前 Project 成员/部门；四角色可读合成 Owner 许可的固定旧轮；当前 IN_REVIEW 与旧 APPROVED 分离。部署管理员无成员、跨项目/未知 Review/Round、失效 Token、成员暂停/会话撤销拒绝。缺 Owner 拒绝；合成 Owner 允许身份但拒绝固定旧版时，不返回旧意见。归档 Project 允许受权只读。

在合成 Owner 暂停点，实际会话撤销、成员暂停及 Review 更新都受到调用方已持数据库锁保护，超时拒绝；调用结束锁释放。读取前后八表/来源完整快照不变，没有 Review 写入或伪造 Audit。生产 License Guard 自身可记录许可验证事件，此测试无 Review 写入不等于所有生产 GET 都无审计。

内部 A03 快照、既有受权 Workflow/Windows 双显式组合 HTTP 回归 PASS。开发 wheel 包含新服务，SHA-256 `8030274d181b9957fd3e0e95057b66396ffba6b9d00726edc096b1c403221d4a`。不是最终可使用安装包。

## Migration / API / Compatibility / Known Issues / Next

无新 Migration/公开 API/依赖/角色/总体架构改变；需 0034，升级无新动作。停用内部服务即可回滚，历史保持。HTTP 没有接线/验收，不对外自动序列化内部 DTO。真实 Owner 权限/业务身份锁、客户资格、审批幂等与 Gate 仍缺；合成 Owner 的窄结果不是客户批准或当前来源资格，真实跨 Owner 死锁/性能/覆盖率未运行。Server 2025 未验，Debian 13 暂不验证。

Next：RVW-01-A06 Review identity 创建/Owner 前置与政策设计，再推进内部 PM 创建命令。持续目标仍为完整可用程序包，不因内部任务 PASS 关闭 Gate 3。
