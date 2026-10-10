# JOB-01-A06-P07：一次性 PG18 Jobs 只读链复验

2026-10-02 / Phase 2 / INTERNAL_PASS（后端隔离数据库与 ASGI）。输入：Gate 2 Job 读合同、已验 `JOB-01-A05-P05` 列表和 `JOB-01-A04-P04` Document 详情；当前前端 P01～P06 已有 jsdom 合同测试。编码前检查：固定测试端口55432无服务、D盘已验证候选含PG18.6、Python3.13 venv可导入当前 backend。只新增验证编排，涉及 Jobs/Audit/Document 原矩阵，不修改产品实体、API、权限、Migration 或依赖。

新增 `validation/job-01-a06-p07/verify.py`：明确传入仓库、PG binary、Python、ASCII临时根；拒占用端口或非PG18.6、在指定根下创建唯一直接子目录，绑定127.0.0.1:55432并仅用一次性trust测试账户。执行既有 Windows Job列表双Factory/双Owner矩阵和Document Job详情双Factory矩阵，要求各自完成标记；最终按原数据目录核停机并仅清理受控直接子目录。失败停机或目录边界不符保留现场，绝不操作已有数据库。新增2项路径/缺二进制防护单元。

Files：`validation/job-01-a06-p07/verify.py`、`test_verify.py`。Migration/API/依赖：无。兼容性：仅独立验证脚本，当前程序行为不变；不创建客户数据或正式秘密。升级/回滚：无数据迁移，撤验证脚本即可。

实测：Windows11 / PG18.6 / Python3.13.15，Job列表与Document详情原矩阵各自完成标记、总退出0；防护单元2/2。原矩阵在真实隔离PostgreSQL/ASGI下覆盖当前Session、Scope/Owner、分页、License拒绝、正式信任缺失拒启动及读无写；其中正向License/游标仍为显式合成测试注入。验证后55432无监听，`D:\PLMTemp`无 `plm-job-read-matrix-*` 残留。本项没有使前端真实浏览器/HTTP监听服务、正式账户、Server2025/Debian或Gate3变为已验证。

Next：按当前源重建非发行 Windows 候选，复核新增 Jobs 前端资产与包内后端；正式 License/NOTICE/质量与发行Gate仍开放。
