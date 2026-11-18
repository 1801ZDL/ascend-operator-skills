---
name: ascend-simulate
description: 为 Ascend/Triton 算子准备目标明确的仿真入口，采集流水、保存原始与bin产物，并将事件绑定到IR和真实指令。用于抓取仿真和解释队列/同步，不能把模拟窗口当作实机性能。
---

# 仿真流水采集与定位

先确定问题需要哪个 kernel、输入、逻辑任务和物理执行范围。已有完整原始捕获时，先评估离线解析能否回答问题，避免为了打开流水或重导出再次运行目标。

## 准备真正执行目标的入口

IR/LLVM 本身不是应用。沿原始 JIT 或已核对的 binary binding，保留正确 signature、constexpr、metadata、grid与输入；不要将其他算子的固定 ABI 当通用运行器。

按目的构造一次或有限次目标启动，避免意外运行整套 pytest、autotune、性能采样循环或 wrapper 的所有 kernel。需要 helper/warmup 时记录实际调用数和 kernel 过滤条件，不以“launch-count=1”推断整个应用只发出一次调用。

baseline 或未修改 IR 的当前编译校准优先复用，必要时补小输入校验。故障诊断可以限轮或去掉 payload，但标注干预，不能当完整功能/活性验收。

## 执行与留存

在已授权环境核当前 CLI 支持的 simulator 入口和目标，版本差异见 [采集与读取参考](references/capture-and-read.md)。参数从当前工具、算子和任务确定，不把示例 SoC、卡号、超时和空间上限当成默认事实。

日志字段、同步或指令语义缺少资料时，可用 [知识检索](../ascend-knowledge/SKILL.md) 找原始文档；对照当前 CLI/ISA、PC 和动态 ID。检索到的通用队列描述不能单独证明 WAIT/TRY 的可见性边界。

仿真常消耗大量 CPU、RAM、文件缓存、IO、临时磁盘和进程；按当前任务预算限制并发、时间与输出，监测自有执行树。若运行器明确禁止物理设备访问，核对其边界；simulator 模式本身不自动证明任何导入/初始化都无设备访问。

保存应用及目标身份、有效命令、ELF/metadata、输入与 grid、stdout/stderr、原始 pop/completion 日志、bin/时间线及解析结果的路径索引。临时输出峰值可能高于最终归档，不能仅按最终 bin 大小预估容量。

外层退出、目标完成、数值、解析与子进程状态分别记录；解析器 rc=0 仍可能没有有效 dump。超时或异常先核对原进程树，不立即重启同一捕获。仅完整且已绑定的原始数据可支持离线恢复，保留原失败记录。

## 阅读流水

先识别实际捕获、core/peer、时钟和单位，再以 PC、指令字、动态 ID 绑定当前 ELF及 IR。viewer 的归一化时间可能含 offset；raw cycle / ns、显示时间和模型时钟不能直接混用。明确 pop、issue、start、complete 字段的工具定义。

按每个角色查看 S、MTE、Cube/Vector、FIX及同步事件。图中的 FLOWCTRL 分组不等于指令执行 pipe；长 WAIT条也不自动等于全部可回收等待。

证明“重复领取/等待环”至少需同一接收角色、通知 ID、代次与执行顺序，并关联 SET供给、WAIT实际完成、TRY返回值或分支及新WAIT提交。不同奇偶 ID、f与f+16、两核同数值ID或不重叠的两条WAIT，单独都不是重复消费的证明。

结果区分局部/完整 grid、有效工作、启动/稳态/收尾及缺失日志。只承诺实际覆盖到的数值和同步资格；流水截图中的忙碌程度不代表实机吞吐。
