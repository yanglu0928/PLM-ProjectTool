# WBS 1.01 Module Layout Validation

状态：`VALIDATION_ONLY / NO_RUNTIME_CODE / NO_EXTERNAL_CALLS`

验证目录规范与冻结基线的一致性：

- 22 个 Runtime Module 与 API-05 的 65 Root Owner 集合一致；
- 依赖白名单与 Architecture Freeze 的允许依赖矩阵一致；
- 模块/层次依赖无未知项、自依赖或环；
- Developer Workbench 保持独立信任区；
- Windows 命名规则和要求的仓库入口存在。

运行：

```powershell
python validation/wbs-1.01-module-layout/validate_module_layout.py --write
python -m unittest discover -s validation/wbs-1.01-module-layout/tests -v
```

结果写入 `evidence/windows-11/result.json`。
