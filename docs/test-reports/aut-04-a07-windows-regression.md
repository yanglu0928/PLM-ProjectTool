# AUT-04-A07 Windows关联回归报告

2026-09-27 / Win11 Python3.13/PostgreSQL18隔离库；25入口全部进程exit0，三个独立执行组，各脚本自行创建/清理唯一DB、临时文件与随机凭据。相关23历史正向fixture仅显式新增合成User cursor，未增加生产fallback；新列表运行及原HTTP亦验。

- PASS `validation/aud-02-a05-windows-platform/verify.py`
- PASS `validation/aud-03-a06-a04-p03-a06-p03-windows-composition/verify.py`
- PASS `validation/aud-03-a07-p02-windows/verify.py`
- PASS `validation/aut-04-a03-windows-user-detail/verify.py`
- PASS `validation/aut-04-a05-user-list-http/verify.py`
- PASS `validation/doc-03-a04-a03-p04-p02-a03-upload-platform/verify.py`
- PASS `validation/doc-03-a04-a04-upload-finalize-platform/verify.py`
- PASS `validation/job-01-a03-windows/verify.py`
- PASS `validation/job-01-a04-p04-windows/verify.py`
- PASS `validation/job-01-a05-p05-windows/verify.py`
- PASS `validation/job-02-a05-windows-cancel/verify.py`
- PASS `validation/job-03-a02-p05-windows-retry/verify.py`
- PASS `validation/prj-01-a04-project-create/verify.py`
- PASS `validation/prj-01-a05-project-read/verify.py`
- PASS `validation/prj-01-a06-project-write/verify.py`
- PASS `validation/prj-02-a01-member-read/verify.py`
- PASS `validation/prj-02-a02-member-create/verify.py`
- PASS `validation/prj-02-a03-member-patch/verify.py`
- PASS `validation/prj-02-a04-member-state/verify.py`
- PASS `validation/prj-03-a01-department-read/verify.py`
- PASS `validation/prj-03-a02-department-create/verify.py`
- PASS `validation/prj-03-a03-department-patch/verify.py`
- PASS `validation/prj-03-a04-department-deactivate/verify.py`
- PASS `validation/wfl-01-a03-p05-authorized-initialize/verify.py`
- PASS `validation/aut-04-a07-windows-user-list/verify.py`

后端1277无失败/2既有符号链接权限跳过。正向License/cursor/部分信任为明确合成注入；实际文件/Scope/Session/权限/审计/数据库/Worker按各脚本断言核验，不能外推正式账户/全部Owner/性能/三平台/最终安装包或Gate。无客户数据或日志文件提交。
