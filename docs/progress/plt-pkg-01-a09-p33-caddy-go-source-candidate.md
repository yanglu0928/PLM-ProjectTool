# PLT-PKG-01-A09-P33：Caddy＋Go源码新非发行候选

日期：2026-10-01；状态：`NON_RELEASE_CADDY_GO_SOURCE_INDEPENDENT_VERIFY_PASS / RELEASE_OPEN`。依据`CR-PKG-005`与P32固定官方Go 1.26.3源码输入，仅建立P22的后继非发行候选；不覆盖旧ZIP、不安装、不注册SCM、不加入任何证书/密钥。

编码前检查：Phase2/Gate3开放；输入P22固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`、Go官方源码SHA-256 `1c646875d0aa8799133184ed57cf79ff24bdefe8c8820470602a9d3d6d9192b8`及Go LICENSE SHA-256 `911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad`。本任务仅重组打包证据，不改产品实体/API/权限/Schema/服务；验收为新旧逐件Hash谱系、增量两项、三份清单与全部非发行标志、整包独立重验。风险：加入源码不等于第三方NOTICE或法律义务完成。

`tools/build_windows_unified_caddy_go_source_candidate.py`先审P22与官方Go输入，再新建Git忽略目录`artifacts/package-prep/windows11/unified-caddy-go-candidate-0f1a8bea5cd8/`。新ZIP `NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-source.zip`为675,167,309字节、SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`，载荷21,112项（P22原21,110项逐件不变，新增`payload/third-party-sources/go/go1.26.3.src.tar.gz`及`payload/third-party-licenses/go/LICENSE`）。新manifest明示P22来源、Go源码Hash、`release_eligible=false`、`legal_clearance=false`、未安装/未注册服务；inventory保留原Caddy/P15审查状态并为Go另加`REVIEW_REQUIRED`。构建脚本全量回读，独立`tools/verify_windows_unified_caddy_go_source_candidate.py`另做固定整包/原包逐项Hash、精确增量及清单审计，均exit0；定向单元3/3 PASS。

下一项P34仅将此固定新ZIP解到全新ASCII Temp目录并验证全量落盘读回、Go归档与随包LICENSE，旧P23/P25布局不复用来声称新包已验；之后还需目标安装/升级、正式信任源、完整NOTICE/法律审查、Server2025、Debian13（实机暂缓）及Gate。此项未清洁解包、未运行新包或打开生产入口，`release_eligible=false`。回滚弃用新候选，P22原Hash和文件不变，无数据迁移。
