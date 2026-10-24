# JOB-01-A04-P03：成功解析结果原源

2026-09-27编码前：Phase2，输入API-03/DM-03/0044及P03原提交/当前权限，前置满足只读结果证明。已存在ParseRecord和不可变ResultRef（0028），Job无独立result列，不能把文档版本或空值当成功结果；不能Document查Jobs私有表。使用当前授权所得JobReadFacts与原Commit source，Document-owned只读Port核唯一成功ParseRecord及对应ResultRef的ID/hash/Scope/version/job与时间。

DEC-273：安全result_ref采用`{type: DOCUMENT_PARSE, id: parse_record_id}`逻辑记录引用，兼容原AUDIT_EXPORT与null，不返回opaque物理resultID或path，不授正文/下载权。原冻结文件不改；增量文档说明。无Migration/API路径/权限/依赖/License变更。历史ParseRecord attempt_no是版本/profile序列，不能猜等于Job attempt_count；唯一成功记录不随意选最新。缺失/歧义/状态/hash/原源不一致拒绝，不伪造结果。回滚撤新结果Port/type及Owner结果分支，历史保留。

验收：严格DTO、无路径输出、原成功Record/Ref坐标及hash/time、错误源拒绝；真实隔离PostgreSQL受约束ParseRecord及不可变ResultRef形状、全测试。隔离库直接构建Parser状态历史只能证明只读原源规则，不是实际Parser运行/Lease/发布/质量PASS。完整Parser执行与运行装配继续追踪。

Result RESULT_SOURCE_INTERNAL_PASS：Document ParseJobResultSource/DocumentParseJobResults及owned Repo，Owner可选真实results Port；未供给仍拒绝SUCCEEDED、不破坏旧caller。SQL仅Document表，核唯一成功/原job/version/scope、对应不可变ResultRef/hash/时间，原Job事实与Source来自受权caller，返回逻辑ParseRecord引用。4新unit/后端1195无失败（2既有权限跳过），精确Source/typed DTO/错误坐标/时间/异常静态化与无结果拒绝回归通过。

真实隔离PG/P02实际原上传：PROJECT第一旧Version与GLOBAL原Commit构建受数据库约束PENDING→RUNNING→SUCCEEDED ParseRecord及不可变ResultRef、Job状态，核唯一逻辑ref及错误原源拒绝十一表无写；第二成功ParseRecord实际入库后歧义拒绝，不挑选方便记录。Parser/Job状态直接fixture构建，无Lease/实际Parser/结果文件字节验证，本项仅元数据原源规则。原当前Session/双Scope可选HTTP权限、十三表无写/真实File-Version限制及原上传/P02来源回归重新通过。成功状态本轮未经实际授权HTTP（下一补），运行组合未注册。

开发wheel660423 bytes/SHA256 `1db70d4d027d0a20a9683e79da07db392555d5078ef3237df29569cd1c887377`，非完整安装包；无Migration/API路径/角色/依赖变化，需既有0044。曾补文档patch猜错标题被拒绝，按实际标题修正，无覆盖。下一成功状态当前授权HTTP验证/运行装配；完整Parser发布与原源/Lease/字节/质量、列表/重试/其他Owner、正式材料/三平台/Gate仍待。
