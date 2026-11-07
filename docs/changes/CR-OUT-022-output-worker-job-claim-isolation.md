# CR-OUT-022：Output 生成作业的 Jobs Owner claim 隔离

- 日期：2026-11-05
- 来源：CR-OUT-021 第十三轮 hosted 复验后依 STATUS 下一项盘点 Output/Worker 信任边界
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P26
- 类型：执行顺序调整 + Jobs/Output 内部 Worker 边界收紧；无冻结基线、公开 API 或数据模型变更
- 状态：实施前登记

## 证据与问题

- Run [41925875768](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41925875768) 中 P25 的 Node PATH 限定对照无效：PostgreSQL child PATH副本确已移除Node可执行目录，initdb仍以 `0xC0000135` 失败；未启动PG、真实HTTP或Edge，P25保持失败。
- 当前 Jobs `claim_next` 的通用查询显式排除 RAG Build/Retrieval 与 Plugin Package Verify，但没有排除 `owner_module='output', job_type='OUTPUT_GENERATE'`。已存在只写入此类Output Job/Outbox的队列，缺少对应的Output专属claim入口；通用Worker可能越过Owner边界取得此Job。
- Windows Plugin package Worker的职责是校验包元数据，不执行插件。当前也不存在专属Output generation Worker入口。该CR只隔离claim权，不声称提供渲染、插件执行、FileObject成功发布或Publisher正式信任。

## 决策与实施范围

- 新增 `JobLeaseService.claim_next_output` 及Repository Port/SQL实现，严格过滤 `owner_module='output'` 且 `job_type='OUTPUT_GENERATE'`；保留现有租约、fencing、重试、取消及事务边界。
- 通用 `claim_next` 排除精确的Output Generate Owner/JobType组合，确保其他通用Worker不会取走Output作业。
- 增加无副作用输入校验单测，并以同一Hosted Windows Server 2025 D盘临时PG实例验证：通用claim不会拿到Output Generate；Output专属claim只能拿到此Owner/JobType；其他owner/type仍保持隔离。沿用已通过的父包PG lifecycle任务执行PG smoke，避免依赖P25当前受阻的sidecar initdb路径。
- 不增加ORM/Migration、公开API、运行时自动启动、插件执行或文件生成。Output job无专属消费者时保持排队；不会让任何其它Worker替代执行。

## 风险与恢复

- 风险：现存通用Worker若曾依赖泛化claim处理未分类Output Job，变更后它将不再拿到该Job。此行为为预期Owner隔离；真正消费者须调用新的Output专属方法。
- 回滚：可撤回新专属claim入口；如回滚通用claim过滤，须先确保无通用Worker消费Output Job，并继续维持无消费者失败关闭。无数据库数据或Schema迁移。
- 无客户数据外发、Secret、License材料、发布/生产写入或不可恢复操作。
- 验证：Hosted全量后端/前端与既有流水线；使用父包中的PG18.6/pgvector0.8.6 lifecycle smoke调用专项验证器。P25仍单独报告FAILED，Gate/Pilot/Release不变。

## P25 路线处理

已停止对initdb做猜测式环境变量微调。P25后续只在有新的直接根因证据时恢复；当前先推进此不依赖P25 initdb差异的Jobs/Output安全边界任务。

## 第一轮 hosted 验证偏差（修复前登记，2026-11-05）

- Run [41929416448](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41929416448) 中后端全量4,023项/wheel、前端、P24/A50通过；父包PG smoke执行至新P26验证器清理阶段失败，原因是验证器调用不存在的 `DatabaseRuntime.engine` 属性。已核对真实运行时有公开 `dispose()` 资源关闭方法。
- 专项claim断言此前已全部执行至finally清理，初步路径证据符合预期，但父包PG smoke以非零退出且P26没有正式Summary，故本轮不能作为PASS验收。无生产代码、Schema或Migration故障；未运行HTTP、插件或文件生成。
- 父PG smoke finally停止了D盘runner temp中的临时服务并删除本轮专用根目录；合成子库没有打包/上传。仅修正验证器以调用 `DatabaseRuntime.dispose()` 后，由同一父包PG hosted job重跑。禁止在本机/C盘复现。


## 第二轮 hosted 验证与结果（2026-11-05）

- Run [41931429638](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41931429638) 的14个作业中13个成功、1个失败。后端4,023项测试和wheel、前端测试/typecheck/build、PG18/pgvector sidecar、父包组装、父包PG lifecycle smoke、A17、A34、A35、A50及P24均成功；P25仍在 `initdb.exe` 创建数据目录前以 `3221225781 / 0xC0000135` 失败，真实Output HTTP/Edge未执行。
- 父包PG smoke内的 P26 专项验证返回 `PASS_SCOPE_LIMITED`：generic claim取得3个非Output组合，且未取得Output Generate；Output专属claim取得两项 `output/OUTPUT_GENERATE`；fencing token正确。合成验证没有Schema变化、插件执行、输出文件、外部API或客户数据；临时PG服务在GitHub hosted Windows Server 2025 runner的D盘生命周期内关闭并清理。
- 第一轮cleanup偏差只影响验证器资源回收：已先记录后改用 `DatabaseRuntime.dispose()`。本轮验证摘要完整生成，P26按限界范围完成；P25独立阻塞不被此结果覆盖。
- **结论：OUT-01-A01-P26 = PASS_SCOPE_LIMITED。** 兼容性仅涵盖托管Windows Server 2025 runner上的合成PG18.6/pgvector0.8.6 claim隔离与同run流水线，不是Windows 11实机或生产Worker证据。无API、Schema、Migration、安装包升级或业务数据迁移；回滚可撤回claim边界变更，保持无消费者时Output job排队失败关闭。
- 后续编码前检查应先确认Output Worker不存在时的下一安全边界和可验证输入；在正式Publisher/插件执行信任链就绪前，不得新增真实渲染、插件执行或成功发布路径。
