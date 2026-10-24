# AUT-04-A12-P03-A01 改密首次结果与重放证明

## 编码前检查

Phase2/Gate3未通过；WBS A12P03A01（P03持久化前置中的单一结果/证明任务）；输入64cdf09/API02、CR-AUT007，前置65c6a68受限身份已验。
模块Auth；实体User/前后PasswordCredential/改密首次结果；无本轮HTTP/Schema写。
权限：结果/密码一致性不授当前Session权利；后续服务必须当前有效Session-CSRF，仅新认证可恢复历史first，失效旧Session不授权新写。
验收：严格immutable首次DTO/前后版本+1/同User绑定坐标/合法时间/至少当前Session撤销；前后密码两项校验、严格bool、全部异常擦缓冲、无密码输出；后续真持久来源另验。
风险：纯DTO/source Port不证明真实Schema来源、Scrypt/原子改密或公开流程。

DEC-20260927-310：私有first绑定result/User/前后Credential UUID、前后credential和User资源版本、Audit/trace、撤销count及changed/accepted时间；公开只credential_version。重放必须两项密码分别交真实来源校验，false冲突、非bool/异常不可用；不存快速摘要、明文或新Key，mutable proof finally尽力擦除。先A01结果/证明，A02 Schema/真实来源，再原子服务/HTTP，不缩小完整改密Scope。回滚撤未挂入口保历史，无Migration/依赖。

## 实施与验证

2026-09-27 / 0.1.0.dev0 / PURE_RESULT_REPLAY_PROOF_VERIFIED_SCHEMA_PENDING。

- 新PasswordChangeResult严格不可变坐标/UUID/前后credential版本+1/User资源版本+1/bigint边界/至少一撤销Session/有序aware时间，公开仅credential_version，不包含密码或私有来源坐标。
- PasswordChangeProof两mutable密码隐藏repr，Verifier分别BEFORE/AFTER交Port；严格True匹配，False为幂等冲突，truthy/nonbool/源异常静态不可用。格式/NUL/非法UTF8/大小拒绝在source前；释放memoryview，成功/拒绝/异常均finally尽力擦除两缓冲。不替代当前认证。
- 9新增unit，全后端1357 tests无失败（2既有Windows权限跳过）。覆盖DTO/公开字段/不变性/边界、两个密码分别不匹配、非bool/源异常、坏载荷/结果不调用source、视图release及两缓冲擦除。
- 实际Scrypt内存独立前后凭据校验通过；交换密码、重复旧密码、UTF8新密码尾空格差异均冲突。这是实际KDF测试，但source为内存夹具，不证明数据库持久来源或换密事务；无本轮新PG/HTTP集成运行，不把P02历史回归冒充本轮运行。
- 开发wheel723773 bytes，SHA256 `bc96eaa9d603cb4feed6989b4f5c79d285b6d36f54d19b57ff84d3dd02f5339c`，仅构建检查，不是安装包，不提交wheel/密码资料。

兼容0047，无Migration/依赖/API/生产升级；回滚撤未挂结果/Proof Port保现有路径和历史。Schema/source真实性、当前Session-CSRF、原子改密/历史重放/提交确认恢复、HTTP/Windows/UI/性能/正式信任/三平台/安装包/Gate未完成。下一A12P03A02：owned first Schema/ORM/空与有数据升降、前后Credential/Audit/User/Session来源及不可变历史验证；再实际Repository与原子服务。
