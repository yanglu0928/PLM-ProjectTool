# AI-04-A07-P03 Document-owned 建议来源定位

日期：2026-10-03；状态：`DOCUMENT_LOCATOR_PASS`；依据 CR-AI-020、DEC-771～773。下一项：`AI-04-A07-P04` AI Task 稳定受权分页。

编码前检查：当前 Phase 2；P02已通过。任务仅建立Document应用边界的固定ParseResult节点解析与V1文档级降级，不开放HTTP、不读取Suggestion表、不切换生产Prompt/Task策略。输入为当前Session/License/Project授权、固定DocumentVersion、固定ParseRecord和V2受控node id；涉及document/evidence兼容边界，无Schema/Migration。验收要求为当前授权重验、hash/来源漂移失败关闭、九类typed locator、固定版本content route、无物理路径/正文泄露，以及V1明确`DOCUMENT`而不伪造精度。

实现：新增`DocumentNodeLocationService`，调用既有`DocumentParseResultReadService`应用接口取得已重新授权并校验文件/result hash的固定结果；随后完整验证canonical Parser Result、文档/解析器身份、profile/version、node kind/source locator、OCR指纹、节点唯一性和请求node集合。服务从受信Parser结果生成`STRUCTURED_NODE`，模型和前端不能提交locator；结果只含node identity、受控locator、内容摘要、`PARSED_NODE`精度、无正文位置标签及固定DocumentVersion受权content route。`DocumentVersionLocationService`为V1历史在当前授权和AVAILABLE状态复核后仅生成`DOCUMENT`精度。定位结构校验从Evidence私有实现提取到Document domain，Evidence原函数/异常合同以兼容适配器保留。

兼容、升级与回滚：无数据库、Migration、公开API、新依赖或生产行为切换；Evidence已有调用方和九类locator返回保持一致。回滚可停止Suggestion读取装配并撤新增Document服务；若撤Document domain校验提取，须先恢复Evidence兼容实现，不能让历史Evidence失去解析能力。content route仍执行既有Session/License/Project/文件完整性检查，不是静态URL。

验证：Windows 11独立合成固定ParseResult证明精确节点、V1文档降级、未知节点拒绝、无storage locator/正文暴露，标记`AI_04_A07_P03_DOCUMENT_LOCATOR_PASS`；Evidence与Document定位定向61通过、95子测试；后端全量2314通过、3跳过、2960子测试；wheel 809项 SHA-256 `c388c7293bc6c2b3523c893102f6463ee38d2fbf709f63ec96761afe1aca41e3`。未访问真实Provider或客户数据，未使用Secret。Server 2025未复验；Debian 13按用户指令跳过验证但仍为兼容目标。

已知问题：服务尚未由Suggestion GET调用；P04/P05须先补Task/Invocation只读分页，P06再把Content Plan来源身份、canonical suggestion citation与本服务逐项绑定并重验当前授权。
