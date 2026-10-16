# PLT-PKG-01-A09-P43-A05：Ghostscript 源码候选隔离布局兼容

日期：2026-10-01；状态：`NON_RELEASE_GHOSTSCRIPT_SOURCE_ISOLATED_LAYOUT_PASS / FORMAL_RELEASE_BLOCKED`。输入 P43-A03 固定新 ZIP SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P43-A04 清洁暂存与原 P33/P22 谱系。未改 CR-PKG-006 范围。

编码前检查：Phase 2/Gate 3 开放；只在全新 ASCII Temp 目录复制/核查非发行布局，正式 `C:\PLMTool` 必须不存在，不注册 SCM、不启动数据库、不供给正式 TLS/License 材料。实体/API/权限/Migration 无变动。验收为来源/暂存先验、21,117 个目标文件全量 Hash/精确映射、Ghostscript/Go 源码及 LICENSE、OCR 模型指纹、包内 Python/PG/Caddy/Ghostscript 版本及合成 Caddyfile validate。风险是新加源码路径在 Windows 目标冲突、长路径、运行依赖缺失或把模板验证扩大称生产 HTTPS。

首次尝试用系统 Python 3.14 启动验证脚本，因该解释器无项目 `cryptography` 依赖而在复制前失败；随后用随包 Python 3.13 重跑完整流程。新布局在本机 `C:\Users\17231\AppData\Local\Temp\plm-install-rehearsal-gs20261001a`，映射 SHA-256 `6c39824984cfa977912eab8208a607ee6acd72aa9bfb5f34858bde330b25e697`；21,117 目标文件逐项复制/Hash/文件集回读 PASS。新增 Ghostscript 源码映至 `app/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz`，源包 LICENSE 映至 `app/third-party-licenses/ghostscript/source-LICENSE`，原 Go 源/许可映射不变。嵌入式 Python 报 `0.1.0.dev0`，PG 报 `PostgreSQL 18.6`，Caddy 报 `v2.11.4`，Ghostscript 报 `10.08.0`，OCR 模型指纹及合成证书模板 `caddy validate` 均通过。最后重验新候选与暂存未变。真实脚本退出 0，定向单元 1/1。

兼容性：只证明 Windows 11 隔离文件布局及启动探针；不证明生产 HTTPS 登录、OCR 完整质量、Server 2025/Debian 13、正式账户/证书/License、法律合规或 Gate。无业务/API/Schema/SCM变化。升级：无迁移。回滚：不用该新非发行布局即可，P33 与新候选历史保持不变。`release_eligible=false`。下一步优先收敛产品级 NOTICE/第三方义务清单与正式信任源，同时把新包运行链继续限定为非发行验证。
