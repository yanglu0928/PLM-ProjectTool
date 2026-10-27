# CR-EXEC-007：重建 Windows embedded backend 的依赖清单

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005/006、PR #52、PLT-PKG-01-A09-P51-A17
- 范围：仅新云端重建的 Python embedded runtime 依赖清单及相关候选打包检查。

## 证据

Windows Server 2025 hosted run `40451488994` 从同提交 backend wheel 按其精确版本直接依赖解析 Windows/Python 3.13 wheelhouse，并完成安装到 embedded `packages`。解析包含全部当前 `pyproject.toml` 直接依赖，日志展示 backend 与 PaddleOCR/PaddleX/PaddlePaddle、FastAPI、SQLAlchemy、数据库、Office/PDF 等运行时包；实际分发数量为 94（含本产品 backend wheel）。流程在原型加载前因旧 builder 写死 106 个 distribution 而停止，未上传 candidate。

仓库旧工具在不同阶段分别假定 93 与 106 个发行包，且对应 wheelhouse/P45 runtime 已缺失；未发现可验证的锁文件或 12 个必须额外安装的包名单。

## 决策与差异

不为满足过期的 106 计数而猜测增加 12 项依赖。候选以同提交 backend wheel 的 METADATA 精确声明解析依赖；记录完整 wheel 名称、版本和 SHA-256；校验全部 pyproject 直接运行依赖（包含应用本身）存在；使用 embedded Python clean isolated process 导入关键业务及 OCR/数据模块；根据本次实际安装集生成 license inventory。发行/完整父包 builder 应校验 manifest、完整依赖集合与摘要，而非硬编码陈旧的历史数量。

差异仅涉及不可复用旧构件上的 distribution 数量断言；产品直接依赖、Python 3.13/Windows 目标、OCR 能力和发布安全边界不变。

## 风险、迁移与回滚

- 旧 106 项 runtime 可能含已不再声明或由传递依赖替换的包。对应组件不自动带入，避免无证据的软件供应链扩张；关键模块及完整 backend 测试保持验收。
- wheelhouse 的 transitive 版本不在静态 lock 文件中；本次候选 manifest 固定每个 wheel SHA 和版本。后续正式更新前可将该清单固化为新依赖锁，或在正式依赖已锁后复建。
- 未通过 import 或 wheel identity 验收即停止上传；回滚为不生成本次 artifact，并保留历史 93/106 记录。
- 不更改冻结 API、Schema、架构、Scope，也不代表法律审核、Pilot 或 Release 通过。

## 验证计划

在 hosted Windows Server 2025 runner 重跑当前 PR：检查直接依赖存在与版本，检查 94 项 distribution 清单、license inventory、wheel SHA、embedded clean-path imports 与完整包内逐文件 hash readback。完整源码 CI 与该组件验收需同时通过。
