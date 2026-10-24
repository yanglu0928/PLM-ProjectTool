# PKG-PILOT-01-A04-P06：新候选交接分析创建包内验收

日期：2026-10-24；状态：`IN_PROGRESS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P06`；从 `HND-05-A01` 已验源码重建非发行候选，验证项目文档固定版本选择→交接分析创建|
|输入基线|CR-EXEC-002、已冻结 `/api/v1`；源码提交 `5ce82bff`，P45 固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、Python pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`|
|前置|HND-05-A01 定向16、前端全量1879/typecheck/build PASS，提交已同步 origin；既有非发行候选包内 PG/API/Caddy/合成License/Edge项目创建 PASS。父包及 wheel 重算 SHA 后才重新组包。|
|模块/实体/API|仅受控非发行打包与验收夹具；Document/DocumentVersion、HandoverAnalysis、Audit/Receipt；使用既有上传/文档元数据/冻结 Handover POST，不改产品 Schema/API。|
|权限/安全|一次性合成 ProjectManager、隔离 PG/测试 License/自签 HTTPS；不外发客户资料、不保存私钥、不将合成信任写入候选；不把真实文档或客户确认当作夹具。|
|验收|包体清单/逐件哈希、清洁暂存、同 SHA；Edge 选择固定版本并创建交接分析、回读详情；PG 验证来源集合/单 Analysis/Audit/幂等收据，异常/跨项目/无来源拒绝；临时 Vault、进程、安装布局清理。|
|风险|本次新增 UI 不在旧候选；来源必须由文档安全上传产生并处于 AVAILABLE，不能伪造；现有包内浏览器夹具可能不包含写流程。若完整证明无法完成，分别记录完成片与客观阻塞，不虚报 Pilot。|

本项未获得正式发行公钥/服务账户/CA/法律放行；只允许一次性合成非发行验收。新候选不可称安装包或交付包，正式 Gate/Pilot 维持 `NOT_READY`。
