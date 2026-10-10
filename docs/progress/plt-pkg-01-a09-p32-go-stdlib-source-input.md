# PLT-PKG-01-A09-P32：Go 1.26.3标准库官方源码离线输入

日期：2026-10-01；状态：`NON_RELEASE_GO_STDLIB_OFFLINE_SOURCE_INPUT_VERIFIED / NOT_BUNDLED`。输入P22固定Caddy候选、P31明确的Go标准库源码缺口及[Go官方全部下载页](https://go.dev/dl/)的`go1.26.3.src.tar.gz`发布SHA-256。未改P22历史ZIP，也未给出法律适用结论。

编码前检查：Phase2/Gate3开放；本任务只固定可公开下载的Go源码离线输入和本地审计，不改业务/API/权限/Schema/服务或发行包。验收先核P22全ZIP，再核官方源包字节数/SHA、归档`go/VERSION`、`go/LICENSE`、足量`go/src`常规文件，最后与Caddy源码根`go.mod`及SBOM的Go版本一致性比对。风险是来源可获得不等于已随候选提供、也不等于对应源码/许可证义务已由有资质人员判定完成。

从官方`https://go.dev/dl/go1.26.3.src.tar.gz`下载到Git忽略的`artifacts/package-prep/windows11/go-stdlib-source/`，整包34,119,059字节，SHA-256 `1c646875d0aa8799133184ed57cf79ff24bdefe8c8820470602a9d3d6d9192b8`，与官方发布页一致。归档`go/VERSION`为`go1.26.3`，`go/LICENSE` SHA-256 `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad`，`go/src/`下11,468个常规文件；Caddy根`go.mod`及SBOM均指向Go 1.26.3。`tools/audit_go_stdlib_source_input.py`真实审计exit0，定向单元2/2。未解压到产品运行目录，不上传客户材料，未把源码加入Git或P22包。

下一项P33在`CR-PKG-005`既有Caddy离线边界范围内**新建**包含此固定Go源码及许可文本的非发行候选版本，完整逐件验真、保留P22不覆盖；之后仍须组件级NOTICE与正式法律复核。正式License信任源、安装/升级/三平台与Gate保持开放，`release_eligible=false`、`legal_clearance=false`。本任务回滚为弃用本地公开源码输入与审计工具，原包不变。
