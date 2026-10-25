# CAP-02-A05-P03-P02-A01：已停用条目的读写状态对齐

日期：2026-10-24；状态：`WINDOWS_11_SYNTHETIC_HTTP_PG_PASS / FULL_REGRESSION_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P03-P02-A01`；仅修复合法 DEPRECATED 版本条目不可读的合同冲突。多条目编辑作为 A02 独立任务。|
|基线/前置|Gate 2 原冻结 `64cdf09` 保留；`CR-CAP-007` 在修改前登记，按用户持续授权选方案 A；现有写 Owner/DB 均接受三状态。|
|模块/实体/API|Capability 读 HTTP 安全投影、前端严格读取客户端和回归夹具；现有路径/字段不变，`CapabilityItem.state` 枚举加入 `DEPRECATED`。无 ORM/Migration/新依赖。|
|权限与风险|管理员历史与普通用户当前批准投影、Reviewer 精确固定版本授权均不变。严格枚举客户端需随服务端同包升级；历史若已含 DEPRECATED，不能直接回退旧读取。|
|验收|合法写入后管理员 GET、受分配者固定条目 GET 回读原值；非法状态继续 503/前端失败关闭；现有权限、游标、License 和 Review 决定链不倒退；前后端定向、完整回归和构建。|

已扩展既有 Windows 11 隔离 PostgreSQL 18.6/HTTP 组合夹具的可选 DEPRECATED 路径，两个条目中首条为已停用；经真实版本 POST、管理员历史 GET、受分配 Reviewer 固定内容签名分页 GET、双人决定至批准及既有权限/License/游标拒绝矩阵退出 0。`Alembic check` 无新升级操作；输出有既有向量索引表达式/生成列比较警告，未把警告改称漂移或新增 migration。测试库已删除，PG 服务由停止态启动后恢复停止。独立 HTTP 合同 5 项（含合法/非法状态），前端读取客户端定向 5 项；前端全量 179 文件、1948/1948 与 typecheck/Vite build 通过。

后端完整 `unittest` 运行3781项（3跳过）退出0。限制：此为合成信任的本机 HTTP/PG，不是固定候选包内或正式公钥/账户/真人审批。Windows Server 2025、Debian 13 未实测。多条目编辑、正式安装/UAT/Gate/Pilot/Release 均不得据此宣称通过。
