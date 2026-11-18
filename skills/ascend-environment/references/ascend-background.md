# 工程与执行背景

按当前问题读取对应小节；硬件与接口细节以本任务的目标、源码和工具为准。

## 编译、运行和源码位置

```text
test / Python wrapper
  → JIT + autotune + constexpr specialization
  → TTIR → 结构化/适配IR → HIVM/NPU-IR → LLVM → ISA/ELF
  → metadata + launcher参数打包 → 实际执行 → 输出/采集/解析
```

这不是固定 stage 名单。当前后端 `add_stages()` 决定缓存扩展名和处理顺序，纯SIMT与融合路径可能不同。前端生成、NPU规划、CCE代码生成分别定位；“LLVM已生成”不等于链接、启动或数值已过。

Triton-Ascend 常见源码入口：

- `third_party/ascend/backend/compiler.py`：stage串接、有效选项和外部工具调用。
- `third_party/ascend/lib/DynamicCVPipeline/` 与 `include/DynamicCVPipeline/`：CV分块、依赖、资源及控制流规划。
- `third_party/ascend/lib/TritonToLinalg/` 等：操作转换与模式。
- AscendNPU-IR / LLVM子仓：HIVM、HFusion、类型、intrinsic与lowering。
- 安装包 `triton/backends/ascend/`：实际Python后端、bitcode和随包工具，可能与源码树不同。

实际变换位置按当前版本确认，不将以上目录当成所有分支的完整结构。新编译器类型需贯通前端注册、IR、MLIR→LLVM、工具链类型/指令及运行时接口；底层已有能力时优先对接，不重复实现硬件适配。

## 计算与管线

A5混合任务常见1个AIC/Cube配2个AIV/Vector；别的SoC、纯SIMT或运行模式不直接套用此拓扑。Cube擅长MMAD，Vector处理向量算术及相关工作；MTE/FIX等负责搬运。S标量、各计算/搬运pipe可异步推进：Python或scalar提交顺序不等于各pipe完成顺序。

buffer通常涉及GM、Cube侧L1、Vector侧UB、L0等空间；SSBUF用于标量控制状态。地址空间整数和bank容量按目标核实；不要凭不同数值地址就断言跨core物理不重叠。

`to_tensor`、view、layout转换和matmul可能把一个逻辑输入物化成多个物理池。ND/nZ、padding、subblock binding和内/外层multibuffer影响真正写入与读出。数逻辑alloc或比较声明字节不能代替核对最终地址、dtype、stride、范围及全部读者。

## 同步语义需要绑定 lowering

```mlir
hivm.hir.sync_block_set [<CUBE>, <PIPE_FIX>, <PIPE_V>] flag = 3
hivm.hir.sync_block_wait[<VECTOR>, <PIPE_FIX>, <PIPE_V>] flag = 3
```

以上是结构示意，语法按当前工具确认。已核对过的Ascend950路径中，SET取第二字段`tpipe`作为完成源，WAIT取第三字段`pipe`作为接收侧阻塞位置。三元组不是三段独立counter键；通知身份还涉及接收core、ID、通信模式及peer。Cube接收两V时曾有f/f+16映射。**这些是特定目标的lowering事实，不是所有版本或模式的通用ISA保证。** 核对当前转换代码、LLVM intrinsic、机器指令与必要ISA契约后再推广。

同一个数值ID在Cube与Vector接收侧可以是不同通知状态；改变WAIT执行pipe也可能不改变目标counter。相同ID是否允许复用仍要看接收角色、代次、初始额度、通知供需及全部消费者，不能只按文本出现次数配对。

TRY_WAIT在本地研究中用作非阻塞观察；成功观察不等于领取通知，也不必然代表某个软件任务的新一代额度。WAIT尚未消费时，之后TRY可能再次观察到同一正值。动态ID和立即数I形式需按最终机器指令分辨；HIR名称不能决定选用哪种形式。

用TRY探索调度时可将“软件提交/资源进度保证合法”“TRY帮助排序”“原pipe WAIT保证数据使用时机”分开验证。将WAIT放到S可能阻止scalar继续超前，但不代表整个计算都改到S串行，也不能据一次跑通推导通用时序或性能保证。架构可见性、retirement与最小间隔未知时保留未证明项。

## 资源生命周期与 ABI

对每个物理buffer记录：owner、逻辑任务/tile、slot/代次、首次写、生产完成、每个最后读、归还/首次复用及退出排空。下游释放输出空间的反向依赖与上游ready同样重要。提交计数和完成计数含义不同；通知总量平衡不单独证明顺序与活性。

binary重放不仅要有`.o/.npubin`，还要匹配kernel符号、当前signature、constexpr剔除、隐藏参数、user参数顺序/宽度、grid、metadata和launcher。源函数39参数可能只有18个运行参数；另一个算子的pack大小不能作为模板。先用当前共享runtime或原始JIT校准，再绑定自定义重放。
