# OUT-01-A01-P03 结果：固定来源与模板策略可信解析边界

- 日期：2026-11-02
- 状态：PASS_SCOPE_LIMITED
- 分支：feature/p51-a33-launcher-checksum-recovery
- CR：CR-OUT-003（仅本边界切片按证据关闭）
- 源码提交：e0b69bdcdc06765e5192d57fe84f924d30606958
- 云端验收：[GitHub Actions run 41417503109](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109)，13/13 jobs success

## 变更

- 新增 TrustedOutputContextResolver，通过明确的Source、Template、Policy、Plugin Operation Port读取调用方提供的精确固定版本，不访问跨模块私有ORM，也不解析current/latest。
- 要求所有引用准确匹配；来源必须同Project、由Source Owner确认授权、审核态符合策略；Template必须已发布且不可变；操作必须注册、启用、可信并支持OutputType。
- 仅按策略字段白名单复制源内容，限制嵌套、字符串长度、条目数和Context总字节数；忽略未白名单字段；生成规范化稳定fingerprint。
- 无注册定义、未授权/跨项目/未批准来源、操作不可信、类型不兼容或输入超限时统一失败关闭。
- 没有Schema migration、API Contract或HTTP变化；没有AI、网络、Plugin执行、Artifact或文件生成。

## 验收

- 新增9项单元测试，覆盖合法固定快照、最小字段、fingerprint稳定，模板/策略/操作缺失，跨项目/未授权/未批准来源，模板状态/OutputType/Operation不匹配，超大Context及非JSON/深嵌套输入。
- 首轮run 41416698193因一个深嵌套负向测试夹具实际深度不足而失败。已先在CR-OUT-003记录，再修正夹具；失败不是测试证明的生产越权问题。
- 修正提交的run 41417503109全13 jobs成功：后端全量测试/wheel、前端测试/typecheck/build、PG18/pgvector重建、parent candidate、A50 Edge来源导航、A17 PlanVersion Edge/HTTPS/PG、临时PG生命周期和A34离线替换/人工恢复均通过。
- 内部父包候选Artifact：13129330605。该候选不是发行包；没有安装或启动产品服务。

## 证据范围与限制

本WBS验证的是Output application resolver的安全边界与Port合同，registry/source数据由合成Port提供。仓库当前仍缺生产Template/Policy/Plugin Operation registry及Requirement/Solution/Plan固定版本读取适配器；P03 resolver没有连接真实PG的注册数据。未实现生产Create路径，缺注册依赖时Output仍失败关闭。因此结果是PASS_SCOPE_LIMITED，不能推定Output纵向链、Pilot或Release已通过。

验证仅在GitHub hosted Windows Server 2025 runner的D盘临时空间进行。没有用户本机/C盘执行、客户数据/外部服务、正式License信任、Windows 11设备测试、产品安装/服务启动或Gate结论。Gate 3、Pilot、正式Release维持NOT_READY。

## 下一项

PLG-01-A01：开发者签名插件包不可变元数据 Schema/ORM。先完成编码前检查及依赖顺序记录；本项只做冻结 PLG-01 存储基础，不实现签名验证、安装、运行时或输出适配。
