---
name: ascend-environment
description: 解释并定位 Triton/Ascend 算子工程背景，核对测试到JIT、实际Python/编译器、IR阶段、override、lowering与launcher ABI。核对 NPU-IR 与 llvm-project 配套版本并优先复用已有构建，必要时配置和编译。用于新任务入场或运行身份排查，具体服务器路径需重新确认。
---

# Ascend 工程背景与运行身份

目标是知道实际运行哪个算子、通过哪套工具、产生何种程序。仓库 HEAD、安装发行包、实际导入模块和外部编译器是四种身份；文件名相同不能证明相同实现。

## 定位实际入口

沿测试的 import → Python wrapper → JIT / autotune / constexpr → 实际 specialization → launcher 追踪。先用源码和安装元数据确认位置；必要的导入在当前任务环境中执行。`inspect`、包导入或设备信息查询可能间接访问驱动，不能把任意 Python 冒烟都当成无设备访问。

按需读 [背景与编译链](references/ascend-background.md)。需要保存工程路径时，在自己的项目按 [本地 profile](references/local-profile.md) 维护；公共技能不预设服务器路径、环境或历史待办。

外部 API/版本支持或跨仓入口不明时，可用 [知识检索](../ascend-knowledge/SKILL.md) 查 KG，再对照当前头文件、源码和实际工具。远程说明不能代替本机运行身份。

## 保存足够的运行身份

通常记录解释器/容器边界、实际源文件和提交/未提交差异、输入形状与 dtype/stride、特化常量、有效编译选项、CANN/目标、调用的工具/bitcode及 ELF。只收集与本轮相关的内容，不默认扫描所有环境、其他租户或凭据。

`scripts/capture_identity.py` 是无设备访问的辅助记录器，例如：

```bash
python scripts/capture_identity.py --distribution triton-ascend \
  --file kernel=/path/to/kernel.py --file compiler=/path/to/compiler.py
```

在需要核对的解释器中运行。它不导入 Triton/Torch，不证明实际模块已加载、库 ABI 兼容或设备可用；仍需将实际调用链绑定到证据。输出可能含个人路径，分享前只保留必要字段。

## IR 与二进制

先看当前后端的 `add_stages()` 和实际工具调用，不猜扩展名含义。普通路径可能包含 `ttir → ttadapter → mlirbc → bcmlir → npubin`，纯 SIMT 路径可不同；早期 IR、晚 HIVM、LLVM 和 ELF 使用不同入口。

需要 override 时：先 dump 目标特化到私有目录，保存原件；核当前安装支持的 knobs、source hash 目录和 stage 类型；使用新进程/私有 cache，并确认 override 日志、修改后 IR 与最终 binary。不能靠删除所有共享缓存“确保生效”。

晚 IR 手改先做未修改内容的同工具重编校准。导出的片段可能缺 VF/helper 定义；CLI 接受打印选项不代表完整模块已导出。能编译不等于布局、同步、资源或数值正确。

重放已有 binary 时核对本算子的 signature、constexpr 剔除、隐藏参数、metadata、grid和实际 launcher；不照搬另一算子的参数数目或 pack 字节数。

## 改编译器与环境

需要源码变更时使用独立分支/worktree及私有构建，遵守用户指定上游和基线；功能改动落在负责生成 IR 的 pass / lowering 层。DynamicCVPipeline 相关规划通常在其 `lib/` 与 `include/`，而不是用 Python compile 拦截替代正式实现。

后端驱动、CLI 兼容和诊断原型也可能是正确修改位置，按问题归属选择并标明范围。构建入口、LLVM 宏、CANN flags随版本变化；按当前树检查，不把 `setup.py`、`setup_ascend.py` 或旧 workaround 固定为通用规则。涉及安装时先确认本任务已授权的目标环境，保留可回退身份。

涉及 NPU-IR/LLVM 配套、已有构建复用或编译时，先读[版本核对与构建](references/npu-ir-llvm-build.md)。先定位本地可用的构建证据，只有缺少配套目标或需要验证本次源码时才配置或编译。
