# JOB-01-A05-P04：实际Audit/Document混合列表矩阵

2026-09-27 Phase2/编码前PASS；输入冻结API-03/0044、P01列表/P02密文游标/两Owner原源。单问题：同隔离库实际Audit来源与Document文件提交混排列表，不修改生产代码/Schema/API/权限/依赖。正式Parser属Phase3，不能用合成成功行替代执行。

Files/Changed：新增validation/job-01-a05-p04-mixed/verify.py复用原实际Audit publication callback。PROJECT/GLOBAL Document真实private staging/Hash/promotion/Upload/File AVAILABLE/immutable Version/原USER Audit/Job提交；只原上传Access/License合成，metadata源读取为实际Port。Audit PROJECT/DEPLOYMENT实际当前Session/CSRF/Project或Admin受理、原Root/Acceptance/Queue、领取/Lease/capture/render、真实temporary Vault SystemActor+private file/result/publicationAudit+SUCCEEDED，非直接SQL成功。

fixture说明：Document PENDING任务available_at只在该临时库调至未来，避免原Audit-only最后准入误领尚无Parser执行器的任务；列表不以available_at作为可见条件。此为明确测试调度隔离，不是生产时序调整或Parser执行。混合同timestamp只在临时库统一Job.created_at为原最早timestamp，确认UUID稳定排序，不改原提交/Audit/Version身份。所有fixture数据库/临时Vault/私有目录由原fixture最终清理，用户文件/正式材料不动。

Tests/Result MIXED_SOURCE_HTTP_INTERNAL_PASS：实际PROJECT同时Audit+Document、Admin同时DEPLOYMENT Audit+GLOBAL Document，无重漏且与当前登记Job集合一致；RUNNING Audit/PENDING Document列表正确，实际Worker发布后SUCCEEDED Audit返回原export逻辑ref。GLOBAL/DEPLOYMENT筛选、PM/IM两Ownermetadata、非creator客户空/creator客户受权原actor、Admin不绕项目/非Admin管理面/未知Session、受限Doc隐藏、License403、实际Audit Jobactor错误整页503通过；Owner原来源/pair/结果每项核验。相同created_at各Scope跨页严格UUID DESC。服务与可选ASGI均读取，十八表每次前后相同，无业务/技术/Auth写入。

本轮新验证器两次通过（第二次补IM/客户/Admin隔离），原发布260行/空导出/各故障回滚/竞争/实际最后identity损失回归随原fixture通过。无本轮unit/wheel重跑或变化，1213无失败/2跳过及wheel666815为P03历史非新跑；性能/三平台/正式License/浏览器/服务/完整Owner/程序包/Gate未验。不把本轮观察响应毫秒当P95。

回滚可撤新增验收脚本/文档不影响实现与历史。Next P05仅Windows两显式platform挂列表+专用KeyRef，default/login保持404、缺Key不得fallback；实际Factory两个Owner与缺源/构造故障回归后继续冻结重试/Outbox和其他Owner Scope，CR/Gate仍待。
