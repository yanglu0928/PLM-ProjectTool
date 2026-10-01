# PLT-PKG-01-A09-P15：Windows统一+PG18非发行组合候选

日期：2026-10-01；状态：`NON_RELEASE_COMBINED_INTEGRITY_AND_SYNTHETIC_PG_PASS / RELEASE_BLOCKED`。

编码前检查：Phase 2/Gate 3 开放；P14已逐字节核P10/P12两个固定ZIP、目标路径零冲突，机读计划SHA-256 `6741b716c886f9128bf6c2bca6a60ff2f83ae3c07eefa82d521d6ee2348761ef`。本项仅从两份来源建新 Git 忽略非发行候选，重建顶层清单/双来源许可库存并全量验证；不修改产品/API/Schema/Migration、现有数据库、旧ZIP或正式安装根。若来源变更/路径冲突/Hash不符即拒绝；回滚弃用新ZIP并撤新增构建工具，保留历史候选。

新候选：`artifacts/package-prep/windows11/unified-pg18-candidate-c28b5e3cbe06/NOT-FOR-RELEASE-windows11-unified-pg18-candidate.zip`，518,659,603字节，SHA-256 `c54a7862872d402a6c9763287a508dc63dd602049f93aa6097e5a8e8e0766ef2`。19,474件P10统一载荷与1,629件P12 PG载荷逐件原字节保留，合计21,103件；新 manifest 明确 `release_eligible=false`、`legal_clearance=false`、`corresponding_source_included=false`、无安装/数据库启动，顶层第三方库存分别嵌入两来源原库存。构建时再次核P14计划与两来源整体Hash，写入中每件Hash、写后两来源整体Hash和新ZIP每件Hash通过。旧ZIP保持不变。

全新ASCII临时目录 `C:\Users\17231\AppData\Local\Temp\plm-unified-pg-stage-259814e0ae49` 解包后，21,103/21,103载荷及顶层3清单完整文件集/逐件Hash通过；包内 `pg_config` 为PostgreSQL 18.6。以此目录在独立临时数据目录、仅loopback随机端口完成 `initdb`、vector0.8.6、HNSW与最近邻纯合成查询；测试实例正常停机且临时数据清理。定向单元4/4。未对新组合重跑OCR四版面或真实文档质量；P10旧包OCR结果不能直接提升为本包的完整质量结论。

新ZIP仍不含正式客户许可/信任源、完成的产品及第三方LICENSE/NOTICE/对应源码义务、签名、安装器/服务账户/ACL/HTTPS、正式备份升级/Windows Server2025产品包验收；Debian13按用户指令暂缓但保留目标。不得关闭Gate 3或称可用发行包。下一项先对本组合包做只读安装路径/清单/门禁复核，再安排安全的隔离装配验证；任何正式安装及服务注册仍需客观前置满足。
