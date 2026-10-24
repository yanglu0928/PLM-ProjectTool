# SUR-01-A05-A06：Survey 四读 HTTP 与签名 cursor

日期：2026-10-06。结论：`SUR_01_A05_A06_READ_HTTP_PASS`。下一项：`SUR-01-A05-A07` Windows生产组合与真实HTTP/PostgreSQL闭环。

本项复用A02已通过Windows 11/PostgreSQL 18.6验证的读取Owner，新增默认关闭的四读Router、Survey完整双字段cursor和Version父资源绑定cursor；固定投影保留类型化引用，不跨Owner复制正文/路径。无Schema/Migration、依赖、Secret、网络或外发变化。

验证：专项20项通过；后端全量2844项通过、3项跳过；wheel 1051 entries并包含两个新增模块，SHA-256 `f42547db0d917f6ee75c4456737702ba8e415e7a0ffc7381d1c15b12f4465dcf`。本项未挂载Windows生产组合，A07完成真实HTTP/PG组合证据；UI、Round/Response/Conclusion、Gate3/UAT/发行仍待。
