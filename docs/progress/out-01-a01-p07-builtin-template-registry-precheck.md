# OUT-01-A01-P07：内置Output文件模板固定版本Registry实现

- 日期：2026-11-04
- 状态：编码前检查PASS_SCOPE_LIMITED；实现进行中
- WBS：OUT-01-A01-P07
- 依据：CR-OUT-006、OUT-01-A01-P06 PASS_SCOPE_LIMITED、冻结API-03/DM-04/DB Schema V1

## 编码前检查

- 数据Owner固定为Output模块；只读包内目录映射到现有OutputTemplateVersion DTO及OutputTemplateRegistryPort，不读取Prototype ORM或其他业务模块。
- 固定ref一对一指向模板版本；不支持current/latest发现。旧ref保持稳定，未知ref拒绝。
- 条目只包含UUID ref、受控output_type、source_kinds、immutable=true、published=true；不得包含可执行脚本、任意路径、客户数据或插件信任声明。
- 不增加ORM/Migration/API/依赖；P07不接Resolver/OutputRequest生产组合，不开启Output Create。
- 验收：单测固定ref映射、身份/字段白名单、重复/畸形/未知配置拒绝；A17 packaged runtime烟测检查打包Registry并输出专用marker；完整GitHub hosted workflow通过。
- 回滚：删除新增内置Registry adapter/entries/test；原有resolver在port缺失时仍失败关闭。

## 剩余编码前事项

按CR-OUT-006开始单一的Output内置只读固定版本Registry实现。