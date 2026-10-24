# RVW-02-A04 固定 Subject 送审合同

2026-09-26；0.1.0.dev0；INTERNAL_CONTRACT_PASS / ACTUAL_OWNER_PRECONDITION_BLOCKED。

## 编码前检查 / Changed / Files

Phase 2；输入冻结 AF-02/DM-02/API-02、CR-RVW-001/0034、A02 送审前置与 A03 基础资格。只实现绑定固定送审数据形状与窄 Owner Port，不实施真正业务主题/锁/审批，不改变技术栈/Scope/角色。前置结构已具备，真实 Owner 尚未实现，不替代其事实。

- `review/application/subject_start.py`：不可变 Request/Prepared DTO、完整绑定/来源/时间校验、Owner 准备和实际锁重核协议，无默认成功实现。
- `tests/unit/test_review_subject_start.py`：6 项单位矩阵。
- `docs/review/review-subject-start-contract-v1.md`：职责/限制/后续事务验收。

## Tests / Result

Windows 11/Python 3.13 后端 **723 项无失败，2 项既有符号链接权限环境跳过**。新增 6 项覆盖不可变、PROJECT/当前根/唯一完整确认人、所有请求绑定维度、固定摘要/proof/UTC/集合、同项目/重复/global Trace 拒绝及来源观测时序；终态旧根只是可构造、仍必须 Owner 重验。构造成功不是实际身份锁，测试没有伪称真实客户或业务版本已存在。

开发 wheel 构建 PASS，SHA-256 `3bcbcd85818b1b12d7c9a893e4cee1e9faf75a1f2c7be5bead8b8e00fac91e89`，不是可用安装包。此纯合同任务没有数据库写/新迁移，未运行新增数据库/HTTP/真实 Owner/完整 start/覆盖率/性能/Server 2025 验收，Debian 13 暂不验证。

## Migration / API / Known Issues / Next

无 Migration/公开 API/新增角色/依赖/架构变化，升级无动作；不使用新 Port 即可回滚，保留历史。缺实际 Owner/源解析与锁阻塞真实送审接线，不阻塞内部受控事务实现；不跨 Phase 编造业务实体或伪造客户确认。

Next：RVW-02-A05 内部完整 start-round/幂等/审计，隔离验证真实基础权限与合成 Owner 协议；完整交付/Gate 3 仍未完成。
