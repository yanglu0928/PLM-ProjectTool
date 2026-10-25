# PRT-01-A09-A08：RequirementPrototypeLink HTTP

日期：2026-10-08。结论：`PRT_01_A09_A08_REQUIREMENT_LINK_HTTP_PASS`。
下一项：`PRT-01-A09-A09` Windows只读/写组合和真实PostgreSQL验收。

## 实现

- 一个显式注入Router公开冻结LIST、CREATE、REVOKE、SUPERSEDE四条路径；默认应用四项保持404。
- LIST使用RequirementPrototypeLink专属签名cursor，绑定Session、Project和page size，输出完整固定双端、
  purpose、Coverage V1、状态、创建事实、替换引用和只读ETag。
- CREATE/SUPERSEDE正文严格固定六字段；Coverage要求covered UUID列表与带非空reason的uncovered列表，
  Owner负责规范排序、全集分区、当前批准双端与Prototype固定RequirementRef证明。
- REVOKE仅接受空正文；三项写入均要求可信Origin、当前Session/CSRF及幂等键，HTTP不复制业务状态机。
- 冻结REVOKE/SUPERSEDE控制位没有M，故不新增If-Match。Owner内部仍传固定expected v0，数据库ACTIVE
  行锁与`lock_version=0`条件更新为最终并发裁决；响应ETag仅投影结果事实。

## 验证

- 3项合同测试覆盖默认关闭、四项成功、分页与跨Project cursor拒绝、严格JSON/Coverage、空撤销正文、
  Origin/Session/CSRF/幂等、Owner错误映射和畸形输出失败关闭。
- Windows 11 / Python 3.13后端全量3208项通过、3项按既有环境条件跳过；compileall和
  `git diff --check`通过。
- 开发wheel含1228项，SHA-256
  `f3ce39a4148fe6c2e76c568f282d489fbf77b1a271264ba9736fa4085fef9c9c`，包含新Link Router。

本项无Schema/Migration、依赖、Secret或外发；Schema head保持0134。真实Windows 11/PostgreSQL 18组合
留A09-A09，Server 2025不据此外推，Debian 13按用户指令跳过实机。
