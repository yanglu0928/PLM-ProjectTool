# CR-EXEC-008：embedded OCR 导入的显式用户缓存目录

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005/006/007、PR #52、PLT-PKG-01-A09-P51-A17
- 范围：仅 hosted Windows runner 上 embedded backend 候选的隔离导入探针。

## 证据

Hosted Windows run `40452182840` 已完成 Python 3.13.15 runtime 与同提交 backend 直接依赖的 wheelhouse 安装。在 embedded interpreter 的 `-I` clean-path 导入中，PaddleX 导入链进入 ModelScope，并调用 `Path.home()`；原进程未提供 `USERPROFILE` 或 `HOME`，因此探针以“无法确定用户目录”失败。该轮未上传 embedded backend candidate。

## 决策与差异

云端探针为当前 job 在临时工作根目录创建专属 `profile` 和 `model-cache`，显式设置 `USERPROFILE`、`HOME` 和 `MODELSCOPE_CACHE`，使导入测试只写入 runner 临时目录。该变更解决验证环境的隐式用户目录依赖，不改变产品配置、安全边界、模型分发或缓存策略。

后续 Windows 服务运行时仍需在安装/启动方案中确定受控模型缓存路径、服务账户和 ACL；本次探针不代表该生产前置已经验证。

## 风险、迁移与回滚

- 某些 OCR/ModelScope 初始化可能在导入阶段继续发现其他显式环境依赖；由 hosted runner 日志逐项定位，不放宽 clean-path 探针。
- 临时缓存不包含模型文件，不代表 OCR 模型可离线执行或功能已验收。
- 如导入探针仍失败，停止候选上传并保留诊断；回滚为移除此探针环境调整，原始失败证据保留。
- 不更改冻结架构、API、Schema 或 Scope，不代表 Pilot、Gate 或发行通过。

## 验证计划

在 hosted Windows Server 2025 runner 重跑源码 CI 与 embedded backend 组装。验收包括：显式缓存目录位于该次 job 的临时工作根目录；Python isolated clean-path 导入业务入口、OCR、数据库、PDF/Office 模块成功；生成的 wheel/runtime manifest 与 hash readback 完整；失败时不上传 candidate。该验证不包含真实 OCR 模型推理、服务账户 ACL、安装升级或用户验收。
