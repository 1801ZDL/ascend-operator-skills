# NPU-IR 与 LLVM 配套、复用和编译

## 先查依赖和本地成果

1. 从实际入口确认所用 NPU-IR 仓库和目标提交或工作树，连同本地补丁一起记录。对于使用 LLVM 子模块的版本，用 `git ls-tree <目标提交> -- third-party/llvm-project` 读出预期 gitlink。对工作树再核 `git ls-files --stage -- third-party/llvm-project`、实际子模块 HEAD 和修改；空目录、独立 LLVM 工作树和本地链接都需要分别识别。旧版可能使用其他依赖机制，以当前仓库构建说明为准。相同 LLVM 主版本号不代表 Ascend 补丁、LLVM/MLIR 接口或 intrinsic 一致。
2. 优先从任务 profile、历史构建报告、当前后端的实际工具路径和明确给出的个人目录找已有构建或安装前缀。先查 `CMakeCache.txt`、已有构建收据、`bin`、LLVMConfig/MLIRConfig 与生成 include；只查候选路径。记录实际 LLVM 源提交、补丁、构建配置和时间。缓存绑定的源码目录可能被 rebase 或重配，当前 HEAD 一致无法证明二进制由这个提交生成。安装前缀没有缓存时，查安装时的构建收据、产物哈希或可信发布记录。
3. 核对 LLVM 和 MLIR 是否来自同一套生成和构建，检查实际编译器、宿主 ABI、构建类型、RTTI、链接方式及目标、Ascend 宏、TableGen 参数。NPU-IR 还需核对 CANN/CCE 版本、芯片目标、宿主工具、模板 bitcode 和实际加载位置。用当前任务最小的解析、翻译、TableGen 或编译样例验证所需能力。一个可用的 `mlir-tblgen` 只足以复用相应生成阶段，`LLVMConfig.cmake` 文件存在也不能证明所需库都已构建。

用本技能的 `scripts/check_compiler_pair.py` 对已知候选做第一轮只读筛选。按优先顺序传入已有目录，可混合构建目录和安装前缀：

```bash
python3 scripts/check_compiler_pair.py --npu-ir "$NPU_SOURCE" \
  --build "$EXISTING_COMBINED_BUILD" --build "$EXISTING_LLVM_PREFIX"
```

脚本读取 NPU-IR 的 HEAD/index gitlink、候选 CMake 缓存、LLVM 源树状态及工具和包配置文件。 `matching-checkout` 表示缓存所指源码当前匹配，`binary_provenance` 仍需另核。内网 CI 使用的镜像或浅克隆需要在执行端确认其持有目标提交，可用 `git cat-file -e "<sha>^{commit}"` 检查。仅公开 fork 存在提交无法满足这项依赖。

## 按所需目标选择构建

| 当前证据 | 处理方式 |
| --- | --- |
| 现有对应版本、配置和目标已经可用 | 直接复用并用小样例核实实际使用的工具及依赖 |
| 可写的私有联合构建绑定目标工作树和配套 LLVM，但 NPU 源码或目标有更新 | 在该目录做增量构建，先确认 Ninja 计划及实际作用范围 |
| LLVM 成果可用，NPU-IR 构建尚无 | 当前版本支持独立构建时，按官方入口指向配套的 `LLVM_DIR`、`MLIR_DIR`。若只支持 LLVM external-project 联合构建，沿用该入口，可按版本支持复用配套的宿主 TableGen，但由新构建图决定其余目标 |
| 构建目录绑定不同源码、权限不合适或配置不兼容 | 创建私有工作树和构建目录，获取目标 gitlink 对应的依赖并按仓库入口配置 |

先读当前 NPU-IR 仓库的构建文档和脚本（例如存在时的 `build-tools/build.sh`），核对项目名、CMake 选项、CANN 路径、LLVM 目标和模板能力。联合构建通常从 LLVM 的 `llvm/` 配置 MLIR 与 NPU-IR external project；仅在源码明确支持时使用独立 `LLVM_DIR`/`MLIR_DIR` 路径。避免通过手写宏覆盖掩盖 CMake、C++ 和 TableGen 的配置不一致。生成头文件和库应由同一配置产生。将源码和安装版本分开，避免在共享 build 目录替换源码路径、拼接其他构建的对象或覆盖公共安装。

需要新建联合构建时，以下配置骨架适用于确认外部项目名为 `bishengir` 的版本。补上该版本真实入口使用的 CANN、目标、功能开关和测试选项，以当前构建脚本给出的参数为准。

```bash
cmake -S "$LLVM_SOURCE/llvm" -B "$BUILD" -G Ninja \
  -DLLVM_ENABLE_PROJECTS=mlir \
  -DLLVM_EXTERNAL_PROJECTS=bishengir \
  -DLLVM_EXTERNAL_BISHENGIR_SOURCE_DIR="$NPU_SOURCE"
```

若只需要构建 LLVM/MLIR 工具，使用相同的 LLVM 源码和配套配置，省略两项 external-project 参数，再以实际目标名构建所需工具。使用已构建的 TableGen 时，先核对该分支支持的 `LLVM_TABLEGEN`、`MLIR_TABLEGEN` 参数及生成器输入契约。记录选用的可执行文件路径和对应版本。

对已有且绑定正确的 Ninja 构建树，先取实际目标并用有限并发编译。例如：

```bash
ninja -C "$BUILD" -t targets all
ninja -C "$BUILD" -n bishengir-opt bishengir-compile
ninja -C "$BUILD" -j "$JOBS" bishengir-opt bishengir-compile
```

目标名以当前构建为准。只缺生成代码时构建相应 TableGen 目标，涉及设备代码生成时检查所需宿主工具、CCE 和模板 bitcode。按任务预算控制编译、链接、测试并发和磁盘使用。验证以受影响工具的实际路径和专项用例为准；记录配置或构建命令、旧产物的复用范围、新工具路径、所跑检查和失败。只有任务需要时才跑全量回归或真机验证。
