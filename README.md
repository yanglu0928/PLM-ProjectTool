# PLM 项目实施辅助工具

本仓库采用模块化单体与前后端分离的单仓库结构。Gate 2 已冻结 Architecture、Data Model、DB Schema V1 和 API Contract V1；正式实现按 WBS 逐项推进。

## 仓库结构

```text
apps/
├─ backend/                    # FastAPI、Worker 与 22 个客户运行模块
└─ frontend/                   # Vue 3 + TypeScript + Vite
tools/
└─ developer-workbench/        # 独立开发者信任区，不进入客户运行包
docs/                          # 架构、数据模型、契约、决策与进度
validation/                    # 可重复执行的设计/实现验证
poc/                           # Phase 0 PoC 历史与脚手架
```

模块目录、依赖规则、测试镜像与 Windows 路径规范见 `docs/architecture/module-directory-standard-v1.md`；机器可读目录见 `docs/architecture/module-directory-manifest-v1.json`。

本地客户资料、Secret、运行日志和生成物由 `.gitignore` 排除，不得提交到仓库。
