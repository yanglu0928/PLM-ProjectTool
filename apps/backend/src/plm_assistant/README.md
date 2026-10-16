# plm_assistant package root

此目录是后端 Python 包根。固定子边界为：

- `entrypoints`：API/Worker 进程入口与 Composition Root；
- `modules`：22 个客户运行模块；
- `shared`：最小技术内核和公共 Contract。

WBS 1.01 不创建可执行 Python package；`__init__.py`、构建元数据和 App Factory 由后续 WBS 添加。
