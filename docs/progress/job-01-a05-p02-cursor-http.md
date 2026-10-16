# JOB-01-A05-P02：加密游标与可选列表HTTP

2026-09-27编码前PASS：Phase2/输入API-01/03、CR-JOB-005、0044及P01只读权限/keyset，涉及Jobs API/Page/Session/current Project/Admin/License。专用AES-256-GCM游标（既有cryptography）保护隐藏候选坐标、绑定family/Session/project/scope/page_size，fresh12-byte nonce，strict canonical token/payload、最长界限。游标不是权限，每页重验当前事实。

本项可选项目/admin GET列表与safe Job metadata及items/next_cursor/has_more；不返回私有position或伪造total_count。默认未挂、Windows专用密钥供给下一步，不复用别的密钥。无Migration/新依赖/角色/路径Breaking变更。验收：strict token/cross-key-family-session-scope-size/tamper/no coordinates、API query/Host/no-store/静态错误、实际PG稳定/稀疏分页/current授权、全测试。回滚撤可选router/cursor，保P01/详情/历史。

Changed/Files：JobListCursorCodec以既有AESGCM库保护canonical私有created_at/jobID、query绑定AAD与fresh nonce；strict prefix/base64/size/payload shape/canonical UUID/UTC时间，静态400。create_job_list_router实现冻结双Scope列表、strict query/Host/Session cookie及每页实际Service、safe metadata/no-store/nosniff；create_app可选参数，默认不挂。签名或完整性保护不透明token符合API-01，增加加密避免隐藏坐标明文，不更换技术栈。

Tests/Result CURSOR_HTTP_INTERNAL_PASS：5新cursor unit及4API contract，全后端1210无失败（2既有权限跳过）；随机密文相同位置不同token、内部packed无明文jobID/time/JSON字段、roundtrip/同key恢复、错误key/family-prefix/Session/project/scope/size/篡改/截断/超长/类型/非canonical拒绝。实际PG原三次PROJECT/GLOBAL来源及current Session/Project/Admin完整P01矩阵经可选ASGI执行：相同时间戳稳定分页/原source拒绝/角色customer原actor/撤权/License/隐藏空页继续，十三表逐次无写；next_cursor解密实际last-consumed privateposition且隐藏JobID不在空页响应、改页长400、default404。fixture成功/拒绝计数门槛及至少一次空延续实际满足，不以unit替代来源/权限验收。原当前权限HTTP/P02/上传回归通过。

开发wheel666121 bytes/SHA256 `752495c533824a9143f537d8fed78a12f6fc33165dec1d93c593e0ce2c91f795`，非完整包。本轮无测试失败，原TEST_ONLY credential/License/上传Access、专用测试cursor key明确合成；无真实Windows专用供给/备份恢复、生产组合/list Audit混排/性能/三平台/Gate3证据。Next P03 Windows Job-list独立KeyRef来源与临时Vault恢复，再Audit/Document实际矩阵及运行接线；CR保持打开，完整Scope不削减。
