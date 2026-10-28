# CR-EXEC-010：排除 future 依赖中的 PEM 测试夹具

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005/006/007/008/009、PR #55、PLT-PKG-01-A09-P51-A17
- 范围：Windows embedded backend 候选中 Python `future` 依赖的 `backports/test/` PEM 测试夹具。

## 证据

Hosted Windows run `40454671218` 通过完整后端、前端、PG18/pgvector 与 Python base 检查，并完成 embedded wheelhouse 安装。安全扫描确认 certifi CA bundle 通过 CR-EXEC-009 的精确路径及仅公开证书内容校验，随后拒绝 `packages/future/backports/test/badcert.pem`；候选未上传。经仅排除该路径重试后，run `40455605059` 在同一目录发现 `packages/future/backports/test/badkey.pem` 并停止，仍未上传候选。两者均位于依赖自带的 backports 测试目录，文件名表明为证书/私钥错误案例测试夹具。

## 决策与差异

候选构建仅跳过相对路径前缀为 `packages/future/backports/test/` 且扩展名为 `.pem` 的文件，并在 manifest 的显式排除清单中逐项记录实际路径。该目录下非 PEM 文件仍纳入扫描与哈希；此测试目录之外所有敏感扩展名仍执行原禁止策略。certifi CA bundle 仍只在精确路径和公开证书内容校验通过后纳入。排除范围局限于依赖自带的测试夹具，不影响 `future` 运行模块代码。

## 风险、迁移与回滚

- 目录下将来新增的 PEM 测试夹具会被排除并逐项记录；变更范围被固定目录前缀限制。
- 依赖测试目录中的非 PEM 资产仍保留；当前只针对 PEM 测试夹具。
- 如运行模块导入/测试证明这些夹具是运行必需，停止上传并回滚目录排除。
- 不改变产品依赖、功能、架构、API、Schema、Scope 或发行边界，不代表 Pilot/Release 验收通过。

## 验证计划

在 hosted Windows runner 重跑全量 CI 与组包。验证仅该测试目录中的 PEM 文件进入排除清单且不进入归档；目录外 PEM/敏感类型仍拒绝；certifi bundle 校验、embedded clean-path 导入和逐文件 hash readback 通过。失败时不上传 candidate。该验证不覆盖完整 OCR 模型推理或安装器/服务 ACL。
