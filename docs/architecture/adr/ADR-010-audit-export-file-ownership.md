# ADR-010：内部审计导出独立归属与结果发布

日期：2026-09-26；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION / IMPLEMENTATION_PENDING。

## Context

API-02的DEPLOYMENT审计导出无法进入现有GLOBAL/PROJECT FileObject链路；PROJECT OutputArtifact需真实Plugin/DocumentVersion来源，不适用于内部安全审计投影。真实拒绝探测见AUD-03-A06-A04-P02。不得重标GLOBAL或制造业务来源。

## Decision

按CR-AUD-002增量扩展Document owned内部FileObject用途及部署归属，Audit own尝试与唯一不可变成功结果；Document/Upload/Parse/业务Output保持原Scope。新用途明确与普通文档隔离，存储仍本地文件+PostgreSQL元数据，不拆微服务，不引入对象存储/队列。

文件写入/Hash/fsync/不可覆盖提升不在数据库长事务内；当前权限/原来源/Lease/取消每阶段重核。通过公共caller-UOW Port完成元数据AVAILABLE+结果+Job终态+Audit同事务，DB提交前文件保持不可见。新generation独立文件标识，旧Worker不得发布/覆盖；恢复不根据路径存在猜成功。

## Consequences / rollback

新增Schema、受控存储区域及Owner公共契约，需真实升级/历史保护/恢复/竞争和下载再授权测试。性能/目标账户/三平台未验收。ADR-008原文件保留，本ADR仅补充审计导出归属/发布例外，其普通文档规则继续有效。回滚以CR为准，有专用历史拒绝down，不删除文件或成功历史。

## Trace

API-02 AUDIT_EXPORT → AUD-03-A06-A04-P02 → CR-AUD-002 → P03-A01～A03 → 后续Worker发布/HTTP验收。决策接受不等同实现PASS或Gate通过。
