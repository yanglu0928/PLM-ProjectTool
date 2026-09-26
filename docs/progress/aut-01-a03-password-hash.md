# AUT-01-A03 生产密码哈希与凭据校验验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结内容 `64cdf09` 的 DM-02/SC-02/API-02、`DEC-20260924-077`，以及 [OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)和 [Python 3.13 `hashlib` 文档](https://docs.python.org/3.13/library/hashlib.html)。
- 实现：Auth 模块内 Python 标准库 scrypt V1 Profile，16 字节随机盐、`N=2^17,r=8,p=1,dklen=32`、256 MiB `maxmem`；自描述编码、Profile 元数据双重核验、常数时间导出值比较、畸形/高成本参数拒绝。Hash Port 单独位于 Application Ports，基础命令输入上限为 1024 字节。
- 验收：Windows 11/Python 3.13 后端 110/110；PostgreSQL 18.6 临时独立库真实 Hash 存储与正确/错误密码验证、Profile 篡改拒绝、同事务 Audit、原始密码不落库及缓冲区清理 PASS。入口：`validation/aut-01-a03-password-hash/verify.py`。本机单次创建约 317ms，仅一次观测，不作 Release 性能结论。
- Migration/API：无新增；沿用 `20260924_0006`。无升级步骤，安装更新 wheel 即可。Windows Server 2025/Debian 13 未在本任务验证。
- 遗留：登录/限流、Session/CSRF、License 与真实 DeploymentAdmin 授权、凭据轮换/失效、三平台负载测试尚未完成；不得对外开放认证。下一项为 `AUT-02-A01 Session ORM/Migration`，Gate 3/UAT 未通过。
