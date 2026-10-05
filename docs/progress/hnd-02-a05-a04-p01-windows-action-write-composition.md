# HND-02-A05-A04-P01：Windows Action 写组合

日期：2026-10-05。结论：`HND_02_A05_A04_P01_WINDOWS_ACTION_WRITE_COMPOSITION_PASS`。下一项：`HND-02-A05-A04-P02` Win11/PostgreSQL 18 组合 HTTP 闭环与 CLOSE 失败关闭验证。

## 实施结果

新增 Windows Action 写组合，在显式Platform写模式挂载CREATE/PATCH与五个生命周期Router；只读Platform模式仍只挂LIST/GET，默认/login-only不开放。组合复用真实UOW、Session、License、Audit、Project授权、受理人、Document、Evidence、幂等收据及七个SQLAlchemy Action Repository。

按`CR-HND-008`，当前仓库没有Survey/Requirement生产Trace Target Owner。组合仍装配真实CloseService和TraceResolutionProofService，但默认显式空Owner注册表，使CLOSE稳定失败关闭；工厂只接受显式真实`TraceTargetProofService`向前补齐，不使用合成Owner或直信Trace行。其余六写不被该独立缺口阻断。

wheel生产入口复验发现AI/Document两个API目录缺少包标记，导致源码可运行而安装包无法导入`production_login`。已补最小`__init__.py`，扫描确认其余含Python文件的模块目录均具备包标记。

## 客观验证

- Windows组合/生产入口专项34项通过；显式写模式调用Action写工厂，只读模式不调用。
- 后端全量2714项通过、3项跳过。
- Win11/PostgreSQL 18分别复验CREATE、PATCH、START、SUBMIT、VERIFY及CLOSE/CANCEL Owner；Alembic无新增漂移。CLOSE正例使用验证脚本合成Owner，只证明机制，不冒充生产Owner。
- wheel重建后从wheel导入Action组合与`production_login`通过；SHA-256 `99d9a79dd65c45d5aec31abfc36dc18926ff9c28f0a65ca2be9a86a830b687e7`。

## 兼容、回滚与未关闭项

无Schema、Migration、冻结URL、依赖、Secret、网络、外发或客户数据变化。包标记只修复wheel收录。撤生产入口两个Action写Router注入可恢复七写404，业务历史保留。

当前P01只证明组合结构、生产模式隔离、Owner真实PG能力与安装包可导入；尚未用同一真实ASGI/HTTP/PG链证明六写和CLOSE的稳定422/零状态变化，因此A04未完成、Gate 3未关闭。P02继续补该证据。
