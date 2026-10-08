# PRT-01-A11-A05-P03-A03-P03：两个批准原型的覆盖并集

从仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p03-multi-prototype/verify.py'
```

在独立PG18.6/pgvector临时库中，一条正式批准Requirement包含两项验收标准；两条PrototypeVersion分别经正式送审与客户角色合成审批，并都固定该Requirement与真实DocumentVersion。起初两个VALIDATES Link均只覆盖第一项、把第二项列为未覆盖，Scope可预览但Coverage应拒绝。经正式Supersede把第二条Link改为只覆盖第二项后，验证两条当前有效Link的并集完整、两个PRT-03与一个REQ-03受审主体、Checklist PASS及SOLUTION推进。脚本只清理本轮随机库、PG实例和Temp目录。

合成审批不代表真实客户确认；本项不证明20并发、生产信任源或其他平台。
