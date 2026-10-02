# CR-AI-012：AITask 外发授权快照完整性

日期：2026-10-02；状态：依 V1.1 持续授权登记，待Schema0067实施；关联冻结 API-03 `EgressAuthorization`/`AI_TASK_CREATE`、DM-04、Schema0064～0066、CR-AI-011；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A03-P06`。

冲突与证据：冻结授权必须固定 preview/payload fingerprint、批准主体/角色/时间、Provider 配置版本、Model/region、用途、数据类别、source version refs、最大载荷、有效期、授权状态和有界重试。0064 `ai_egress_authorization_snapshots` 仅保存 AuthorizationRef、purpose、Provider/Config、region、categories、单一 fingerprint、approver和时间窗；缺 Model、批准角色、源集合摘要、载荷/Token 上限、状态与重试边界。当前结构不足以证明后续 Invocation 没有扩大授权。

方案比较：A 把缺失值放入 Job JSON 或应用日志，无FK/不可变/安全投影保障，否决。B 把Model、上限等推迟到 Invocation，会允许在Task授权之后自由扩大，否决。C 以0067增量补充快照列；source refs 不复制一份明细，而是以同 Task 不可变 InputRef 集合加 `source_refs_fingerprint` 固定；新快照强制完整，0064～0066遗留快照允许NULL但不得执行，选择C。

设计差异：增加 `ai_model_id`、`approved_role`、`preview_payload_fingerprint`、`source_refs_fingerprint`、`max_payload_bytes`、`max_input_tokens`、`max_retry_attempts`、`authorization_state_at_capture`。新插入必须全部非空，Model 必须 AVAILABLE 且属于同 Provider，state 必须 `AUTHORIZED`，数值有界；快照仍不保存Key、SecretRef、Prompt或正文。应用层须对 Owner 快照和解析后 InputRef 集合计算相同规范化摘要，不同则拒绝。

风险与控制：旧快照被误执行通过新建服务只接受完整快照及 Worker 失败关闭控制；Model/Provider 错配由FK和守卫控制；超限与授权扩大由数值上限、指纹和每批次 Owner 重校验控制。快照只记录捕获时状态；撤销不改写历史，未开始/下一批次必须向Owner查询当前状态。

迁移/回滚：0067为快照表增加可空列以兼容历史，由INSERT守卫强制新行完整，不回填历史。无完整新快照时可降0066；有新快照时拒绝物理降级，向前修复或受控备份恢复。

验证计划：P07验证空库/旧快照升降重升、drift、新行缺列/Model-Provider错配/非AVAILABLE Model/非AUTHORIZED/超界/变更删除拒绝、正确快照和非空历史拒降；之后再实现 Owner Port 和原子创建。无真实客户数据外发。
