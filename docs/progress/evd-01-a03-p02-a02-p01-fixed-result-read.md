# Document 固定解析结果受权读取

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P01`。结论：`WINDOWS11_INTERNAL_PASS`。Document 模块现在有供后续 Evidence 使用的内部固定 ParseResult 读取 Port；它不创建 Evidence，也不证明任何精确 Locator。

## 变更与边界

新增 `DocumentParseResultReadService`、Document 私有 `SqlAlchemyParseResultReadRepository`、7 项定向单元测试及隔离 PG18 验证脚本。读取链先复用现有 `PrepareDownloadService` 的当前 Session/Project/License 和文件完整性快照，再由 Document 私有仓储取同 Scope、Project、DocumentVersion、成功 ParseRecord 与精确 ResultRef。私有结果存储按绑定的路径、SHA-256 和大小回读，检查结构化载荷版本、源 SHA、Parser Profile/Version，最后重新取得受权文件快照和 ParseResult 元数据；撤权、变更或不一致失败关闭。返回值只含内部字节与固定身份，不向公开 API 暴露物理路径。

生产 API、权限规则、ORM/Schema、Migration、第三方依赖及发行包均未改变。接口目前未接入 Evidence 创建链，因而不能据此认定八种精确位置或 STRUCTURED_NODE 已验收。

## 验证

- 定向 7/7 PASS：成功链、读取中撤权、固定来源或结果漂移、字节篡改、缺结果及载荷源 SHA 不一致。
- Windows 11 隔离 PostgreSQL 18.6：临时簇执行当前 head Migration，合成成功/失败 ParseRecord、实际私有结果文件、跨项目/错版本查询、撤权和物理字节篡改均按预期；脚本退出 0，簇停止且临时目录清理。此集成的授权快照为受检合成 Port，不代替实际用户 Session/License 组合验收。
- Python 3.13 后端按测试包正确发现，1,736 项 OK（3 项既有环境跳过）；新 wheel 构建成功，两份新增源码均在包内，SHA-256 `6649114acf51a0c1cb3b3d8cd16a8d915537719895bdbf9af9f6e3e38f37fcf7`。最初两轮全量尝试分别因旧 PoC 环境缺依赖、错误测试发现顶层而失败，不计产品回归结论；纠正后完整重跑通过。

## 后续

下一项 `EVD-01-A03-P02-A02-P02` 应在 Evidence Application 经此 Document Port 验证单一实际节点和其原始 Locator，再逐格式扩大类型与真实文件测试；不得用整文档 Hash 冒充节点证明。当前还没有生产组合根装配、实际 Session/License/PG 一体化证据、SECTION 专用节点、所有格式精确位置或 Server 2025/Debian 发行验证。兼容性：仅内部新增 Port；升级无需迁移；回滚为不装配该 Port，既有不可变解析历史保留。Gate 3 和可用程序包仍未通过。
