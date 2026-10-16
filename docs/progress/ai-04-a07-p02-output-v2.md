# AI-04-A07-P02 建议输出 V2 与精确节点验证

日期：2026-10-03；状态：`OUTPUT_V2_PASS`；依据 CR-AI-020、DEC-771/772。下一项：`AI-04-A07-P03` Document-owned 精确节点定位解析。

编码前检查：当前 Phase 2；任务只处理 Provider 输出信任边界，不开放 HTTP、不切换生产 Prompt/Task 策略、不实现 Accept/Reject。输入为固定 Content Plan、实际发送的 `document-minimum-text-v1` 投影和既有 Invocation；实体及数据库不变；公开 API 不变；权限继续由既有 Grant/Content Owner 在发送前复核。验收为 V1 历史兼容、V2 严格字段/大小边界、精确 node 白名单、人工维护提示、敏感引用不进入 repr，并拒绝越权或不存在节点。

实现：新增 `gap-output.v2@2` 和兼容别名。V2 用 `source_citations=[{source_ordinal,node_ids}]` 替代文档级序号，并要求 `confirmation={required,question,required_fields}`；只有 `PENDING_CONFIRMATION` 可要求人工填写，字段 key 限定为 ACTUAL_STATE、DECISION、OWNER、TARGET_DATE、SCOPE、CONSTRAINT、EXCEPTION、NOTES。准备服务从已经过 Owner 验证且实际进入 Envelope 的最小投影提取无正文 node catalog；Parser 将其作为唯一白名单，模型不能提供 URL、locator 或任意节点。citation/node 聚合与人工字段均有数量、字符、编码及 canonical JSON 大小上限，节点引用隐藏于对象 repr。

兼容、升级与回滚：`gap-output.v1@1` 与别名保留，旧历史仍为文档级定位；无 Schema、Migration、公开 API 或新增依赖。本项只注册 V2 校验能力，未启用生产 V2 策略。回滚可停止创建 V2 Task 并移除新注册项，既有 V2 canonical payload 不得删除，需由当前版本只读保留。

验证：Windows 11 独立合成验证接受已发送节点，拒绝不存在节点和缺人工维护提示，标记 `AI_04_A07_P02_OUTPUT_V2_PASS`；AI 模块 269 通过、301 子测试通过；后端全量 2308 通过、3 跳过、2944 子测试通过；wheel 807 项，SHA-256 `bc3466e072d1f0e5fe6f35c75a6bb3986525a839178f29d0ddbdf50177035aec`。没有真实 Provider I/O、Secret、客户数据或数据库变更。Server 2025 未复验；Debian 13 按用户指令跳过验证但仍是兼容目标。

已知问题：node id 已受信验证，但还没有转换为页/段落/单元格 locator 或受权 content URL；P03 必须由 Document Owner 对固定 ParseRecord/Result 复核后生成，不能让 AI 或前端自行拼接。
