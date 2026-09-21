# POC-09 License

## Status

`IN_PROGRESS / WINDOWS11_PASS / SERVER2025_PASS / DEBIAN13_NOT_RUN`

## Environment

- 目标：Windows 11、Windows Server 2025、Debian 13，x86-64。
- Python：3.13.x。
- 密码组件：`cryptography 50.0.1` 的 Ed25519 实现。

## Input

使用当前机器枚举出的 MAC 候选和仓库内合成 License Payload。测试私钥只在进程内即时生成，不序列化、不写入仓库、发行包或客户服务器；证据不保存原始 MAC、完整机器指纹或公钥。

## Steps

1. 枚举可用网卡，由调用方显式选择一个 MAC；缺少选择或选择不在候选中时失败关闭。
2. 将 MAC 规范化为大写冒号形式，再以 UTF-8/ASCII 字节计算 SHA-256。
3. 按字段排序和紧凑分隔符生成确定性 JSON Payload，由开发者工作台侧 Ed25519 私钥签名。
4. 客户侧仅使用公钥验证签名，并检查机器指纹、签发时间、生效时间、过期时间和运行期间时钟回拨。
5. 在 Windows 11 和 Windows Server 2025 执行正常机器、MAC 变化、过期、Payload 篡改、错公钥、异常系统时间、文档畸形和签名篡改场景。

## Result

Windows 11 与 Windows Server 2025 全部通过。两端均能生成不含原始 MAC 的 License Request，正常 License 验证通过；MAC 变化、过期、篡改 Payload、错公钥、系统时间早于签发时间、运行期间时间回拨、畸形文档和签名篡改全部拒绝。

## Metrics

- Windows 11：26/26 单元测试、10/10 验收场景 PASS。
- Windows Server 2025：离线依赖安装与包 Hash PASS；26/26 测试、10/10 场景 PASS。
- Python 标准库 Trace：License 91%、MAC 92%、SystemTimeGuard 94%，达到 License 不低于 90% 的目标。
- 两个平台：非法授权场景 8/8 拒绝；私钥落盘 0；原始 MAC 落盘 0。

## Logs

- 脱敏汇总位于 `evidence/<platform>/`。
- 完整本地结果位于 Git 忽略的 `artifacts/poc-09/`。

## Known Issues

- Debian 13 尚未执行，不得从 Windows 结果外推 Linux 网卡枚举或密码库兼容性。
- `SystemTimeGuard` 本 PoC 验证运行期间回拨逻辑；跨进程重启的可信时间状态存储、OS ACL 与防篡改策略须在 Architecture Freeze 时确定。
- 本 PoC 不冻结正式管理 API、数据库实体、License 文件安装目录或商业授权策略。

## Conclusion

锁定的 `人工选择 MAC → Normalize → SHA-256 → License Payload → Ed25519` 技术链在 Windows 11 与 Windows Server 2025 上可行，且已证明已列出的非法授权场景失败关闭。开发者私钥无需也不得进入客户侧。

## PASS / FAIL

`IN_PROGRESS`：Windows 11 `PASS`；Windows Server 2025 `PASS`；Debian 13 `NOT_RUN`。

## Alternative

若 Debian 13 后续出现密码库或网卡枚举兼容性失败，保留失败证据并触发 L3；未经确认不得替换 Ed25519、机器指纹算法或 License 核心机制。
