# JOB-01-A04-P02：解析Job的Document原始来源

2026-09-27/Phase2编码前PASS：原Upload Commit/版本/真实文件与P01只读Queue已验，输入冻结DM-03/04/API-03与0044。单问题：读取Document-owned真来源并经Audit-owned Application Port确认原提交事件；不能Document直接读Audit/Jobs私有表，不能Hint当当前权限/文件字节/Parser结果。

Document Source DTO/Repo锁定当前可见ACTIVE或ARCHIVED Document、COMMITTED SOURCE_UPLOAD、文件/不可变版本与UPLOAD ordinal0来源，精确Scope/project/actor/document/version/版本号/file引用与摘要/size/MIME、版本AVAILABLE/文件DOCUMENT/PERSISTENT/AVAILABLE；旧版本不要求等最新指针。Audit独立只读证明接口核唯一原USER DOCUMENT_UPLOAD_COMMIT/trace/actor/Scope/targetDoc-version/AVAILABLE/发生时间，不查询Doc私有表。协调只返回受控内部source，无路径/正文/Lease/下载权。

原P01把version_no误限int32，但DocVersion与Outbox aggregate_version均BigInteger；先记录修正至正bigint，不降低实际Scope/验收，不改历史DDL。无Schema/Migration/API/依赖/角色/License变化。DEC-271先记录，回滚撤新只读Source/Proof保历史；校正bigint上限应保留。

验收：严格DTO/错误源/无权读前置语义明确；真实PROJECT新/后继/故障恢复上传及真实GLOBAL私有文件提交完整Source/原Audit证明、旧Version仍可读、跨Scope/Actor/version/trace/Upload/Doc状态/文件限制拒绝、无路径/正文输出、十表无写；单位/原Queue/提交回归/全测试。原fixture权限与License仍合成，本项不装当前Auth/Owner/HTTP，不宣称Parser执行。Next当前权限Owner投影与双Scope实际Session核验。

实施/Files：Document parse_job_source.py Application DTO/Reader与owned Repo，只查自身Doc/Upload/File/Version/ordinal0来源；Audit upload_commit_source.py只读Application Query/验证Port与owned Repo，只查Audit事件，唯一原提交状态/actor/scope/Doc-version/trace/时间精确匹配。读取依次共享锁Doc/Upload/File/Version，不返回path/payload，Audit记录不可变无需跨表锁；当前事务/权限仍由未来Owner caller供给。P01公开validate_parse_read_request并修正正bigint范围，旧入队与Schema不改。

Result INTERNAL_PASS：Windows11/Python3.13.15后端1185项无失败（2既有账户权限环境跳过），4新Source/Audit严格单位行为。真实独立PG/私有临时文件，PROJECT三次原真上传提交（新/后继/失败恢复）与新增GLOBAL真实staging→Hash/promotion→File AVAILABLE→Version/Upload/Audit/Job提交，源读取全链匹配；GLOBAL实际字节摘要另验证，不再仅Queue元数据。原第一Version在最新指针已后继时仍可读；错actor/version/trace/Upload/Doc/Scope拒绝，真实Doc RESTRICTED拒绝；追加第二条实际同Version提交Audit使证明歧义，读取拒绝不挑选方便记录。每轮读取及拒绝九表快照不变。原P01 Queue/提交/文件回归通过。

范围校正：前文计划“十表无写”实际本项逐表九张（Job、Outbox、Upload、Document、Version、SourceRef、File、Audit、receipt），验证覆盖写链全部相关表，不能称十表；File/Version当前可见状态与元数据过滤已实现，但本轮实际限制转换只测Document，File/Version限制状态专项尚待，不冒充已验。原Upload fixture Access/License明确合成，本项无当前Session/角色/HTTP/Parser结果或执行证据，无生产操作。本轮验证无失败，曾猜错Public文件路径后按实际package读取，不影响实现。

开发wheel657150 bytes/SHA256 `9e64091f41e4dc09e098bcd3224d54cf6dee2ae859cafa05742516fa7d2e2a29`，非完整安装包。无本轮Migration/API/依赖/权限变化，Schema仍0044，撤新Source/Proof保旧历史回滚；bigint修正应保留。Next JOB-01-A04-P03：当前Session/Project或Admin授权下Document Parse Job Owner投影与真实双Scope读取；成功结果需另核实际ParseRecord，不猜结果或把读取当Parser已执行。其他Owner/列表/重试/正式材料/三平台/性能/Gate继续待。
