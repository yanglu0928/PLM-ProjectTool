# PRT-01-A09-A03：Prototype 五类签名游标与 Windows KeyRef 边界

日期：2026-10-08。结论：`PRT_01_A09_A03_CURSOR_PASS`。下一项：
`PRT-01-A09-A04` PrototypePackage 五项 HTTP 合同。

## 实现

- 新增Package、Prototype、Version、Template、RequirementPrototypeLink五类HMAC-SHA256游标；全部使用规范
  URL-safe Base64、固定字段集合和规范JSON重编码检查，篡改、未知字段、非规范编码或错误密钥统一映射为
  `REQUEST_MALFORMED`。
- 每类游标绑定32字节Session摘要、Project与页大小；Version另绑定Prototype，Template另绑定
  `GLOBAL/PROJECT` scope且GLOBAL强制无Project、PROJECT强制有Project。复合位置分别固定更新时间/身份、
  version_no或link_id，并保持Owner页大小上限（Version 100，其余200）。
- Windows组合使用五个固定、独立的当前账户Vault KeyRef；启动时必须一次取得五把不同的32字节密钥。任一
  缺失、类型/长度错误、重复密钥或Provider异常均返回静态启动错误，不自动生成、不复用、不从环境变量回退。

## 验证

- 单元10项、Prototype相关定向102项、后端全量3186项通过且3项既有环境条件跳过；compileall和
  `git diff --check`通过。
- Windows 11真实当前账户Vault使用五个UUID后缀临时KeyRef：装入五把随机密钥后组合成功；删除Version KeyRef
  后启动失败关闭；恢复原密钥后此前Package游标仍可验证。仅删除本次自有临时引用，结束后反查均不存在。
- 开发wheel共1221项，包含五类cursor和Windows组合，SHA-256
  `383100e924645ab3630084c15a1bb5c2937576d719792a619632d7aa9e930870`；不是正式发行包。

本项无Migration、公开路由、依赖、客户数据或网络外发；Schema head保持0134，A04前所有Prototype公开HTTP仍
关闭。正式目标服务账户KeyRef供给、ACL及恢复仪式仍是Release约束；Server 2025不从Windows 11外推，
Debian 13实机按用户指令跳过。
