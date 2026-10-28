# PLT-PKG-01-A09-P51-A23：包内生产入口安全拒绝验证编码前检查

- 日期：2026-10-28
- 状态：编码前检查通过；目标是当前Windows父包中生产API入口的缺凭据安全拒绝，不尝试使生产服务成功启动。
- 输入：A22父包及run 40609229745 smoke证据、当前Windows生产入口、当前D盘runner目录/临时PG smoke工具。
- 执行环境：只允许GitHub hosted Windows Server 2025 runner；所有解包、数据根、配置、日志及进程归属都限于runner临时D盘。绝不在用户本机执行，绝不接触 `C:\PLMTool`、用户现有数据库或服务。

## 编码前检查

- 父包运行时位置：`payload/runtime/python.exe`；应用包位于 `payload/runtime/packages`。
- `serve_windows` 只允许回环绑定，错误时以固定、无敏感信息的消息退出。生产应用组合先从当前Windows Credential Manager读取数据库凭据，再构造生产API；没有Vault目标时应在绑定端口前拒绝。
- A22父包manifest明确报告产品公钥缺失，`PackagedProductKey` 和License组合根也会fail-closed。A23测试不注入或伪造公钥、凭据、License或数据库。
- 当前父包runner smoke已清洁解包、哈希验证并在相同runner临时D盘启动独立临时PG。A23复用此测试生命周期，先检查数据库凭据目标不存在，再运行包内生产入口；如Vault意外存在，跳过启动并将结果记为不可验证，避免触及任何不明数据库。
- 当前 smoke workflow已在 `.github/workflows/cloud-sandbox-validation.yml` 中连接，代码在Smoke结束前执行，可由同一实际构建的父包进行验收。

## 单一问题与实现计划

在现有 hosted parent smoke 中补充包内 `serve_windows --platform-write` 的受限负例：
1. ZIP清洁解包和manifest/hash校验完成后，确认固定数据库凭据target不存在；若存在则禁止探测。
2. 在新建的runner D盘Temp数据根生成最小非敏感bootstrap YAML，随机选择一个loopback端口。
3. 清理环境中所有 `PLM_*` 与 `PYTHONPATH`，用包内Python隔离模式启动入口，要求标准输出为空、退出码为1且stderr精确为固定拒绝消息。
4. 通过重新绑定所选端口确认没有API listener；报告仅说明无凭据/信任时失败关闭，不把它称为正式License验证。
5. PG smoke、服务探测、配置和数据临时文件完成后清理runner拥有资源。

## 首轮偏差记录

- 首次run `40611975169` 在凭据查询前因helper缺少`sys`导入停止，尚未执行包内进程；修复后run `40613037995` 在包内运行时路径校验拒绝，亦未执行生产入口。依据embedded backend打包器，实际布局为`payload/runtime/python.exe`和`payload/runtime/packages`；同步修正路径后从全新hosted构建重验。失败run不计PASS。

## 风险、回滚与验收

- 该探针实际启动包内Python进程，但只在GitHub托管Windows runner上、以无Credential的合成配置运行；不存在真实数据库连接串，也不向外部服务发请求。
- 如果误检测到runner上预置数据库Credential，探针必须跳过而非读取目标秘密或启动服务，记录为 `SKIPPED_EXISTING_CREDENTIAL_UNSCOPED`。
- 仅改云端 smoke 探针及其证据字段，不改产品API、License、数据库Schema、Migration、安装正式根和SCM。
- hosted workflow需重新跑 backend/frontend、相同commit父包装配及完整父包PG/startup smoke；清洁解包、PG生命周期、启动固定拒绝消息、API端口未绑定、临时目录/进程清理均通过才记 `PASS_LIMITED`。
- 回滚时移除探针与输出字段，不动产品代码/许可证书信任。
- Secret检查：不输出Credential数据、环境值或配置内容；仅保存凭据target存在性布尔结果，实际配置/日志留在D盘临时目录并清理。
