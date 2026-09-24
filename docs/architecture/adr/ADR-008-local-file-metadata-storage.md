# ADR-008：本地文件系统正文与 PostgreSQL 元数据

## Status

`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN`

## Date

2026-09-22

## Context

项目需要保存合同、技术协议、调研记录、解析中间结果和生成制品。第一版为单服务器私有化部署，没有对象存储集群需求。文件必须支持不可变版本、证据定位、ProjectId 隔离、Hash 校验、备份和 Windows/Linux 路径兼容。

## Decision

1. 文件正文保存在本地文件系统，PostgreSQL 保存 FileId、ProjectId、Version、SHA-256、MIME、Size、Uploader、CreateTime 和受控 Storage Locator。
2. 逻辑区域固定为 `global`、`projects/{project_id}`、`generated`、`temp` 和 `plugin-data`；物理路径由 Storage Adapter 根据内部标识生成。
3. 上传链为隔离临时区 → 大小/类型/文件特征校验 → 流式 SHA-256 → STAGED 元数据 → 同文件系统原子提升 → 不可变 DocumentVersion → Parser Job。
4. 正式文件版本和生成制品不得覆盖；修订产生新版本，历史 Evidence/Trace 继续指向原版本。
5. 文件不得暴露为静态目录。下载、预览、解析和证据定位统一通过 DocumentService，并执行 Session、Project/Global、资源状态与用途授权。
6. 业务模块只保存 Document/Version/Evidence 引用，不保存或返回本地绝对路径。
7. 原始文件名仅作规范化元数据，不参与路径拼接；路径穿越、符号链接/重解析点越界、设备名和大小写碰撞失败关闭。
8. PostgreSQL、data、config 和 license 组成基线备份集；升级前进入维护模式并收敛 Worker，恢复时校验数据库元数据与文件 Hash/版本一致性。

## Consequences

- 单服务器离线部署、容量规划、备份和恢复较简单，无需 MinIO 等服务。
- 数据库与文件系统存在一致性窗口，必须通过 STAGED 状态、原子提升、补偿清理和恢复审计处理。
- 浏览器、业务模块和插件不能依赖物理路径；未来更换 Storage Adapter 时上层 Contract 保持稳定。
- Windows PostgreSQL 运行/数据路径在现有 PoC 约束下使用纯 ASCII；用户文件名可为中文，内部物理名使用标识。
- V1 不提供自动备份，实施团队必须执行并验证恢复。

## Rejected Alternatives

- 文件正文存 PostgreSQL 大对象：增加数据库体积和备份压力。
- MinIO/对象存储：当前单服务器无必要，增加安装与运维组件。
- 公开静态目录：绕过项目授权、审计和版本控制。
- 使用原始文件名作为物理路径：存在越界、冲突和跨平台兼容风险。

## Rollback / Change Rule

可在不改变 DocumentService 和 Storage Locator 语义的前提下调整目录与 Adapter。引入对象存储、网络共享或把正文迁入数据库属于架构与数据迁移变更，需 L3 决策、双写/校验/回退方案和三平台重新验证。

## References

- `docs/architecture/security-file-job-runtime-boundaries-v1-candidate.md`
- `docs/architecture/module-boundaries-v1-candidate.md`
- 《实施方案 V2.1》1.6、12.4～12.7
