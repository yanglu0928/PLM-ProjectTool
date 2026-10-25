# JOB-01-A04-P01：Document解析任务读取前置

2026-09-27 / Phase2，编码前核查：冻结API-03 Jobs全Owner读取、DM-03/04、现0044与原真实Upload Commit入队。现ParseJobQueue只有enqueue_parse，原重放调用会在Job缺失时创建，不能拿写接口证明只读详情；UploadIntent仅持Document/Version，不直接持JobId，不能从Document模块读Jobs私有表或猜payload。

选择补Jobs owned只读peek_parse_for_job（Hint）与find_parse（精确绑定且行锁，绝不创建）。严格Binding DTO含原ParseJobRequest与refs，原Job/Outbox owner/type/scope/project/actor/上传幂等key/精确JSON引用/aggregate版本/原trace一致。不返回原payload/Lease/错误文本给HTTP，不授Document/文件权限。Document Owner下一分项读取真实Upload/Version/File/Audit来源后调用find确认，hint不是来源或许可。现入队行为与历史不改变。

单任务只补此Port/Repository/DTO与验证；无Schema/Migration/API/依赖/权限变更，Scope保持GLOBAL/PROJECT。DEC-270先记录。验收：严格输入/错来源refs/未知owner/缺pair失败关闭且绝不enqueue或commit；真实旧Upload Commit产生的PROJECT任务只读peek/find、GLOBAL真实Queue元数据分支（不冒充已提交文件）、原trace/字段/错Scope/错ref/缺事件保护、Job/Outbox/Document/Audit/receipt快照无写，原提交/文件回归与全测试。回滚撤新只读Port，原历史保留。正式Doc来源/HTTP/Parser执行/性能/包/Gate待。

实施/Files：parse_enqueue.py新增严格ParseJobBinding及只读Port，原enqueue验证/行为不改；parse_enqueue_repository.py仅Jobs owned Job/Outbox按完整引用/trace核验，find持原Job→Outbox锁、不创建、peek只内部Hint。4新单位行为、validation/job-01-a04-p01-parse-binding实际验证；旧upload-commit验证仅增加可选exercise回调，默认行为保留。

Result INTERNAL_PASS：Windows11/Python3.13.15后端1181项无失败（2既有权限环境跳过）。真实独立PG/临时私有文件，原Upload Commit新版本/同Document后继/故障恢复三次PROJECT真提交产生的Job/Outbox与原Upload/Document/Version/版本号/actor精确匹配；原trace/actor/Document/version错请求拒绝，无Job/Scope/ref返回None不入队，八表完整快照无写。真实GLOBAL队列元数据读回与缺Outbox孤立Job拒绝同样无写；GLOBAL并无正式Upload/Version/File原源，明确不能冒充该Scope的Document Owner/文件授权。旧上传版本/父版本条件/重放/权限与License合成拒绝、实际Audit故障全事务回滚、最终文件恢复/坏字节保护原测试保留通过。本轮验证无失败，读取曾猜错文件路径后已按实际路径读取，不改变验收。

开发wheel653100 bytes，SHA256 `43683aac45c9d6957abe77e169b75c8b0651c068a03fe17d18c848a48b2fe141`，非完整安装包。Migration/API/依赖/角色：无本轮新增；应用仍0044。Known Issues：只读队列绑定不证明真实Document原源/当前Doc状态/File可用/ParseRecord结果，不授下载/许可/Lease/执行权，不自动公开或挂Windows。原Upload fixture的License/Access是显式合成，不能称真实当前Auth已通过。Next JOB-01-A04-P02：Document owned解析Job来源DTO/Repo与原Upload Commit Audit/Version/File关系核验，先真实GLOBAL/PROJECT来源验证再Owner装配；列表/重试/Parser执行与其他Owner完整Scope保留，正式材料/三平台/性能/Gate待。
