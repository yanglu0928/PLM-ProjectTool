# CR-PKG-010：当前后端依赖与非发行包内 Python 运行时不一致

日期：2026-10-24；来源：`PKG-PILOT-01-A02` 包内迁移预检；状态：`NON_RELEASE_IMPLEMENTED_AND_VERIFIED / FORMAL_LEGAL_AND_INSTALL_OPEN`。承接 CR-PKG-008/009，不覆盖父候选或 A01 ZIP。

## 冲突与证据

A01 清洁解包完整，但用包内 Python/Alembic 升级隔离 PostgreSQL 时在迁移环境导入 RAG ORM 失败：`ModuleNotFoundError: No module named 'pgvector'`。当前后端 wheel 声明 `pgvector==0.5.0`；随包 Python 运行时经 wheel 元数据核对，其余 18 项普通生产依赖均满足，唯缺 Python `pgvector`（与服务器 pgvector 扩展 0.8.6 不同）。因此 A01 完整性通过不代表随包程序可运行。失败用一次性 PG，已停止并清理。

已保存的 Windows PoC 轮子 `artifacts/poc-01/windows/wheelhouse/pgvector-0.5.0-py3-none-any.whl` SHA-256 为 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`，与该 PoC `sha256sums.txt` 一致；包含 MIT 许可文本。尚不构成正式法律放行。

## 方案与选择

- A：运行时从开发机虚拟环境拷贝 `pgvector`。来源/版本/许可无法由固定原始归档独立验证；不选。
- B：从已固定 SHA 的 PoC wheel 向**新**非发行派生候选追加 `pgvector` 包及 dist-info/许可，验证精确版本、轮子路径和逐件哈希，更新第三方清单；原父包与 A01 ZIP 不变。选择 B。
- C：等完整运行时全量重建。正式发行必须做依赖/法律复核，但不会帮助当前快速定位其余包内运行问题；本轮不以此阻塞受控 B。

## 差异、迁移/回滚与风险

只扩充非发行打包器的固定补充 wheel 输入与新候选载荷/清单；不修改 `pyproject.toml`、产品模块、Schema、API、License、客户数据或正式安装。新候选必须唯一 ID/哈希且保持 `release_eligible=false`、`legal_clearance=false`。wheel 的名称/版本/文件路径/哈希/许可和与原载荷的大小写冲突均失败关闭；第三方清单追加来源和待法律审阅状态。回滚为弃用新候选，A01 与 P45 历史 ZIP 均保留。不得用此候选声称正式安装成功。

## 验证计划

先做合成正/负例与路径/哈希失败关闭；再用干净已提交源码、原父包和固定 PoC wheel 构建**新**候选，独立清洁解包、包内依赖清点与 Python 导入。仅在固定候选上运行隔离 PG18/pgvector 的 `0184→0185` 有数据/空库升级与受控降级重升；失败时记录真实错误与清理状态，正式 Pilot/Gate 不变。

## 技术验证结果

修复前 A01 包的迁移退出 1（缺 Python `pgvector`），一次性 PG 已停止清理。修复后从干净提交 `98d28da3498deefafbfa4396fda6fea16743d136` 派生新包 SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`；包含固定 PoC wheel 全部 46 件，清单新增 MIT 许可位置与 `REVIEW_REQUIRED`。打包/暂存/迁移边界定向 8/8；22,191 件独立清洁解包、包内 Python `pgvector==0.5.0` 导入、PG18/服务器 pgvector 0.8.6 的 `0184→0185→0184→0185`、空库直升与旧配置行保留均通过。见 [A02 证据](../progress/pkg-pilot-01-a02-packaged-head-migration.md)。这不代表法律放行、正式安装/升级或 Pilot 可用。
