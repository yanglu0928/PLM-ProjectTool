# AUD-02-A04：Windows Audit 游标独立密钥来源

日期2026-09-26；Phase2；版本0.1.0.dev0；结果WINDOWS_CURRENT_ACCOUNT_TEST_PASS，正式运行账户供给/平台装配未完成。

## 编码前检查 / Changed / Files

输入A02专用HMAC、A03-P02可选HTTP及既有WindowsSecretKeyProvider/密钥备份生命周期；前置满足。仅处理专用key来源和恢复，涉及Audit cursor与既有Vault，无数据库/冻结API/角色/依赖或安全算法改变。DEC-20260926-189。

新增entrypoints/windows_audit_list_cursor.py：只读audit-list-cursor-v1引用，返回codec；默认Windows当前账户Credential Manager读取，缺失/异常/长度错误安全拒绝启动。无生成、自动轮换、环境变量/明文文件fallback。不得复用Secret、License或其他cursor密钥。普通应用与Windows平台路由仍未自动挂载。

## Tests / Result

- Windows11/Python3.13后端793项无失败，2项既有符号链接权限环境跳过。新增3项验证专用ref/签名往返、错误key/provider异常无敏感错误细节，以及真实当前账户临时Vault恢复。
- 每次唯一audit-cursor-test-UUID引用：真实Windows Vault供给、临时加密备份不含key hex、签名cursor、删除own测试引用后factory失败关闭、恢复原引用/key后旧cursor验证成功。finally仅删除own引用，测试后再次确认不存在；TemporaryDirectory清理自身备份。未读/改正式audit-list-cursor-v1或其他部署密钥，没有外发。
- A03-P02临时PostgreSQL真实Session/Scope/四个HTTP/keyset/当前撤权与读无写回归PASS，License仍为合成Guard。
- 开发wheel PASS，SHA256 `b851a0fcc458ee1ed9c77d08872dcb59fd1c5dc80af94af12cf448739cda0d57`；非正式安装包。

## Migration / API / Compatibility / Upgrade / Known Issues / Next

无Migration/Breaking API/角色/依赖变更，无数据升级动作。回退为不装配factory与Router；审计历史不变。正式部署须在实际运行账户通过既有交互式key生命周期供给专用引用并独立保管恢复口令/离线备份；运行时不得自动生成替代。丢失原key只能人工恢复才能延续旧cursor，新增key不是恢复。本次临时口令仅合成测试，不是正式供给或用户口令保管证明。

目标Windows11/Server2025/Debian13不变；仅Win11当前开发账户验证，异账户/Server2025未验，Debian暂不验证。下一项AUD-02-A05 Windows显式平台组合与缺Audit信任源失败关闭/真实Session HTTP回归。正式发行信任锚、服务账户供给、导出、Review真实Owner、Gate/性能/UAT/可用包仍待，不缩减Scope。
