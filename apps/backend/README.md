# Backend

FastAPI、Worker 与客户运行模块的后端工程根目录。WBS 1.01 只建立目录边界；`1.02` 才创建 FastAPI app factory，后续 WBS 再创建 SQLAlchemy、Alembic、错误、日志、Trace 与 Config 实现。

Python 代码使用 `src/plm_assistant` 布局；测试位于 `tests`，不得把本地数据、Secret 或生成物放入源码目录。
