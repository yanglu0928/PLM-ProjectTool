# PLT-PKG-01-A08-P04：bce-python-sdk 0.9.79 精确发行来源核查

## 前置检查

- 当前 Phase：Phase 2 Platform Core；非发行许可调查。
- 当前 WBS：PLT-PKG-01-A08-P04，仅核查 `bce-python-sdk` 精确版本，不扩展业务 Scope。
- 输入基线：A01 原 wheel、A08-P01 无独立许可文件结论、A08-P03 非发行新候选；版本源为 [PyPI 0.9.79 官方 JSON 记录](https://pypi.org/pypi/bce-python-sdk/0.9.79/json)。
- 前置任务：A01/A08-P01/A08-P03 通过；正式许可义务审核未完成，只能做证据核查。
- 涉及模块：发行证据文档；无代码、实体、API、权限、Schema 或 Migration。
- 验收标准：wheel 与源码包均绑定 PyPI 精确版本 Hash；对比两者 Python 源文件；查明是否随包携带独立许可文本；不将元数据声明误写成许可合规。
- 风险：上游主分支当前许可证不能证明 0.9.79 分发物中的独立文本；不得将当前核查视为法律意见。下载源码包仅存 Git 忽略目录，可撤本地副本回滚。

## 核查结果

- [PyPI 0.9.79 官方记录](https://pypi.org/pypi/bce-python-sdk/0.9.79/json)的 wheel SHA-256 为 `71799ac8740505e0759d30873f6f1a478fa8f83aedf425d511f1419a5f30082e`，与 A01 原 wheel 一致；源码包 `bce_python_sdk-0.9.79.tar.gz` SHA-256 为 `cd77476b43347ed28d0211d5ad557e524e1ec648bd093d57c6a6d3de075a7508`，本机下载后重算一致。
- 源码包 285 条目、210 个 `.py` 文件；wheel 209 个 `.py` 文件，209/209 同路径源文件 SHA-256 完全一致；源码包仅多构建用 `setup.py`。这证明本轮两份精确发行产物的 Python 源文件匹配，不证明完整法律义务。
- 两个精确发行产物都没有独立 `LICENSE`/`NOTICE`/`COPYING` 文件；wheel 元数据和 PyPI 均声明 `License: Apache License 2.0`。210 个源码 `.py` 中 155 个在前 4 KiB 含 Apache 2.0 声明；并非全部文件都包含该声明。上游 [仓库主分支许可证](https://github.com/baidubce/bce-sdk-python/blob/master/LICENSE)为 Apache 2.0，但主分支不是经验证的 0.9.79 标签；`git ls-remote --tags` 精确版本过滤未返回匹配 tag。
- 因此本项仅达到 `EXACT_RELEASE_SOURCE_AND_DECLARATION_VERIFIED`，而不是 `LICENSE_CLEARANCE_PASS`。A08-P03 新候选并未包含本包的独立 Apache 2.0 文本；不能据上游当前主分支文件静默补包并宣布合规。

## 后续

`PLT-PKG-01-A08-P05` 扩展前端生产依赖及原生/系统组件来源清单、文本和义务证据；后续发行审查需决定对缺文本的 `bce-python-sdk` 如何附带精确适用许可，以及明确本产品源代码对外许可。Gate/Release 保持阻塞，`release_eligible=false`。
