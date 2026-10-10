# PRT-01-A11-A05-P03-A01：需原型的单需求分支

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p03-approved-prototype/verify.py'
```

只用合成身份、Requirement、模板和文件；端口55434必须空闲。脚本在唯一ASCII Temp目录启动隔离PostgreSQL18.6/pgvector，复用真实Requirement→PROTOTYPE/v10验收，然后经正式服务创建PrototypeVersion、送审/批准和RequirementPrototypeLink。实际文件由本地存储发布并逐字节校验；缺Link、篡改文件均拒绝，完整Link/恢复文件后两项资格、Checklist PASS及到SOLUTION/v13的HTTP链通过。退出时删除本轮随机数据库、停止实例并只清理本轮目录。

此脚本不验证多Requirement混合NOT_REQUIRED/批准原型范围、并发、其他目标平台或生产信任源；客户角色审批为合成测试，不代表客户真实确认。
