# JOB-01-A02-P02：任务详情可选GET

2026-09-27/Phase2；编码前输入aa9f8e7、CR-JOB-001/002及冻结API-01/03，0043真实版本/内部读取前置满足。WBS单问题：既有授权读取接通冻结项目/admin任务详情GET；不同时做列表/写/生产组合。

实体JOB-01只读，调用原授权Service/Owner；API为原JOB_PROJECT_GET/JOB_ADMIN_GET路径，GET无CSRF状态变更，仍可信Host/Origin、严格SessionCookie/路径ProjectId/Trace、当前License/Role/Owner。默认应用不挂载，通过create_app显式Router依赖，无Schema/权限/依赖变化。

验收：实际JobView安全元数据、强ETag v<DB version>、no-store；错误脱敏与错误Envelope；缺/重复Cookie、Host/Origin、零UUID、未知query、跨项目/不存在、Admin项目隔离、撤权/许可拒绝；实际PG两Scope真实状态转换和版本，六业务表读不写，默认404。当前没有可证明的细分百分比/checkpoint/最终安全错误来源时返回null，不从payload/Attempt异常正文猜测；retryable由Owner当前策略供给（Audit无公开用户重试False），result仅受权逻辑引用，不授内容下载权。Document/其他Owner仍待接线，不宣称完整Jobs模块。

风险：版本只表示Job资源，不保证跨资源事务版本；If-None-Match不省略授权/不返回304，If-Match写命令后续实现。未知错误SYSTEM_UNAVAILABLE不泄露SQL/路径。回滚撤Router与显式create_app参数，不改旧读取/迁移；正式组合/信任/Gate/完整程序包仍待。先验证后追加结果并同步GitHub。

## 实施与验收

Changed/Files：modules/jobs/api/read_detail.py严格安全JobView及双路径GET、api/__init__.py、entrypoints/api.py可选挂载；contract/test_job_detail_api.py、validation/job-01-a02-p02-http/verify.py与本运行Contract。原内部读取/Owner/0043迁移不改；无新依赖/权限/Migration，默认/当前Windows组合不自动开放。

Tests：5新Contract tests，后端1150无失败/2既有权限跳过；默认404、明确字段集合/真实版本/no-store、项目/admin源绑定、成功逻辑结果引用、Host/Origin/query/零UUID/重复及畸形Cookie、错误Envelope/脱敏、If-None-Match仍读/撤权拒绝。真实隔离PG通过ASGI/TestClient复用原Auth/Project/Audit Owner链而非Mock Provider：双ScopePENDING/RUNNING/SUCCEEDED、当前PM/IM元数据/客户仅自身、Admin项目隔离、停用User/Department、未知Session、跨项目/不存在/actor错来源，8授权/13拒绝；每个矩阵读六业务表快照不变。追加实际条件请求撤销Admin仍401、坏Host403/query400，原发布回归通过。License明确合成，ASGI不是监听HTTP进程或浏览器验收。

失败记录：首次HTTP真实验证业务/权限断言均完成，但脚本误把成功数量下限写为10，实际完整矩阵为8成功/13拒绝；核对每个真实用例后改为明确精确数量，再完整复验通过，不删除业务用例/不改产品。

Result：可选GET已验范围INTERNAL_HTTP_PASS；不是Windows正式装配、所有Owner、列表/取消/重试、浏览器/UI/UAT/完整包/Gate通过。Known：progress/checkpoint/error当前无可验证来源为null，后续Owner须实现实际来源；正式公钥/目标账户材料、其他平台/性能仍待。Next：JOB-01-A03 Windows显式装配，并从真实会话复验默认关闭/缺正式信任源失败关闭，随后审计导出POST。

开发wheel构建通过：642375 bytes/SHA256 `cfac8a8e35ed9af116a77061f2c51ff8ff6f585947b05d40d7c3cf14e9691834`；不是完整安装包。
