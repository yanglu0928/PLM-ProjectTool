# AI-04-A06-P07-P04 Output Schema Owner 与响应解析

日期：2026-10-03；状态：`OUTPUT_SCHEMA_PARSER_PASS`；依据 CR-AI-018、DEC-756、P07-P02/P03。

新增代码内受信、版本化 Output Schema registry，首版登记 `gap-output.v1@1` 及现有部署示例兼容别名 `gap-analysis-output.v1@1`。结构只允许1～100条非正式建议，分类限定 `STANDARD_FUNCTION / NONSTANDARD_FUNCTION / DIFFERENCE / PENDING_CONFIRMATION`，每条必须包含有界NFC标题、摘要、理由、建议及1～32个升序不重复来源序号。来源序号必须属于本次授权Grant；模型不能提交formal fact、Owner/UUID、内容指纹或未知字段。P05再由受信Owner把序号解析为Schema0074 Evidence引用。

OpenAI-compatible响应解析严格要求单一choice、字符串content、纯JSON和`STOP`；外层与内层均拒绝重复键、NaN/Infinity、越界整数/浮点、Markdown fence、超深/超节点/超文本及未知Schema。输出规范化为最多1 MiB的排序UTF-8 JSON和SHA-256，响应正文与payload不进入repr；调用方仍持有Response并负责发布后清零。

验证：新单元4项/8子用例；Windows 11在真实Prepared Invocation/授权来源身份上验证有效建议、来源序号、规范JSON/指纹、未知formal fact拒绝与响应清零；后端全量 **2245项通过、3项既有条件跳过、2920子用例、无失败**；开发wheel SHA-256 `2fd6018406f032e0277531e3921dee8c0ded6ad8a6d581056b3ea347e3379a0d`。无Schema/API/依赖/真实Provider/Secret/外发。下一项P07-P05实现Evidence Owner解析及成功结果原子发布。
