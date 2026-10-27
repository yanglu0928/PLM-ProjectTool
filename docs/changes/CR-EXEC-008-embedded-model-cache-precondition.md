# CR-EXEC-008：为隔离嵌入式运行明确模型缓存与用户目录

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-007、PR #52、PLT-PKG-01-A09-P51-A17

## 证据

run `40452182840` 中 wheelhouse 解析/安装成功（94 个发行包，当前直接运行依赖齐全），随后 isolated embedded import 进入 PaddleX → ModelScope 的模块初始化。ModelScope 调用 `Path.home()` 创建默认 cache 路径，而先前最小化测试环境未指定 profile/home/cache，因此报 `RuntimeError: Could not determine home directory`。未生成 candidate artifact。

## 决策与边界

云端验证器在隔离进程中显式设置临时 `USERPROFILE`、`HOME` 与 `MODELSCOPE_CACHE`，均指向 runner 自有临时目录，并重试关键模块导入。该变量只用于构建/验证。它不代表生产服务账户、模型离线预置或安装数据目录已通过验收。

后续正式启动脚本/安装配置必须将模型缓存写入产品受控数据目录并授予服务账户最小 ACL，不能依赖用户 profile 或写入安装目录；这作为真实安装/服务账户独立验收项持续跟踪。无架构/API/Schema/Scope 变更。

## 风险、回滚与验证

云端 smoke 成功只能证明显式 cache/profile 下模块可加载。若模块又要求额外运行时目录，记录实际依赖后继续处理。失败即停止上传。回滚为不产生本次 artifact；不改动历史 P45。本次只使用 synthetic/local runtime data，不接触客户资料或 secrets。
