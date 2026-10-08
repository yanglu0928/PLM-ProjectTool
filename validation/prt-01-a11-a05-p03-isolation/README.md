# PRT-01-A11-A05-P03-A03-P02：跨项目与撤权

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p03-isolation/verify.py'
```

只在隔离PostgreSQL18.6/pgvector随机库中生成第二项目和独立的合成PM（项目成员约束不允许同一用户同时属于两个未移除的项目）。用第二项目经理及ProjectId关联第一项目Requirement/Approved PrototypeVersion应被正式Link服务拒绝，第二项目不得形成Link。随后在第一项目临时暂停其PM成员身份，资格GET与Checklist写均应拒绝且不产生Prototype记录；恢复测试夹具后才允许真实文件、Link、Checklist与SOLUTION正向链。脚本退出时删除随机库，停止并清理本轮PG实例/Temp目录。

暂停/恢复为临时库故障注入，不是生产成员操作，也不代表客户确认；不验证更多角色组合、并发或其他目标平台。
