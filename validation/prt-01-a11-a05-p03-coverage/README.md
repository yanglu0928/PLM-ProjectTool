# PRT-01-A11-A05-P03-A03-P01：部分覆盖与不计数目的

从仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p03-coverage/verify.py'
```

两次运行各用独立的隔离PostgreSQL18.6/pgvector与合成业务数据。第一次创建含两项验收标准的正式已批准Requirement，VALIDATES Link只覆盖第一项，第二项注明未覆盖原因；Coverage资格必须拒绝，随后通过正式Supersede补足。第二次用ILLUSTRATES Link填写全部覆盖字段，仍不计入Coverage；再用正式服务新建VALIDATES Link补足。两次均要求最终Checklist及SOLUTION推进通过，且退出前停机、清理各自的随机测试库和Temp目录。

此项不证明跨项目、撤权、多原型重叠、20并发、生产信任源或其他目标平台。
