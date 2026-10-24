# JOB-01-A05-P01：当前受权任务列表内部服务

2026-09-27 Phase2/编码前PASS，输入API-03、CR-JOB-005、0044与原Owner/Auth/Project证明。只实现同UOW受权候选读取/Owner原源/私有keyset，不开放HTTP或游标。

Changed/Files：Jobs application authorized_list.py严格Query/Candidates/Page及当前Session/User/Project/License Service；read_repository新增Jobs-only稳定created_at/UUID倒序keyset、Scope/project/customer原actor和显式registry过滤/limit+1；Project新增冻结JOB_PROJECT_LIST四角色锁事实策略，客户创建者过滤在Jobs Service执行。每项Owner核真来源后JobFacts再读一致；资源不可见仅隐藏，不无限填页。next为最后消耗候选，允许空页继续；公开位置需CR中加密方案，不直接暴露隐藏JobID。无Migration/API路由/依赖/License变化。

Tests/Result INTERNAL_PASS：6新单位行为及全后端1201无失败（2既有权限跳过），真实原三次PROJECT与GLOBAL提交/currentSession/Project/Admin，PROJECT实际同时间戳三页UUID稳定无重复遗漏、PM/IM与原creator客户、非creator客户空列表、GLOBAL不含PROJECT及DEPLOYMENT过滤空；未知/撤Session/停用User/部门/暂停成员/跨项目/Admin项目/License拒绝十三表无写。真实Job actor错误整页静态拒绝，不隐藏坏来源；两个真实受限Doc版本隐藏后空候选页仍有限前進。每次列表及拒绝十三表快照不变，原当前权限HTTP/P02/上传回归随fixture通过。

首次全回归权限矩阵固定26项与新增合同操作不符；保留矩阵并增加第27项roles/read-lock/non-write断言，重跑全通过。扩展组合测试重复撤销原IM Session触发数据库invalid session transition，改用独立customer Session验证，不修改保护规则或复活会话，重跑实际验证通过。旧测试细节保留，未宣称首次通过。

开发wheel663139 bytes/SHA256 `e9a4420681310cdf5e371cdcaacb3ba7c1e8c6a6b67f2d919d1bf3471c9429fc`，非完整包。TEST_ONLY credential/License/原上传Access合成，非生产登录/许可。实际列表验证本轮仅Document Owner，Audit/混排/成功结果列表仍待；未知Owner不授metadata，完整Scope保留。公开加密游标/HTTP/Windows装配/性能/三平台/Gate3未验。Next P02专用加密游标与安全查询绑定，然后公开列表/实际Audit-Document矩阵/运行装配；回滚撤list/policy保旧详情/历史。
