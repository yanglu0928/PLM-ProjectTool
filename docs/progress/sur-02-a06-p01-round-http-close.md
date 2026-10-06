# SUR-02-A06-P01：Round CLOSE、七 HTTP 与 Windows 组合

日期：2026-10-06。结论：`SUR_02_A06_P01_ROUND_HTTP_CLOSE_PASS`。下一项：`SUR-02-A06-P02` Round 前端与 Windows 真实浏览器闭环；随后进入 `SUR-03-A08/A09` Assignment/Response HTTP、组合与前端。

## 实现

- CLOSE 在已完成项目授权后，于同一事务调用 A07 完整性 Owner；锁定 OPEN Round、全部 Assignment/当前 Answer/Evidence，保存服务端生成的32字节报告指纹，再原子写 CLOSED、Audit 与幂等回执。重放只读取已提交终态，不重复证明或写历史。
- 新增冻结七 Operation 的严格 HTTP：Round LIST/CREATE/GET/PATCH/OPEN/CLOSE/CANCEL；强 UUID、JSON 字段集合、UTC `Z` 时间、If-Match、Idempotency-Key、Session/CSRF/Origin 和安全错误映射，默认未注入 Router 时保持404。
- Windows只读组合增加LIST/GET，写组合增加其余五项；生产启动在Document读取/下载/Parse Result就绪后注入真实Evidence固定来源证明。缺少一部分依赖整组启动失败；为兼容历史内部验证，全部未提供时CLOSE保持显式`SURVEY_ROUND_COMPLETENESS_UNAVAILABLE`。
- Round cursor 使用现有`survey-cursor-v1` Secret按固定`survey-round-cursor-v1`标签HMAC派生独立32字节用途密钥，避免引入第三份目标账户Secret，不与Survey列表token跨域复用。

## 验证、兼容与回滚

- Windows 11 / PostgreSQL 18.6：真实Session/项目角色、完整Assignment/Answer/Evidence、生产Windows组合和HTTP完成CLOSE、同Key重放、Audit/receipt单写、列表/详情、终态再关闭拒绝及Alembic drift，结果PASS。
- 契约/单元定向13项、11子断言PASS；后端全量`2905 passed / 3 skipped`、`4203`子断言；开发wheel `1085`项，SHA-256 `7fc7d8e4a9c0e295c05898c7f9df248536701cf8398453854f792ea0d81c95d1`。该wheel不是最终交付安装包。
- 无Schema/Migration、依赖、网络外发或冻结URL变化。应用回滚可撤Round Router/生产Owner注入恢复404/失败关闭；已经提交的Round、关闭指纹、Audit和receipt历史必须保留。

## 已知问题

本项只完成后端CLOSE与七HTTP；Round前端和真实浏览器闭环尚未完成，因此`SUR-02-A06`尚未整体关闭。Assignment/Response HTTP/UI、Conclusion、完整模拟项目、Gate 3/UAT、Windows Server 2025发行复验和可使用程序包仍待；Debian 13实机按用户指令跳过但仍为正式兼容目标。
