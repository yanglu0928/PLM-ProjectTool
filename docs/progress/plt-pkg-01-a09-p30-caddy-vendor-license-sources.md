# PLT-PKG-01-A09-P30：Caddy vendor 模块许可文本来源映射

日期：2026-10-01；状态：`NON_RELEASE_CADDY_VENDOR_SOURCE_EVIDENCE / LEGAL_REVIEW_OPEN`。输入P22固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`、P29队列SHA-256 `3b72ab936c13ff04aff00b2bfae2002c17a00430734943725efc2c5712aca232`和包内可构建源码SHA-256 `33777097f666d60d78bfb74df06978c933f32aa5a0d4ce0b0c5d028489984187`。

编码前检查：Phase2/Gate3开放；本项仅核Caddy候选的技术来源，不改变实体、API、权限、Schema、打包内容或SCM。验收为固定ZIP/队列/SBOM/源码逐层Hash先验、`vendor/modules.txt`与SBOM名称/版本/PURL逐项一致、每个可匹配模块有直接位于其目录的非空许可样文本及Hash、生成清单全量读回。风险是路径/文本存在不证明许可适用范围、版权归属、NOTICE完整或对应源码充分性，审查标志不得改为PASS。

`tools/map_caddy_vendor_license_sources.py`对145个可映射Go模块核对版本/PURL 145/145，并从固定源码归档的各模块直属目录定位154份`LICENSE*`/`COPYING*`/`NOTICE*`常规文件；结果见[154条来源证据](plt-pkg-01-a09-p30-caddy-vendor-license-evidence.csv)，SHA-256 `1a771e5056c96c1d66b979765fefdbb6c5d55c6cf82fb210dc2daec0e78e7abb`。每行有SBOM `bom-ref`、模块/版本、归档内路径、文件Hash/字节数和`REVIEW_REQUIRED`。149项SBOM中另4项（Caddy产品、主程序伪模块、Go标准库、构建二进制路径）不属于`vendor/modules.txt`模块，需按其各自来源独立评审；不能把它们计为缺少许可证或已放行。定向单元2/2，固定候选真实映射exit0；CSV使用LF固定行尾以保持Hash可复现。

本任务不提取或重分发许可正文，不分类具体开源义务，也不产生法律结论。下一项P31分别核这4个非vendor项与根目录Caddy许可/Go标准库出处；同时需对145项逐条核正式声明与其他依赖家族。产品级LICENSE/NOTICE、Ghostscript等其余包发行门禁和正式信任源仍开放，`legal_clearance=false`、`release_eligible=false`。回滚只弃用映射器及CSV，不影响候选ZIP或运行数据。
