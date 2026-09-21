# POC-09 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P09-A01|Python 3.13 / x86-64 / cryptography|PASS|PASS|NOT_RUN|脱敏环境 JSON|
|P09-A02|枚举 MAC 且必须显式选择|PASS|PASS|NOT_RUN|候选数量，不记录原始值|
|P09-A03|MAC Normalize 与 SHA-256 稳定|PASS|PASS|NOT_RUN|单元测试|
|P09-A04|Ed25519 正常签发和验签|PASS|PASS|NOT_RUN|正常 License 场景|
|P09-A05|MAC 变化拒绝|PASS|PASS|NOT_RUN|`LICENSE_MACHINE_MISMATCH`|
|P09-A06|过期与未生效拒绝|PASS|PASS|NOT_RUN|时间边界测试|
|P09-A07|Payload / 签名篡改拒绝|PASS|PASS|NOT_RUN|`LICENSE_SIGNATURE_INVALID`|
|P09-A08|错公钥拒绝|PASS|PASS|NOT_RUN|`LICENSE_SIGNATURE_INVALID`|
|P09-A09|异常系统时间与回拨拒绝|PASS|PASS|NOT_RUN|系统时间错误码|
|P09-A10|畸形文档与未知字段拒绝|PASS|PASS|NOT_RUN|失败关闭|
|P09-A11|License 核心逻辑覆盖率 ≥ 90%|PASS|PASS|NOT_RUN|同代码 Trace 91%～94%|
|P09-A12|私钥、原始 MAC、客户数据不落库/不入 Git|PASS|PASS|NOT_RUN|敏感信息扫描|

## 门槛

- 正常机器与有效期内的合法签名必须通过。
- MAC 变化、过期、篡改、错公钥、异常系统时间和畸形结构必须全部拒绝。
- License 私钥只能存在于开发者工作台；PoC 测试私钥仅驻留内存。
- Debian 13 未执行前，POC-09 不得标记为三平台完成。
