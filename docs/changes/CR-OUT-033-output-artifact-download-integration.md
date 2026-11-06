# CR-OUT-033：OutputArtifact到Document内容流的受保护HTTP纵向验收

- 日期：2026-11-06
- 状态：P38实现候选已提交；Hosted PG18/HTTP验收待完成
- WBS：OUT-01-A01-P38
- 来源：P37已验证前端下载入口，但Hosted视图测试使用mock；P36验证PG Repository固定引用，没有证明两者经同一HTTP组合实际返回文档字节。
- 基线：冻结API Contract V1、OUT-02和Document下载合同；CR-OUT-032；不改API/Schema/Migration/default composition/生产trust。

## 证据缺口

生产源码在显式 include_secret_read Platform模式内同时装配Output Artifact引用与受保护Document download router，Windows --platform 选择此模式；login-only默认不装配。正式Platform trust目前未具备，不能启动真实受保护产品进程。P37 UI测试是合成Client/导航mock，不能证明真实Document内容字节经过项目授权和完整性流。

## 选择的方案

在GitHub hosted Windows Server 2025 D盘临时PG18环境，新增测试专用合成Session/License和Runner临时文件夹，通过现有Artifact引用与Document下载route factories调用真实HTTP端点，贯穿固定Artifact→DocumentVersion→FileObject→verified content bytes。验证授权/项目隔离、不可用Artifact失败关闭、Hash/大小一致和无locator/body泄露。对正式Platform app assembly能覆盖的纯连接边界使用工厂测试，不提供production trust fixture。

## 影响与回滚

首选只新增验证器、测试和其父包接线，不变更产品API、数据库合同、默认或Windows Platform信任装配。测试环境仅合成数据，外发/外部调用为零。若验收揭示产品接线问题，先补充本CR列明影响、兼容/迁移/回滚及测试，再按持续授权修复。回滚只删除新验证代码/runner接线，不触碰历史业务数据或文件。

## 验收

Hash/长度/字节完全一致；项目越权、未知/不可用Artifact、内容完整性错误均失败关闭；没有存储定位符进入响应；后端全量/wheel、前端全量/typecheck/build、父包PG18及A17/A34/A35/A50检查通过。整体workflow/P25独立情况如实报告。Win11实机、正式trust、Pilot、Gate或Release不因该合成验收而通过。


## P38 Hosted实现候选

已在P33临时PG18父包验证器中增加P38 helper，使用真实OutputArtifact读取Repository、真实DocumentReadService/Repository、PrepareDownloadService、LocalFileStorage及两个HTTP router factory；Session、Project授权摘要和License guard使用仅限合成测试的夹具。实际HTTP贯穿授权Artifact引用到Document流字节，并检查跨项目/未知引用隐藏、Hash/大小/MIME、存储路径不披露及文件被篡改后不返回正文。只写Runner临时目录；未修改生产API、Schema/Migration、默认挂载、正式信任或业务数据。待Hosted run验收后按结果更新。
