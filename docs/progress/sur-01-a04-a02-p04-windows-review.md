# SUR-01-A04-A02-P04：Survey Review Windows 写组合与真实 HTTP/PostgreSQL

日期：2026-10-06。结论：`SUR_01_A04_A02_P04_WINDOWS_HTTP_PASS`。下一项：`SUR-01-A05-A01` Survey 定义剩余 HTTP Operation 与读取 Owner 前置核查。

## 实施结果

- 按 `CR-SUR-003` 新增 Review-owned `ProjectReviewSubjectRegistry`，以唯一 `SUBJECT_TYPE`失败关闭分派 create/start/transition/replay 全套回调；Windows平台仍只挂载一组冻结Review四写路径，同时注册 Handover `HND-02` 与 Survey `SRV-02`真实Owner。
- 将生产平台写组合从Handover单Owner Router切换为PROJECT多Owner Router。默认、login-only与只读平台不调用该工厂，未知Subject、重复或不完整Owner均失败关闭。
- Survey组合复用当前runtime/UOW、Session、Project授权、Reviewer资格、License、Audit、幂等收据、Review三仓储，以及四类来源证明和已验证Survey Owner；未在HTTP层跨模块写表。

## 客观验收

- Registry/组合新增6项单元测试；生产组合与Survey Review定向合计48项通过。
- Windows 11/PostgreSQL 18.6全新临时库、Schema head/drift下，以真实Session/Project/Survey来源完成create/start、目标部门漂移拒绝批准、恢复后批准、批准后升版、第二次create/start、来源漂移后withdraw；approve/withdraw原幂等键重放保持首次结果，最终V1 APPROVED且为正式指针、V2 RETURNED。
- 同一多Owner组合实际回归Handover create/start/approve/升版/withdraw及重放，标记 `HND_01_A04_A02_P04_WINDOWS_HTTP_PASS`；Survey原P02直接Owner链也重新通过。
- 后端全量首次出现1项既有随机RAG密文篡改单测偶发失败；该项连续独立3次通过，随后全量2816项通过、3项既有条件跳过。该偶发性不计为首轮PASS，也未修改RAG代码。
- 开发wheel 1040项，包含PROJECT Review Registry/组合及Survey Owner，SHA-256 `9334cdad39de0438c6fef6b9d40056c0ebe3b9bfc19c2fbad725fa8a0c2f825d`。

## 兼容、升级与回滚

无Migration、ORM、冻结API/DTO/角色、依赖、Secret、网络或数据外发变化。应用回滚可恢复原Handover单Owner组合，但会关闭Survey Review HTTP；数据库历史必须保留。验证夹具最初把目标部门与操作者所属部门共用，漂移时HTTP授权层先正确撤销操作者资格；改为独立目标部门后，才精确验证“操作者仍有权、业务来源已漂移”的撤回语义，产品代码未为夹具放宽。

业务`SURVEY_VERSION_SUBMIT_REVIEW`便捷端点、Survey创建/版本/验证/读取HTTP与前端、Round/Response/Conclusion、Workflow资格、Windows Server 2025、Gate 3/UAT及可使用发行包仍待。
