# CR-EXEC-010：排除 future 依赖中的 badcert 测试夹具

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005/006/007/008/009、PR #55、PLT-PKG-01-A09-P51-A17
- 范围：Windows embedded backend 候选中 Python `future` 依赖的一个 PEM 测试文件。

## 证据

Hosted Windows run `40454671218` 通过完整后端、前端、PG18/pgvector 与 Python base 检查，并完成 embedded wheelhouse 安装。安全扫描确认 certifi CA bundle 通过其精确路径和仅公开证书内容校验，随后拒绝 `packages/future/backports/test/badcert.pem`；候选未上传。该文件路径位于依赖自带的 backports 测试目录，文件名表明其为证书错误案例测试夹具。

## 决策与差异

候选构建跳过且不打包相对路径精确等于 `packages/future/backports/test/badcert.pem` 的文件。其余敏感扩展名仍执行禁止策略，certifi CA bundle 仍必须通过 CR-EXEC-009 的路径及内容校验。被排除文件不参与 hash manifest；排除操作写入 manifest 的显式排除清单，保证可追溯。此变更只影响开发测试夹具，不影响 `future` 运行模块代码。

## 风险、迁移与回滚

- 若未来该文件改名或路径改变，仍由禁止扩展名规则拒绝，不会自动扩大排除范围。
- 依赖测试目录中的其他文件保持纳入与扫描，当前未证明其余测试资产不需要。
- 如排除项导致运行时导入或回归失败，停止上传并回滚本次精确排除。
- 不改变产品依赖、功能、架构、API、Schema、Scope 或发行边界，不代表 Pilot/Release 验收通过。

## 验证计划

在 hosted Windows runner 重跑全量 CI 与组包。验证精确排除记录出现在 runtime manifest；文件不会进入归档；其他 PEM/敏感类型仍拒绝；certifi bundle 校验、embedded clean-path 导入和逐文件 hash readback 通过。失败时不上传 candidate。该验证不覆盖完整 OCR 模型推理或安装器/服务 ACL。
