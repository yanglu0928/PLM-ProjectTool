# WFL-01-A05-P02 不可变 Checklist 记录形状

日期 2026-09-26；0.1.0.dev0；CR-WFL-004；结果 DOMAIN_SHAPE_PASS，不是数据库/授权/Owner/Gate PASS。

## 编码前检查

Phase 2；WBS A05-P02；输入固定 V1 十二项、冻结 ChecklistRecordRequest/状态与已记录 CR-WFL-004。前置 0030 当前投影/0031 成功迁移快照、追加更正设计已完成；当前只解决首次/更正记录的不可变结构，不依赖尚未实施的 Review 查询进行放行。

模块 workflow.domain；实体 ChecklistRecordSnapshot，无其他模块内部查询。无 API/Migration/权限策略/依赖改变，无公开写入口；未来须验证 Session/CSRF/PM/License/非归档/Workflow 强 If-Match/当前阶段和可信记录链。验收是固定归属/三结果/版本/链/UUID/UTC/依据形状及拒绝边界；风险为 UUID 不证明真实状态/访问权/批准。

## 实施与实际证据

新增 `domain/checklist_record.py` frozen/slots 快照，保留独立 record/workflow/project/actor/trace、定义/阶段/item、前状态/新结果、Item 与 Workflow 两个前后版本序列、UTC 时间、supersedes、依据/理由/影响。首次 PENDING/0 无父；后续非 PENDING 且有非自身父。版本各 +1 且在 PostgreSQL bigint 范围；不把 Item 版本当 HTTP If-Match。

FAIL 可不提供依据或意见，表示不足，不造客户事实；PASS/WAIVED 要求非空 Evidence/Review 引用形状，Review 从服务器 Owner 解析，未增加客户端请求字段。WAIVED 另要求例外/理由/影响；UUID 可定位形状不是实际批准。Supersedes 同对象/项目/当前版本和 Stage 当前可写状态仍须应用/数据库证明，领域不访问仓库。

Windows 11/Python 3.13 新增 8 项测试，包含 12×3 初次组合和 3×3 更正、旧对象不变、引用集合/自引用/链/豁免/类型/阶段/UTC/bigint 边界；后端 660 项无失败，2 项既有符号链接环境跳过。开发 wheel 构建并检查包含新模块 PASS，SHA-256 `d8112fff0c13b047f484686d5bcc49a60022826ad48778213e263937d1bb1c02`。不是正式安装包。

无 Migration/API/依赖，升级无动作；回滚为不使用新快照，不删除旧历史。数据库/实际授权/Owner/性能/覆盖率未运行；Server 2025 未运行、Debian 13 暂不验证。

Next：WFL-01-A05-P03 两张 owned 记录/依据表、0032/隔离结构验收；Gate 固定记录关系与真实服务/Owner 后续独立实现，不据纯 Domain PASS 开放写接口或关闭 Gate 3。
