# 数据与接口导航

[返回总览](../README.md)。先按任务定位，不必读取整个 schema 或所有样例。

## 三种边界

| 要交接什么 | 结构依据 | 语义与例子 |
| --- | --- | --- |
| 项目设置、素材、剪辑计划、时间线、修改结果、转录 | [JSON Schema](../contracts/contracts.schema.json) | [时间线语义](reference/timeline.md)、[13 份数据样例](../contracts/examples/) |
| 浏览器↔后端请求/响应 | [OpenAPI](../contracts/collaboration/api.openapi.json) | [HTTP 说明](reference/api.md#s10-2)、[31 份 HTTP 样例](../contracts/collaboration/api.examples.json) |
| A 调度↔B 布局/渲染 | [Python 接口类型](../contracts/collaboration/runtime_contracts.py) | [函数交接](reference/api.md#s10-6)、[替身用法](../contracts/collaboration/README.md) |

现有数据 `schema_version` 和 HTTP `api_version` 均为 `1.0.0`，各自独立维护。OpenAPI 内复制的 `Data_*` 必须与根 JSON Schema 保持一致，检查脚本会验证。产品阶段限制见 [产品范围](product.md#s2)，不能只凭 schema 合法就开放功能。

## 按任务读取

| 当前任务 | 必要参考 |
| --- | --- |
| 素材登记与本地路径 | [资产说明](reference/timeline.md#s6-3)、[架构与存储](architecture.md#s11) |
| AI 输出计划 | [计划字段](reference/timeline.md#s6-5)、[AI 选片评估](ai-selection.md#s20-4) |
| 编译或渲染时间线 | [秒/帧约定](reference/timeline.md#s6-2)、[时间线](reference/timeline.md#s6-6)、[校验规则](reference/timeline.md#s6-10) |
| 标题、暖度、删除、撤销 | [修改操作](reference/timeline.md#s6-8)、[编辑与版本](reference/editing.md#s9) |
| 上传、轮询、错误、播放 | [HTTP 与状态](reference/api.md#s10-2) |
| 字体、标题布局、预设 | [风格配置](reference/editing.md#s7)、[模块交接](reference/api.md#s10-6) |
| 前后端尚未接好 | [独立开发替身](reference/api.md#s10-5)、[可运行工具](../contracts/collaboration/README.md) |

## 修改契约的流程

A 维护公共契约，B 提出需求；先展示新旧字段/签名差异，协调两边调用者，再在同一完整变更中更新定义、样例、替身和实现。改变含义时升级相应版本。冲突不能靠调用方猜测兼容，先记录具体不一致并明确修正。

样例和开发替身都是模拟数据；真实 API、AI、渲染、字体、存储恢复与 Replit 验收仍待实现。执行检查的命令与范围见 [工具说明](../contracts/collaboration/README.md)。
