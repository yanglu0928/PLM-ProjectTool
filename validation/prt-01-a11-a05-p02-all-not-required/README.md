# PRT-01-A11-A05-P02：全 NOT_REQUIRED 分支真实 HTTP/PostgreSQL

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p02-all-not-required/verify.py'
```

脚本先确认55434端口空闲，再在唯一ASCII Temp目录启动隔离PostgreSQL18.6/pgvector。复用Requirement真实服务验收并在同一临时数据库中创建合成Prototype NOT_REQUIRED决定，验证默认路由关闭、缺决定拒绝、两项资格/Checklist PASS、PROTOTYPE→SOLUTION与幂等回放。该合成PM决定不代表客户签署；本脚本不验证需原型/Approved PrototypeVersion/Link/真实制品分支。退出时清理本轮数据库、停止实例并仅删除本轮临时目录。
