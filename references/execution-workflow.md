# 单次快照、可回收预览与批量执行工具

本文是普通换肤的唯一执行定义。默认契约是 `one-full-source-baseline → offline-plan-and-projection → disposable-full-preview → one-committed-batch-write → one-final-review`；颜色标准仍以《颜色决策规则》为准，保护边界以《Figma 执行规范》为准。跨模式/复杂材质必须做可回收整页预演，原稿与正式交付区不留试稿。现场代表试色、逐区写入和写后自动修正仅在用户明确要求交互式试色时启用，不能作为普通任务默认路径。

## 1. 一次完整读取与本地场景投影

用户选色后，Phase 1W 在一次 `use_figma` 只读调用中完成完整原稿快照、原稿整页截图及预先可确定的 1:1 原生局部截图。快照包含隐藏实例子层、全部 Paint/Effect/文字区间、绑定、节点结构和读取异常。成功保存后不得再次遍历或传输整棵原稿树；所有角色、材质、状态、宿主和保护分类都从这份快照派生。

`mutationPlan.reviewScenes` 覆盖完整页面而不是只挑代表写入：每个场景记录 `sceneId`、全部等价实例、非等价材质/状态/宿主、依赖节点、实际写入路径、原稿→副本映射规则、保护清单、目标层级和最终截图范围。任务卡场景须同时包含内容器表面、标题/正文、Icon 图形与底托、进度/状态、小按钮和邻近标签；不能把这些关系拆散后分别宣称通过。

本地生成 `expectedClone`：先投影 clone、KV 适配、必要解绑及完整颜色原子 diff，再在该投影上运行与终审相同的确定性检查。投影必须在写入前通过：

- `icon-glyph-coverage`：每个功能 Icon 根下全部可见颜色通道逐路径覆盖；图形通道默认 `change`，只有带可复验 `themeNeutral` 证据才能 `preserve`。
- `material-relations`：除最大色差外，重复/交替色标的源角色组不得在目标中被拆散或合并；金属层的暗/亮/反射节奏保留。
- `surface-discernibility`：纯色/正常混合的页面、卡片和内部容器按真实 Paint、节点和祖先 Alpha 合成；跨模式的表面边界必须冻结 `minimumDeltaE >= 3`，按原稿职责确认为 `container` 的内部容器使用 `minimumDeltaE >= 4`。复杂渐变/IMAGE 宿主用原稿截图与离线合成预览，不得比较裸 Hex。
- `state-discernibility`：同一状态家族的每个成员使用相同 `stateGroupId`。源稿在同一宿主上的每一组非等强关系都自动展开为 `emphasisOrders`；不得只登记一个“代表节点”。进度节点、奖励标签、选中/未选中、完成/未完成若在原稿中有亮暗差异，目标不能全部落为同一色或同一合成强度。

只有静态投影检查通过，才生成冻结写入函数并用于可回收整页预演。预演是同一完整计划的 Figma 原生渲染，不能用代表卡或局部写入替代；其快照和截图随后用于完整机器/视觉预检。任何临时副本清理失败都必须停止，不能转入正式交付。

## 2. 可回收预演、一次正式批量写入与一次最终审查

跨模式或复杂材质任务用 `scripts/generate_figma_staged_preview_js.py start <sourceId> <sourceFingerprint> <planHash> --apply-js <frozenApplyJs>` 启动预演。`applyThemeWriteToClone(figma, clone)` 必须与正式交付使用同一冻结计划和 setter 路径，返回逐操作无失败的 `status=pass`；失败时立即删除临时副本。成功时返回带唯一标记的 `cloneId`，编排层随后用 Figma 截图接口取该临时画框的原生 1:1 整页 PNG，并在 `finally` 中调用生成器的 `finish` 程序按精确 ID 清理，复核页面子节点顺序和原稿指纹。截图下载到本次运行目录后核对尺寸/哈希并做真实视觉验收；预演函数返回的紧凑指纹与写入回执对照 `expectedClone`，不假称拿到了完整临时快照。计划改动后重做静态检查与预演；不得沿用旧 PASS。预演的调用次数和清理结果如实记录，不冒充零写入。正式交付前把预演与写入计划绑定同一哈希。

唯一**正式**写入程序在同一 `use_figma` 调用内完成以下顺序：核对原稿根指纹及预演计划哈希 → clone 一次 → 放置 KV/冻结 KV 子树 → 必要实例解绑与颜色绑定解除 → 应用全部原子颜色/Alpha 操作 → 逐操作核对 setter 后值 → 返回副本 ID、节点映射、完成/失败路径和最终紧凑指纹。程序可在内部分块以控制代码和执行时间，但不能拆成多次正式 Figma 写入调用，也不能在块间重新读取整树或截图试色。
完整复合 KV 先追加到 clone 的末尾并立即锁定，这样原稿子节点的索引路径在全部 UI setter 执行期间不变；写色和读回结束后才把锁定 KV 移到 Hero 的目标层级。追加时不得写其内部，移动后须核对最终层级、位置、尺寸与锁定状态。失败仍按精确临时/正式副本清理契约处理。

若调用返回部分失败或冲突，立即把本次任务标为未完成；不得把冲突值改成新的 before、不得盲目重放整批、先停止写入并核对回执及当前真实状态；按《执行契约》的有界修复另行冻结修复事务。没有任何设计变更发生的前置失败可修正程序后重新执行同一阶段，未知/部分成功不能盲重放。

Phase 7 只进行一次集中终审阶段：一条 `use_figma` 调用取得原稿不变指纹与完整副本快照，另一条截图接口取得同一副本的 1:1 原生整页图；`reviewScenes` 细节图从整页图本地裁取。随后在本地派生灰度、模糊、缩略图和并排裁图，运行全部机器/视觉门禁。任何失败保留精确节点、通道、关系与截图证据，并按《执行契约》的有界修复推进；不得无新证据循环“读—修—再读”。

`audit_delivered_theme.py` 是完整 KV 子树直接导入时的写入/截图一致性辅助审计，不替代 finalize 或业务视觉审查。其 writePlan 必须有冻结的 `kvPlacement:{childIndex,x,y}`；识别尺寸来自 KV 输入，截图尺寸来自当前页面，不使用历史页面常量。需要对子树缩放/增层/栅格兜底的 KV 适配，以 kvFitPlan、完整投影及 finalize 验收，不把未适用的辅助脚本 PASS 当作全流程证明。

`generate_blue_revision_apply_js.py` 和 `generate_compact_revision_js.py` 是历史任务专用模板，含固定节点/几何，默认 CLI 已退役；不得作为新任务通用写入能力。通用任务使用冻结计划编译器与 staged-preview/commit/final-review 生成器。维护时保留历史实现仅供阅读，不把旧任务脚本放进正式工作流。

## 3. 中断恢复与证据持久化

四个顶层产物不变。快照和截图可以是旁文件，用路径和哈希引用；不把大树反复嵌入日志。每次完成实际动作就原子保存本地产物，不在末尾补写历史时间。这里的“持久化”只指**当前未完成任务的中断恢复**，不是跨任务积累历史配色或长期归档。

Phase 0 先运行：

```sh
python3 scripts/run_workspace.py init --file-key ACTUAL_FILE_KEY --target-id ACTUAL_TARGET_ID
```

把返回的绝对路径登记为 `mutationPlan.runWorkspace`。当前运行产生的下载 KV、原稿/副本快照、配色 JSON/PNG、截图、派生视图、差异、批次、门禁和最终审计旁文件全部写入此目录；Skill 根目录只保留规则与可复用脚本。不得自动枚举或读取稳定 `artifacts/`、`work-*.png`、旧 `run-*` 目录来猜测当前 KV、目标或方案。当前输入必须来自本轮用户消息与当前 Figma 文件的实时读取。

只有用户明确要求恢复同一个未完成任务时，才读取既有 `runWorkspace`；恢复前同时核对标记中的 `fileKey/targetNodeId`、新 KV 身份或文件哈希、原稿快照指纹和 Figma 中唯一副本。任一不匹配即新建运行目录并重新只读分析，绝不把旧色板、旧截图或旧 PASS 带入新任务。

`mutationPlan` 保存 `runId`、源/副本 ID、`sourceToCloneNodeMap`、`reviewScenes`、`writePlan`、`singleWriteReceipt`、`finalReviewReceipt` 和 `executionPhaseLog`。恢复时先核对输入与唯一原稿快照；若写入已发生但未终审，先完成该事务终审，不能重放写入；失败后的修复另行冻结事务。

唯一写入前落盘完整 `writePlan`：每个原子属性操作的 `before/after`、依赖、保护和目标映射。一个颜色叶子或文字区间 API 调用是最小核对单元；技术数组切片仍属于同一 Figma 调用。

唯一写入调用在同次 setter 后核对并分类回执：

| 当前属性 | 处理 |
|---|---|
| 等于目标值 | 已完成 |
| 等于前值 | 未完成；记录并终止，不自动补写 |
| 既非前值也非目标值、节点缺失 | 冲突；记录已发生的部分写入并终止 |

不得把冲突值自动改成新的 `before` 来覆盖，不盲目重复整个脚本。所有成功/失败/未知操作都保留，超时不等于失败回滚。原稿检测到外部修改时重新分析受影响依赖，不擅自将原稿恢复成旧快照。结构操作单独核查实际存在性和映射；纯属性恢复工具不负责重试 clone、detach、增删层。

只对受影响场景重新取图；未变化原稿视图、快照和已审过的同一渲染可复用。全量原稿/副本结构最终仍各核对一次。任何写入后的截图不得复用写入前的文件冒充新证据。

### 3.1 完成后的临时证据清理

`finalAudit=pass|pass-with-warnings` 且完成回复所需摘要已提取后，默认执行：

```sh
python3 scripts/run_workspace.py cleanup ABSOLUTE_RUN_WORKSPACE
```

清理范围是该目录内的全部本次运行文件，包括下载素材副本、配色提案、快照、试色/最终截图、派生视图、节点映射、差异、批次、门禁和审计 JSON。Figma 原稿、副本和用户提供的原始文件不在清理范围。运行未完成、需要继续恢复，或用户明确要求保留审计包时不清理；取消任务且用户不需要恢复时也清理。

清理脚本必须校验系统临时根、目录前缀和运行标记，只接受本 Skill 自建的精确目录。禁止 `rm -rf` 通配符、禁止扫描并批量删除旧目录、禁止删除仓库内 `artifacts/` 或任何未带有效标记的路径。清理返回值写入完成回复：`pass`、`kept-by-user` 或 `not-complete`；失败时报告精确原因并保留目录，不绕过校验。

## 4. 可复用工具

工具只收集/比较数据，不判断语义角色、计算真实裁切交集或自动批准视觉 PASS；JSON 检查通过不能代替渲染验收。普通审计使用 Python 标准库；辅助视图另需 Pillow。当前目录以 skill 根目录为例。

### 4.1 Figma 快照

读取 [figma_snapshot.js](../scripts/figma_snapshot.js)，将其函数定义原样放入已按 `figma:figma-use` 准备的 `use_figma` 调用，再执行 `return await snapshotThemeTree(figma, actualRootId)`。不使用历史脚本中的固定 ID，不加载字体，不改设计。返回 JSON 完整保存，常规输出只展示节点数、错误和产物路径。

快照结构为 `{schemaVersion:1, collectorVersion:1, rootId, capturedAt, nodes:[{id,parentId,children,props}], errors:[]}`。默认包含隐藏实例后代，结束时恢复遍历设置；读取错误显式记录，审计拒绝不完整快照。文字各属性独立合并区间，颜色区间拆分不应制造字体变更；Vector region Paint 保持在独立属性路径，允许其颜色变化不等于允许顶点/线段变化。

它覆盖常见活动页的显式属性；新节点能力、特殊文字属性和引用型状态需补充读取，不能把未采集属性声称为已验证。绝对坐标不参与原稿→副本机械比较，避免合法根 x 位移造成全树误报；几何用本地坐标/变换核对，实际裁切和截图定位另用真实绝对变换。需要更新采集字段时统一修改此脚本并重建可比快照。

### 4.2 差异与保护检查

```sh
python3 scripts/theme_audit.py diff source-before.json source-now.json source-policy.json --out source-diff.json
python3 scripts/theme_audit.py diff source-before.json clone-now.json clone-policy.json --map node-map.json --out clone-diff.json
```

`node-map.json` 是完整、唯一的源 ID→副本 ID 对象；解绑后重建。工具只规范化节点自身及父子引用，不猜测同名节点，不忽略新增/删除节点。其比较空间是 `/nodes/<源ID>/props/...`，同 ID 检查不需映射。

策略格式：`{"schemaVersion":1,"allowedChanges":[],"protectedPaths":[]}`。原稿 `allowedChanges` 必须为空；副本每个允许差异为 `{path,before,after}`，由**写入前方案和预期属性**建立，不从实际错误结果反推授权。路径采用 JSON Pointer，如 `/nodes/1:2/props/fills/0/color/r`；数量变化作为整个数组差异，必须单独列明前后完整值。根 x/relativeTransform 的合法变化分别登记。

保护路径覆盖该属性全部后代，优先于允许差异；不能笼统允许整个节点。混合文字或 Vector 保护须精确到区间/区域并确保索引仍有效；若文字区间合并/拆分使保护路径失效，先重新按原字符范围核对和映射，不能移除保护或用宽泛例外让脚本通过。工具的差异表不自动区分业务许可，登记例外仍必须符合主 skill。

颜色读回按预先声明的目标配方校验；只有第 3.2 节浅→浅基线真实通过后所沿用的通道，或当前明确锁定的通道，才要求与源值保持，不复用历史任务中强制保留源 S/V 的专用校验代码。属性差异通过不代表按钮、CTA 或 Icon 已在背景上突出，视觉门禁仍按《颜色决策规则》第 3.2 节执行。

原稿/保护属性和差异发现使用精确值；仅已登记的目标数值允许绝对 `1e-6` 的浮点读回误差，避免把 Figma 的 0.699999988 与计划 0.7 误判成部分失败。`diff=pass` 表示没有越界差异，不证明所有计划已经执行；完成检查还须逐批确认待写和冲突均为空。

### 4.3 部分写入恢复

```sh
python3 scripts/theme_audit.py recover clone-now.json batch.json clone-id-policy.json --out recovery.json
```

`batch.json`：`{schemaVersion:1,batchId,operations:[{path,before,after}]}`。恢复命令全部使用**副本 ID**命名空间，不使用源 ID 策略。操作路径指向现有节点属性；文字区间可用规范化 `textRuns` 作为读回单元，实际执行仍调用允许的文字 API，不能直接给快照字段赋值冒充 Figma 写入。操作不可重叠；保护与许可按实际变化通道检查。输出 `completedPaths/pendingOperations/conflicts`，存在冲突或越界时不输出可执行补写列表。`ready` 只表示可安全恢复这一属性批次，扩展仍需另外检查试色门禁。

### 4.4 场景门禁

```sh
python3 scripts/theme_audit.py scene-state clone-after-trial.json scene-spec.json --out scene-state.json
python3 scripts/theme_audit.py seal-gate scene-state.json visual-review.json --out gate.json
python3 scripts/theme_audit.py scene-state clone-fresh.json scene-spec.json --out scene-current.json
python3 scripts/theme_audit.py check-gate scene-current.json gate.json --out gate-check.json
```

`scene-spec.json` 含 `sceneId/dependencyNodeIds/recipe/nodeMap/protectedPaths/writePaths/reviewRequirements`，全部 ID/路径为副本命名空间（`nodeMap` 的键为源 ID）。依赖自动包含指定根的后代和全部快照内祖先；**重叠兄弟、背景材质和邻近对照仍需显式列入**，不靠工具猜测语义。不要把页面根作为局部依赖种子导致全树进入每个场景；页面根作为祖先时只纳入自身属性。最终整页验收可另用根作为场景。

`reviewRequirements` 在写入前登记 `{id,acceptance,nodeIds}`，至少包含 `theme-consistency/clarity/hierarchy`；存在 Icon 底托、选中 Tab 与主要按钮时，`hierarchy` 必须明确验收 `icon-container < selected-tab < primary-button`。存在表面边界或控件状态时，分别登记 `surface-discernibility/state-discernibility`，不能合并成文字可读或笼统 clarity；按实际角色再包含按钮显著性、CTA 最强操作、Icon 清晰度、文字、材质和用户专属规则。规则 ID/验收条件来自第 5 节冻结的清单，`recipe.ruleLedgerHash` 引用其指纹。验收条件不得由失败结果反推或临时放宽。

`theme-consistency` 的 acceptance 同时包含已选 `accentFamilyPlan`：Icon 稳定主体是否来自连续背景环境，深色 UI 的 `number/icon` 是否同 Hex，以及数字/Icon/按钮的显著家族关系。Icon 的小面积金属反射单独记录材质职责，不据此把稳定主体改成新的高亮色。

`visual-review.json` 含 `{sceneId,status,reviewedAt,notes,screenshots,checks}`；每个 check 为 `{id,status,observation,comparison,nodeIds,screenshots}`。checks 必须完整覆盖预登记条件，实际观察写出主体、材质或状态的表现，comparison 写出与真实背景/弱控件的关系；不能仅写“协调、可读、没问题”。逐项引用实际查看的截图和节点；一个截图可以证明多项。`fail/unknown`、缺项、漏节点、无比较或截图均不能封存 PASS；不适用必须在预检清单中有证据，不能验收时临时用 N/A 消除失败。`reviewedAt/capturedAt` 必须带时区。

封存工具验证完整性与证据哈希，不识别图片好坏，也不自动生成审核理由。只有已实际查看目标上下文并满足视觉标准后才写 pass；复核必须使用 Phase 7 唯一终审的新鲜快照。各场景门禁放入 `mutationPlan.finalGates`。

### 4.5 截图派生

```sh
python3 scripts/render_views.py scene-screenshot.png scene-views --blur-radius 3 --thumbnail-width 240
```

从同一真实截图生成彩色原尺寸、灰度、模糊和缩略图，清单记录源哈希及参数。输入必须包含真实背景；透明图被拒绝，不默认铺白。1:1 需另确认截图像素与设计尺寸比例，不能用低分辨率整页图放大冒充。工具不裁图、不改 Figma、不调用生成式模型。

审计命令用 `--out` 保存完整 JSON：退出码 0 表示本命令成功，1 表示差异失败/冲突/过期，2 表示输入或读取错误。派生视图用输出目录，错误时退出非零。任何非零结果先排查，不算门禁通过。本地验证：`python3 -m unittest discover -s tests -p 'test_*.py'`、`node --test tests/figma_snapshot.test.js`。

### 4.6 同色关系检查

```sh
python3 scripts/theme_audit.py color-relations source-before.json clone-now.json color-relations.json --manifest manifest.json --map node-map.json --out color-relation-audit.json
```

`color-relations.json` 是 `sourceAudit.sourceColorRelations` 的人工语义关系输入视图：`{schemaVersion:1,groups:[{id,reason,paths:[颜色通道路径,...]}],automaticGroupPlans:[...]}`。每个 `groups` 成员至少含两个通道，`reason` 记录同角色、状态、材质、等价宿主或连续表面证据。除此之外，工具从完整 manifest 自动重建全局源 sRGB8 等价组；人工文件不能删减自动组。路径指向源 ID 命名空间下的完整 RGB(A) 对象，如 `/nodes/1:2/props/fills/0/color` 或 `/nodes/1:3/props/fills/0/gradientStops/0/color`，不能只填 r 通道。同族文字等价组的状态 Alpha 单独保留，RGB 按冻结的等价组/合法状态分区处理；Paint/祖先 Alpha、渐变几何和实际合成另由结构及视觉检查负责。

除人工语义组外，工具在传入完整 manifest 后会对所有 `disposition=change` 的源通道按 sRGB8 自动建立等价组，默认要求目标仍为同一 sRGB8；有源证据的预冻结语义分区按下述契约检查，人工 `groups` 的硬等价仍独立成立。`protected/preserve/ignore` 不与可换肤组强绑。每个语义组/分区的目标在角色展开前只决定一次，不允许各成员独立取色。

独立源职责可在 `automaticGroupPlans` 登记以下格式；不是用户确认点：

```json
{
  "id": "automatic-source-rgb8-255-187-149",
  "relationType": "semantic-partition",
  "sourceHash": "规范化原稿快照哈希",
  "paths": ["/nodes/number/props/fills/0/color", "/nodes/button/props/fills/0/color"],
  "reason": "原稿数字与按钮分别承担信息强调和操作主体职责",
  "partitions": [
    {"role": "text.number", "paths": ["/nodes/number/props/fills/0/color"], "sourceEvidence": "原稿收益数字及其真实宿主"},
    {"role": "button.primary", "paths": ["/nodes/button/props/fills/0/color"], "sourceEvidence": "原稿主要操作底板及状态"}
  ]
}
```

路径必须覆盖自动组且每条恰好一次；每个分区有独立且与 manifest 一致的 role、原稿证据，内部目标 sRGB8 相同。组内所有 surface 成员保留在一个分区；显式 `groups`、表面系统、材质和同族控件门禁仍独立执行。缺证据时继续调查原稿，不为绕过失败改角色、伪造职责或临时 monkeypatch 审计。该接口检查已记录职责的一致性，不能自动证明人工语义判断正确。

未作语义分区且自动组同时含有 `surface` / `surface.*` 角色和任一非表面角色时，必须在 `automaticGroupPlans` 中精确覆盖该组：

```json
{
  "id": "automatic-source-rgb8-50-35-29",
  "relationType": "surface-linked-equivalence",
  "targetBasis": "surface-recipe",
  "anchorPath": "/nodes/card/props/fills/0/color",
  "paths": ["该自动组全部且仅有的颜色路径"],
  "reason": "原稿中非表面成员以该稳定表面颜色形成透底、间隔、连续或负空间"
}
```

`anchorPath` 必须是组内真实表面成员，不能选择更方便的 Icon、描边或文字通道；目标值来自这个表面的已审配方，不在关系文件重复写 Hex。缺计划、路径集合过期、锚点不是表面成员或改用非表面配方，`color-relations` 直接失败。这是跨控件的关系门禁，不限定圆、勾、进度条或任何节点名称。

原稿截图中视觉相同但存储 RGB 不同的元素，另以 `displayed-relations` 的 `source-appearance-equivalence` 登记并冻结各元素真实主体坐标；工具先要求源样本的 L*/ΔE76 跨度均不大于 2，再要求目标跨度不超过源稿，不允许附加余量。若该组横跨表面与非表面，把 `relationType` 改为 `surface-linked-appearance`，同时冻结 `targetBasis=surface-recipe` 和表面采样点的 `anchorPointIndex`。不得用不同节点类型或新语义角色作为自动拆色理由。

人工关系成员按原稿语义、状态、材质职责和真实宿主在选新色前确定；**不得把目标 RGB/Recipe 值放进分组键**，也不得在成员不一致时拆组让审计通过。源职责必须先审查并冻结，不能从目标失败反推例外。独立职责的合法语义分区由执行者自主决定；显式连续/同族等价不接受分区豁免。`relationType` 缺省为 `source-equivalence`；有预先声明的 `basis` 时可用 `target-shared` 检查跨角色共享目标 RGB，或用 `hue-family` 加本次场景的 `maximumHueDistanceDegrees` 检查同族有彩色主体。`surface-linked-equivalence` 与 `surface-linked-appearance` 只保存关系、锚点和来源证据，不另造目标色。普通小按钮与 CTA 的稳定主体路径仍必须共同引用 `schemeAnchorContract.button`。

同一显示表面由不同底色/Alpha/宿主合成时，另加 `displayed-surface-continuity` 机器规则，verifier 为 `{type:"displayed-relations",groups:[{id,nodeIds,xy:[原生截图坐标,...],nativePixels:[宽,高],maximumChannelDelta:本次容差}]}`。Phase 3 冻结同职责空白采样点；采样覆盖 Tab 底与下方实际容器，避开媒体、字形、指示条及局部高光。`finalize` 的 `displayedSamples` 指向 `{sourceHash,actualHash,groups:[{id,source:[{image:{path,sha256},xy},...],actual:[...]}]}`，绑定对应快照并核验源/新像素关系。实际图片必须同时属于新鲜视觉门禁证据。该检查验最终合成，不要求参与合成的裸 RGB 相同，也不能以“基底同色”抵消最终断层。没有可验证样本或源稿关系不成立时，重新定位关系，不声称已经完成机器验收。

先从原稿建立分组，再由预检配方生成 `expectedClone` 运行同一检查，明确标为计划验证；Phase 7 以唯一最终快照再次验证。语义拆分理由另记 `themeDecision`，不从错误结果反推预期。

原稿存在同族主要小按钮和 CTA 时，`colorManifest.schemeAnchorContract.button` 必须保存共同 RGB；每个主要小按钮与 CTA 至少一个稳定主体通道标记 `anchorId=button`，执行审计直接核对这些目标值等于共同锚点。`button-appearance-family` 仍是必需机器规则，verifier 用 `displayed-relations`，组为 `{id,relationType:"appearance-family",basis,carrierPaths,nodeIds,xy,nativePixels,additionalLightnessSpread,additionalColorSpreadDeltaE76}`，检查派生暗部、高光和真实合成没有造成可见异色分裂。`button.material/cta.base/cta.material` 专指该主要交互家族；次级、禁用或源稿明确非等价的控件用有依据的独立语义角色，不能把失败成员事后改为次级。`carrierPaths` 包含该家族全部实际参与的对应材质通道，每组同时包含小按钮与 CTA；源通道清单自动核对联合组与 `control-family-consistency` 的完整范围，不能仅登记 Tab 或把大小按钮拆成两个各自通过的组。

六色方案的精确执行由 `scripts/execution_audit.py` 的 `scheme-anchor-conformance` 统一检查：`schemeAnchorContract` 必须且只能包含 `background/card/number/icon/button/tab`，每个角色至少有一个稳定可见通道标记相同 `anchorId`，且 `target` 与锚点 RGB 完全一致。该检查在 `expectedClone` 预检和最终真实副本审计中各跑一次。

`xy` 冻结原生截图中各成员的同职责主体取样，稳定主体、对应受光区分别比较，不拿小按钮主体与 CTA 窄高光相比，也不只取最有利的单点。样本沿用 `displayedSamples` 证据格式与新鲜门禁绑定。工具从实际合成 sRGB 计算 CIELAB L* 和 ΔE76，要求新稿的组内明度跨度/色差不超过原稿跨度加写入前明确的情境余量；两个余量分别给出、须有限且非负，无统一默认值。这里约束的是同族内部接近关系，不冻结原稿绝对 L*，也不恢复跨模式逐点对比度下限。数值通过仍须检查完整按钮与各自真实宿主上的视觉重量、材质和全局操作优先级。失败后改颜色或重新诊断源稿关系，不能从失败数值反推放宽余量。

`color-relations` 是必需机器规则，verifier 为 `{type:"color-relations",groupsHash:完整关系文件的digest}`；Phase 3 冻结，finalize 必须引用 `colorRelations` 并重新比较实际结果。确无同色关系时仍提供 `{schemaVersion:1,groups:[]}`，verifier 另附 `emptyEvidence` 说明原稿事实，不能漏掉整条规则。有依据的角色/宿主变体须在写入前更新登记表与冻结规则，并使相关门禁失效；不能从实际错误颜色反推拆组。

人工硬等价组默认检验原稿组内 RGB 确实相等、新稿组内仍相等（`comparison:"float"`，仅容许 `1e-6` 浮点误差）；自动组固定按 sRGB8 检查完整 manifest 中的全部可换肤通道。缺路径或不完整快照报错。它能抓到 Vector/Frame、不同区域和不同语义角色因映射分流而拆色；显示合成相同但存储值不同的情况仍由零附加跨度的原生像素组补齐。保存结果于 `finalAudit.colorRelationAudit`，失败回到对应映射和场景。

### 4.7 原稿对比度基线检查

执行标准与覆盖职责只维护在《验收规则》第 5.1 节。复用 `contrast_audit.py`，不临时重写亮度公式或手写 PASS：

普通半透明文字/图形叠在复杂宿主上时，颜色 spec 可用 `{host:{image:{path,sha256},xy:[x,y]},layers:[{colorPath,alphaPaths}]}`：宿主来自经哈希验证的原生截图无字形区域，前景来自真实快照的 NORMAL SOLID Paint；只乘一次实际 Paint/节点/祖先 Alpha，不能用抗锯齿字形像素代替前景。

```sh
python3 scripts/contrast_audit.py source-before.json clone-now.json contrast-samples.json contrast-relationships.json --map node-map.json --out contrast-baseline-audit.json
```

`contrast-relationships.json` 为 `{policy:"source-baseline"|"contextual",decisionContext:{sourceUiMode,targetUiMode,adaptationMode,reason},pairs:[{id,kind,nodeIds,sampleIds,minimumContrast?,minimumDeltaE?,stateGroupId?}],emphasisOrders:[{id,strongerPairId,weakerPairId,sampleId}]}`，kind 为 `text/surface/state/icon/button`。跨模式 `surface` 必须冻结 `minimumDeltaE >= 3`，按原稿职责确认为 `container` 的内部容器不低于 4；`state` 必须有 `stateGroupId`。工具自动枚举同组、同宿主、同采样职责中源比值不相等的全部成对顺序，任一未进入 `emphasisOrders` 即报错；不能只登记代表节点。

`contrast-samples.json`：`{schemaVersion:1,policy,decisionContext,sourceHash,actualHash,pairs:[{id,kind,nodeIds,samples:[{id,basis,source:{foreground,background},actual:{foreground,background}}]}]}`。两种颜色输入：`{layers:[{colorPath,alphaPaths:[]},...]}` 为自下而上的 NORMAL 纯色实际属性路径、以不透明宿主开始；或 `{image:{path,sha256},xy:[x,y]}` 为包含真实背景的原生截图像素。basis 写明叠层/取样依据。不能把复杂渐变或其他混合伪装为纯色叠层；脚本不推断真实遮挡、语义与采样代表性，须按视觉门禁核实。颜色/透明度路径采用源 ID 的规范化空间；sourceHash/actualHash 使用 `theme_audit.digest(snapshot_document(...))`，actual 文档先用 `mapped_document` 完整映射。
可在预演截图落盘后运行 `python3 scripts/prepare_contrast_sample_queue.py <source-before.json> <expectedClone.json> <manifest.json> <rule-ledger.json> --out <runWorkspace>/contrast-review-queue.json`，逐关系列出文字区间、最近已登记宿主、Paint 路径和简单 SOLID 的属性候选；纯色文字 Paint/节点 Alpha 有精确路径且宿主是单层不透明 SOLID 时可给出自下而上的合成候选。输出始终为 `needs-review`，不是 `contrast-samples.json`：还须核对真实原稿/预演 1:1 图中的文字覆盖区、叠层、遮挡及宿主；复杂渐变、多 Fill 或无法确定的 Alpha 不得套用纯色候选。审完后按上述 schema 人工冻结真实样本，再运行 `preflight_full.py --stage full`。

在 `contrast-baseline` 规则设置 `verifier:{type:"contrast-baseline",policy,decisionContext,relationships:[...],emphasisOrders:[...]}`，样本文件同时携带完全相同的 policy、decisionContext 与 `emphasisOrders`，最终 spec 引用 `contrastSamples` 文件。finalize 从最终新鲜快照重算，拒绝旧指纹、缺失/重复关系或采样、范围变化、策略/模式/画风依据漂移、适用数值下限失败，以及已冻结的强弱顺序倒置；仅 source-baseline 拒绝任一源比值或相对力度回退；最多 `1e-9` 的计算误差不构成设计容差。contextual 下没有明确 minimumContrast 的样本只记 measured，测量完整不等于视觉 PASS；minimumContrast 仅来自用户明确标准或写入前有依据的角色目标，不自动套 WCAG，不从失败结果反推宽松下限。所有策略仍需真实可辨性、主体明快、操作/状态层级与材质视觉门禁通过。旧文件缺 policy/context 时仅兼容原 source-baseline，不能静默降级为 contextual。新旧截图使用相同的原生量化口径；同一关系的复杂背景应冻结足够的可比较样本职责，而不是事后只挑最有利像素。

### 4.8 视觉单元与局部修正闭包

`sourceAudit.visualUnits` 只维护一份结构关系登记表；旁文件输入为：

```json
{
  "schemaVersion": 1,
  "sourceHash": "原稿规范化文档的digest",
  "units": [{
    "id": "creation-tabs",
    "basis": "原稿截图与层级确认：选中异形底板、相连底板及内层列表构成连续表面",
    "carrierPaths": ["/nodes/源ID/props/fills/0/color"],
    "dependencyNodeIds": ["完整控件根", "真实颜色承载层", "外卡宿主", "相关遮罩/叠层"],
    "reviewNodeIds": ["完整控件根"],
    "reviewRuleIds": ["surface-discernibility", "state-discernibility", "hierarchy"]
  }]
}
```

示例路径与 ID 须替换为真实值，`carrierPaths` 须填全，不是只写一个外层。全量 manifest 每个 RGB(A) 通道只能归入一个主单元，含 Vector region、文字区间、每个渐变色标、内层 Frame、隐藏/保护通道。主单元用于定位，跨单元关系继续引用原同色组与对比关系，不重复抄写成员。单元以真实完整视觉结构为依据，不按 RGB 全局分桶；独立图片/控件不因同色自动归并。

`dependencyNodeIds` 明确包含所有 carrier 所在节点、完整控件根及实际宿主/影响层；工具补充全部祖先。不是自动计算遮挡或蒙版交集，相关兄弟叠层、图片与跨区域宿主仍须人工依据真实读取登记。`reviewNodeIds` 为需要完整对照的单元根，属于依赖并位于每项冻结视觉规则的 scope 内。只读/保护成员不获得写入权限，所有写入仍由原白名单及保护策略决定。

Phase 3 在 `visual-unit-coverage` 机器规则冻结 `{type:"visual-unit-coverage",registryHash:登记表digest}`，final spec 必须引用 `visualUnits`。finalize 检查原稿指纹、全量颜色通道归属、依赖完整性及冻结规则范围；每个单元须有一个新鲜通过的场景同时包含全部依赖与对应根的全部指定视觉检查。多个各缺一部分上下文的局部 PASS 不能拼成完整单元 PASS。一张包含完整上下文的真实截图可以支持多个单元和规则。

首次试色、扩展及局部修正均引用这份登记表。局部修正前执行：

```sh
python3 scripts/execution_audit.py impact source-before.json color-manifest.json visual-units.json color-relations.json contrast-relationships.json changes.json --out affected-units.json
```

`changes.json` 为 `{changedPaths:[源ID命名空间的实际属性JSON Pointer,...]}`，原子 Fill 数组或精确颜色通道均可；解绑先重建映射。输出受影响单元、同色关系、对比关系、强调顺序、视觉规则与只读依赖。工具从直接改动及祖先/宿主影响出发，沿同色/对比/顺序关系迭代到闭包；未受影响单元不重验。输出仅列待复验内容，不授权写入，也不直接让任何门禁通过。

原稿分析及登记表在原稿未变化时复用；新发现的漏层须先补完整成员/依赖，再更新冻结规则并使关联门禁失效。修改配方先跑计划快照的同色、对比/顺序检查，通过后按既有阶段写入，实际读回后重算并看源/新 1:1 彩色与灰度完整对照。机器只能证明登记完整与已声明关系成立，无法证明人工没有把内层归错单元或虚写视觉通过；实际连续区域追踪与对照不可省。

每个含两个及以上可见颜色职责的视觉单元还须建立一份 `materialRelationPlan`，成员使用源节点命名空间的 `sourceId` 与相对 `props` 的 JSON Pointer，例如 `/fills/0/gradientStops/1/color`；跨节点的卡顶氛围圆、标题主体/高光、Icon/按钮材质层同样登记。`preserve` 声明要保留的 `rgb/saturation/value` 轴，`preserveOrder` 声明饱和度/明度职责顺序。源成员存在重复/交替颜色角色时，工具默认启用 `preserveRoleGroups`：同一源角色的目标成员保持相近、不同源角色继续分离。`expectedClone` 和最终副本快照分别运行：

```sh
python3 scripts/material_relation_audit.py source-before.json target.json node-map.json material-relations.json --out material-relation-audit.json
```

`allowFlatten` 默认为 `false`；只有写入前已有具体 `allowFlattenReason` 才可作为显式例外，并仍需原生 1:1 视觉证据。脚本 PASS 只证明已登记关系没有被压平，不替代材质、氛围或标题的视觉验收。

## 5. 执行覆盖、严格验收与性能

### 5.0 统一规划、连续执行、集中审查

本节统一流程调度，第 5.4 节负责传输和批处理工具。阶段表示证据依赖，不要求重复生成同一份数据。

1. **一次分类，按家族决策。** Phase 1W 从唯一完整快照建立颜色通道总表，以源节点＋属性路径为唯一键，登记角色、区域、家族、材质职责、状态、宿主和保护类别。标题/Icon 清单、区域写集及审查范围全部从总表派生；不确定项只能从已保存快照和截图继续分析，不回 Figma 定向补读整树。
2. **一份配方，全实例投影。** Phase 3 按 recipeId 与指纹维护家族配方，各实例补具体通道映射与必要变体。每个等价实例和所有非等价材质/宿主/状态都进入 `expectedClone`；不存在“代表通过后再决定剩余实例”。
3. **一份权威计划，一次正式写入。** `mutationPlan` 同时维护 clone/KV/解绑/颜色操作、配方引用、区域归属和最终审查范围。区域文件只用于离线组织与代码生成，不成为独立写入批次。任何配方改动先重建投影并重跑可回收预演，正式写入后不自动修订计划重试。
4. **结构准备也属于正式写入。** Phase 4 只在本地规划 KV 适配、必要实例解绑、颜色绑定解除、完整映射规则和副本目标；这些操作与颜色叶子在 Phase 5 可回收预演和 Phase 6 正式写入中必须使用同一冻结函数。禁止为了建立永久副本基线提前写一次。
5. **终审集中取证。** Phase 7 一次获取完整副本及全部预登记截图；局部视图、灰度、模糊、缩略图和跨区并排图都从该证据本地派生，不逐卡远程截图。
6. **写前集中消除问题。** `expectedClone` 与可回收原生预演的任何机器或视觉预检失败都按共同配方、错误映射和单实例差异在本地修复、重新投影并重新预演；不得把已知问题带入唯一正式写入。
7. **最终审计不自动回写。** 最终新鲜全树状态重算结构、保护、覆盖与目标达成，另验跨区关系及全页累计效果；失败即报告未完成，不定向重取整树或自动修复。

重复转换、分区和切批优先调用现有通用工具；任务级程序仅用于现有工具确实无法表达的转换，并记录缺口。节点 ID、目标色和角色映射放在运行数据中。需要持续复用的缺失能力应完善现有入口并验证；不得声称尚未实现的固定生成器已经可用，也不默认每次复制一套任务专用 build_manifest/build_region_plans 程序。

### 5.1 先把适用规则落到对象

在 `themeDecision.ruleLedger` 登记本次适用规则：`{schemaVersion:1,rules:[{id,kind,applicable,source,acceptance,scopeNodeIds}]}`。source 指向用户要求或维护的规则章节；acceptance 写明可观察的通过条件。`scopeNodeIds` 使用源 ID，覆盖该视觉规则涉及的全部实际实例；最终映射到副本。机器规则不必提供该字段。不适用项仍保留，附 `notApplicableEvidence`；不以名称不熟、嵌套深或旧色不明显作为不适用依据。

基线机器规则 ID：`source-unchanged/clone-allowed-differences/color-coverage/plan-complete/contrast-baseline/color-relations/material-relations/visual-unit-coverage/icon-glyph-coverage/color-bindings-clear`，全部必验。`material-relations` 检查冻结关系和重复源角色组；`icon-glyph-coverage` 检查每个功能 Icon 根下的全部可见颜色通道及保留理由。不存在多色视觉单元或功能 Icon 时须以全量清单给出不适用证据。基线视觉规则 ID：`kv-fit/theme-consistency/clarity/hierarchy/button-salience/cta-salience/icon-clarity/readability/material-layers/surface-discernibility/state-discernibility/control-family-consistency`；存在对应角色就必验，不能手写机器 PASS。

Phase 3 写入前冻结清单哈希；清单变更使关联门禁失效。规则位置不重复搬进 ledger，仅记录适用范围和验收条件。脚本不能自动判断是否完整提取了自然语言规则，必须对照本次用户要求和适用参考章节逐项核对；也不能以脚本支持的字段为由缩减设计规则。

### 5.2 全量枚举防漏，目标校验防未执行

颜色清单必须深入 `textRuns.fills`。生成 `textRangePlan` 时按完整快照的 styled fill range 原边界逐段登记，不能在紧凑传输或区域拆分时降级成节点级 TEXT；每段引用清单中的全部颜色路径、真实宿主和对比度关系。跨深浅模式再生成 `crossModeCompositePlan`：从完整颜色清单自动派生有效 Alpha、文字、氛围和渐变候选，而不是由人工挑代表；渐变/氛围候选同步生成边界组。两份计划只增加本地分类与校验，不要求额外逐节点 Figma 往返。

`iconGlyphPlan` 格式为 `{schemaVersion:1,sourceHash,roots:[{rootNodeId,channels:[{path,part,action,reason,themeNeutral?,neutralEvidence?}]}]}`。`part` 为 `glyph/container/reflection/protected`，`action` 为 `change/preserve/protected`。每个 Icon 根下的可见颜色清单路径必须且只能出现一次；`glyph + preserve` 必须同时提供 `themeNeutral=true` 和非空 `neutralEvidence`。

```sh
python3 scripts/execution_audit.py inventory source-before.json --out color-inventory.json
python3 scripts/execution_audit.py coverage source-before.json color-manifest.json --out coverage.json
python3 scripts/execution_audit.py complete source-before.json clone-now.json color-manifest.json clone-policy.json --map node-map.json --out completion.json
```

`sourceAudit.colorInventory` 保留只读枚举结果；`mutationPlan.colorManifest` 是从该结果与已声明配方生成的全量分类/目标视图：`{schemaVersion:1,sourceHash,ruleLedgerHash,entries:[{path,role,disposition,reason,ruleId,recipeId,sceneId,target}]}`。每条实际存储 RGB 通道，包括 Fill、Stroke、Effect、Vector region、每个渐变色标及文字区间，均只能出现一次。disposition 为 `change/preserve/ignore`；保留或忽略写出职责与依据，change 另有目标 RGB、配方和代表场景。可见通道不能 ignore；布尔子图形、结构中性色或主题一致的颜色可有依据 preserve。隐藏/零透明度通道仍列入完整性清单，不能误报为可见参考。IMAGE 与特殊属性另按原有素材清单审计，不把 RGB 枚举声称为全部图像/语义覆盖。

覆盖差集必须为空，不能用“改了多少节点”或仅统计操作列表来证明无遗漏。`diff=pass` 只证明未发现越界；`complete` 还核对所有允许差异已达到声明的 after，及清单中的变化/保留值是否正确。漏写、未达目标、未授权目标、源快照变化、未知/重复通道均失败。文字区间重分段或解绑后若路径变化，按原字符范围/稳定映射重建可比视图，保留旧记录，不能让缺失路径变成免验。新 KV、结构例外与不可采集能力仍按其专门审计验证。

### 5.3 最终结论由必需检查汇总

```sh
python3 scripts/execution_audit.py finalize finalization-spec.json --out release-check.json
```

spec 是旁文件视图，引用 `sourceBefore/sourceNow/cloneNow/manifest/policy/nodeMap/ruleLedger` 的 JSON 路径和最终 `visualScenes:[{spec,gate}]`，必须同时引用 `colorRelations/materialRelations/contrastSamples/visualUnits`；`manifest` 内必须包含与源快照绑定的 `iconGlyphPlan`。finalize 重算 Icon 图形逐路径覆盖、材质源角色组、原稿与新稿合成对比度、状态组完整强弱顺序和完整视觉单元；缺证据、任一样本/关系失败均不放行。至少包含一个 `reviewScope:"whole-page"` 的最终整页场景，依赖种子为最终根，`hierarchy` 覆盖根并有整页截图。

`control-family-consistency` 还要求至少一个有效场景在同一次比较中覆盖该规则全部冻结 scope，不能由多个各只覆盖一张卡的 PASS 累加通过。可从同一原生全页图裁出并排片段，保留裁切来源/比例，并实际查看相邻与远处同族实例；整页层级检查可共用图像，不额外反复渲染。

任一必需项 FAIL/UNKNOWN、缺规则、漏实例、过期证据或允许差异未完成，整体均 FAIL；不能按通过比例、平均分或大多数区域正确放行。警告只用于全部必需门禁已通过后的非阻塞信息，不能容纳不可读、暗沉、不突出、漏改或违反保护。若保护色与新 KV 可读性无法兼顾，保留保护并准确报告未完成及具体冲突，不降级为警告。最终整页累计焦点仍必须实际查看，不能用局部代表的 PASS 推导全页美观。

### 5.4 缩短调用链，保持检查覆盖

- **配色提案使用快速只读路径。** Phase 0/1P 首次远程读取只返回：页面与两个候选顶层节点的 ID/类型/尺寸、原 UI 缩略图、新 KV 原生截图、直接影响 `sourceUiMode`/显著性/同族控件的精简摘要，以及新旧 KV 画风比较所需证据。禁止在同一返回中附带全树 Paint/Gradient、全部文字、全部路径或大段节点 JSON；预计超过约 12KB 时先聚合计数，再按明确缺口定向读取。不要对 `PAGE` 截图，也不要用 `figma.io.write` 代替视觉截图；直接对 UI/KV 节点使用 `get_screenshot` 或 `node.screenshot()`。高长 UI 先取一张缩略整页图，只有看不清的关键区域才补原尺寸局部图。
- 新 KV 截图只下载一次到本次 `runWorkspace`。优先运行 `python3 scripts/analyze_kv_preview.py <kv.png> --out <runWorkspace>/kv-analysis-fast.json` 生成候选色群和底边连续性统计，再由视觉判断环境/前景/材质身份；不为聚类临时引入 NumPy、科学计算依赖或重复导出。配色预览只在候选通过前置门禁后生成一次，修改色值才重渲染。
- 用户选色前不采集或传输完整 `snapshotThemeTree`，不建立逐实例 `layerStacks`、全量 `visualUnits`、所有文字区间和对比度关系。用户选色后进入 Phase 1W，一次性采集完整原稿快照并建立写入级基线，然后才允许 Phase 3；若用户未选择，昂贵审计不会白做。此延迟只优化时机，不降低任何写入或最终验收要求。
- **Phase 1W 固定快照路径。** 用 `python3 scripts/generate_figma_baseline_js.py <sourceFrameId> --page-id <pageId>` 生成经本地测试、长度小于 45,000 字符的 `use_figma` 程序；仅在当前页已是目标页或平台无需切页时可省 `--page-id`。一次 `snapshotThemeTree` 完整遍历（含隐藏实例子层），同次返回紧凑的区域/颜色/变量与样式绑定风险摘要，并以 `figma.io.write` 产出带长度与校验和的无损二进制 image block；这是数据传输，不是视觉截图。把该 block 原样保存到本次 `runWorkspace`，用 `python3 scripts/decode_theme_snapshot_png.py <artifact> <runWorkspace>/source-before.json` 解码；若保存的是 base64 文本，增加 `--base64`。节点数、根 ID、读取错误、校验和及字节长度必须全部核对后才建立基线。不得把缩略图、截断文本或仅有摘要当完整基线。若 image block 缺失/被转码，只记录一次失败；仅在后备分片能对应**同一次稳定采集**、校验总长度/分片数/指纹时改用后备路径，否则报告真实传输阻塞。不能为每片重新遍历全树，也不得在正式设计上轮流试文件、缓存、PNG 和原始大文本。Phase 1W 与 Phase 6 分别记录采集、编码、传输、解码耗时。
- 调用 `use_figma` 的编排层须直接读取返回的 `image` content block；不要把 40 万字符级 base64 打印给模型。若使用 `functions.exec`，在同一次编排中保存结果或 `store`，再按不超过工具单次输入限制的约 48,000 字符分块写入本次运行目录的 `.b64` 传输文件，随后只返回块数量、长度与工具状态；再以 `--base64` 解码。实测把完整 base64 一次送给文件工具会超过 64 KB 审核上限。缺少 image block 时不要从原生视觉 screenshot 反推数据，也不要把 `figma.io.write` 的文件名误认为本地可访问路径。
- **不可丢失的编排样例。** 上轮独立测试的 `use_figma` 已返回完整 block，却只向模型输出 `dataLength`，执行单元结束后原始 block 丢失，故首次门禁失败。避免这种失败：在收到返回值后，先于 `text()`/`notify()`/映射摘要执行 `store('phase1w:'+runWorkspace, block.data)`。使用当前 Codex `functions.exec` 时，可在同一执行链将原始 base64 经 PTY 分块直接送到已有解码器（下面的 `runWorkspace`、`skillRoot`、`fileKey`、`description`、`code` 须换为本次值；不要打印 `block.data`）：

  ```js
  const r = await tools.mcp__codex_apps__figma_use_figma({fileKey, description, skillNames: 'figma-use', code});
  const block = r.content?.find(c => c.type === 'image' && c.mimeType === 'image/png');
  if (r.isError || !block?.data) throw Error('KVSS1 block missing');
  store('phase1w:' + runWorkspace, block.data); // 先持久化，再输出任何摘要
  const proc = await tools.exec_command({
    cmd: `python3 scripts/decode_theme_snapshot_png.py --stdin-base64-length ${block.data.length} /dev/null ${runWorkspace}/source-before.json`,
    workdir: skillRoot, tty: true, yield_time_ms: 1000, max_output_tokens: 1000
  });
  if (!proc.session_id) throw Error('snapshot decoder did not stay open');
  let session = proc.session_id;
  let done;
  for (let i = 0; i < block.data.length; i += 48000) {
    const reply = await tools.write_stdin({session_id: session, chars: block.data.slice(i, i + 48000), yield_time_ms: 1000, max_output_tokens: 1000});
    if (reply.exit_code !== undefined) {
      if (i + 48000 < block.data.length) throw Error('snapshot decoder exited early');
      done = reply;
      break;
    }
    session = reply.session_id ?? session;
  }
  for (let poll = 0; (!done || done.exit_code === undefined) && poll < 3; poll++) {
    done = await tools.write_stdin({session_id: session, chars: '', yield_time_ms: 5000, max_output_tokens: 1000});
  }
  if (done.exit_code !== 0) throw Error('snapshot decoder failed');
  text(JSON.stringify({snapshotSaved: true, bytesOfBase64: block.data.length, decoder: done.output}));
  ```

  若分块流送/工具调度失败，先用本次 `store` 的同一 block 恢复落盘，**不得**再次调用完整 Figma 采集。`--stdin-base64-length` 要求 PTY 并按长度读取，避免 shell 长参数和输出 40 万字符；解码成功后仍需核对 Figma 摘要中的根 ID、节点数、长度、校验和与本地快照。不要把 `store` 当作已落盘证据。
- `figma_source_preflight.js` 的绑定风险摘要是写入前的风险入口：逐组处理 Paint 色标、文字区间、局部样式/变量绑定，再冻结目标 `afterHash`。本技能交付固定色副本，因此颜色变量与 Paint/带颜色 Effect 样式必须在副本 UI 范围解绑，精确保护内容也只解除引用而保留当前显示色；新 KV 锁定子树保持直接使用，不解绑、不重着色；非颜色变量保持原样。不得通过修改共享变量或样式来换肤，也不得先试写再从截图发现颜色回弹。摘要有 `omittedBindingGroups>0` 或读取错误时定向补查，不能视为“无绑定”。

- 原稿未变化时，复用唯一完整快照中的视觉单元登记表、关系图、通道分类和灰度分析；颜色配方变化只重建本地目标投影，不回 Figma 重读。记录分析、唯一写入、最终证据传输和本地验收耗时。

- 普通换肤只传输一次完整原稿快照和一次完整最终副本快照；最终审查调用同时返回原稿不变指纹。中间不存在全树读回，截断结果不能冒充完整文件。
- Phase 2 只展示本地配色预览；用户选定后，所有场景在 `expectedClone` 上共同验证，不把任何候选或代表试色写进 Figma。
- Phase 6 将 `regionPlan` 仅作为离线归属清单，再汇总成单一 `writePlan`。可按代码预算在同一生成程序内部拆数组/函数，但 clone、detach、解绑与颜色操作必须由同一 `use_figma` 调用执行。任何生成器不得输出需要多次工具调用才能完成的普通路径。
 - `expectedClone` 由完整原稿快照和完整 `writePlan` 在本地投影，不需要先建立一个 Figma 副本基线。唯一写入调用开始时只核对原稿紧凑指纹；Phase 7 唯一终审调用传输完整副本快照并同时核对原稿指纹。投影失败或存在无法建模的结构副作用时，写入前报告阻塞，不能先改稿再探索。

- **写入能力预检。** 在 Phase 5 对冻结的 `writePlan` 执行 `python3 scripts/preflight_instance_writes.py source-before.json write-plan.json --out instance-preflight.json`。`vectorNetwork`/`vectorPaths` 的实例后代写入需列出全部实例祖先的解绑计划，并使用 `structural-fingerprint` 或已验证节点映射；未规划时脚本会返回失败。若通道只是 Fill setter 的派生镜像，计划把它标为读回验证，不调用实例内矢量数据 setter；验证仍需目标属性完整指纹。仅检查 `boundVariables` 键是否存在会误把空对象当成绑定，导致无意义的禁止 setter。任何无实际颜色/Alpha/绑定目标的操作都先删除再重投影。

- 大树传输先核对本次接口预算。本次实测 `use_figma.code` 上限 50,000 字符，返回文本约 20,500 字符会截断；生成器统一留到 45,000，后备文本分片使用至多 17,500 ASCII 字符。操作数预算之外还须检查包含 helper 的实际代码长度。颜色批次复用 `snapshot_fingerprint.js` 与 `figma_apply_color_diff.js`；生成 after 指纹前须把已声明目标 RGB(A) 规范为 Figma 原生 float32，避免 Fill 自动同步 Vector region 后因 double/float32 表达差异误报冲突，实际 before 仍精确保留。默认只传颜色叶子路径的原子 diff；Paint 类型、数量、顺序或渐变拓扑未变时，禁止用 `path:""` 重发完整 Paint 数组。只有结构本身属于已批准变更时才允许完整属性替换并记录原因。每项写入仍携带完整属性 before/after 指纹，在实际节点完整 Paint/Vector 数据副本上应用，不能把差异片段直接覆盖为完整 Paint。每项写入后**同次读取完整属性或文字区间**并核对 after 指纹；变量回弹立即返回冲突，不把“setter 没报错”当成功。Fill 引发的 Vector region 自动同步仅在完整 after 指纹吻合时作为完成项跳过，否则仍为冲突。

- 已有完整基准/精确目标模板时，可复用 `snapshot_fingerprint.js` / `snapshot_fingerprint.py` 减少读回传输：仍执行 `snapshotThemeTree` 全量真实采集，以 ID、父子顺序和全部属性的逐行指纹逐一核对；返回真实采集时间、错误、节点数、模板指纹与差异数。只有所有节点匹配且无错误、无缺失时，才可结合本地模板重建该次读回，并保留 live proof；不能只传声称 PASS，不能忽略差异/截断，不能给未重读的模板换时间戳。指纹是传输校验，不是视觉验收，也不是面向恶意输入的密码学证明。首次无完整基准时使用完整无损传输；`decode_snapshot_transport.py` 拒绝缺片、不一致和解码散列错误。禁止为每个小分片重复采集全树；若运行环境不能保留只读传输缓存，优先改善序列化或批量传输，并记录实际开销。
- `node-map.json` 由正式写入调用返回并在同次核对；可回收预演只使用临时映射，不为区域重新按名称或位置建图。
- 一张真实上下文截图可支持多条验收；彩色/灰度/模糊/缩略图均本地派生。所有最终截图在一次终审调用中按预登记节点取得，不每改一个角色就远程截图。
- **最终传输预算。** 实测同次写出两个 image block 时只交付第一块，合成一个约 1.1 MB 的二进制块也完全不交付，约 797 KB 的单张截图块同样不交付；只有约 318 KB 的快照块稳定收到。Phase 7 用 `python3 scripts/generate_figma_final_review_js.py <sourceId> <cloneId> <kvCloneId> <sourceFingerprint>` 取得单个 `KVSS1` 无损副本快照并用 `decode_theme_snapshot_png.py` 校验，再对持久正式副本调用 Figma 截图接口取得 1:1 整页 PNG。局部预登记场景从整页图本地裁取，源稿图沿用 Phase 1。两种证据均按实际到达、解码与哈希校验后才可判视觉 PASS；不能从返回 JSON 的字节数推断文件可用。
- 一次最终新鲜读回同时重验全部共享场景、覆盖和保护检查；不能为每个检查单独重新取全树。

- 场景指纹按 Figma 数值语义规范化 JSON 中等值的 `1/1.0` 和 `0/-0.0`，避免格式差异误报过期；布尔值与数值仍区分，真实数值变化不放宽。`stateHashVersion=2` 闸门沿用真实审查时间和证据，不重写历史时间。升级旧格式门禁时，保留旧文件，仅使用已有完整状态和同一实际 review 重新计算指纹；没有这两份真实证据时重新读取/审查，不能直接把 stale 改成 pass。
- 分别记录完整基线、每次可回收预演的启动/截图/清理、一次正式写入和一次集中终审的真实起止时间、节点/操作/字节数、清理结果与审批原因；轻量配色提案读取另列，不得混入基线传输数。默认完整原稿基线传输为 `1`，每次预演取得一个临时副本紧凑指纹和 1:1 截图，正式交付写入调用数为 `1`，最终副本完整快照传输为 `1`，另取一张整页截图。预演中的指纹复核不冒充新的基线传输；实际工具调用数必须如实披露。

```sh
python3 scripts/split_region_plan.py region-plan.json
python3 scripts/generate_figma_region_js.py region-plan-part-0.json
python3 scripts/generate_figma_region_batch_js.py region-a.json region-b.json
python3 scripts/render_views.py whole-page.png region-views --regions pixel-regions.json
```

`pixel-regions.json` 为 `{sceneId:[x,y,width,height]}`，坐标是截图像素，必须从实际设计边界和截图比例换算；包含真实宿主及邻近比较控件，禁止低分辨率放大冒充 1:1。局部视图保存原截图指纹与裁切边界，裁切不代表新 Figma 渲染。

前三条命令仅生成待审查执行代码，不调用 Figma 或授予权限。operations 使用 clone ID、完整属性 before/after 指纹及原子 diff，来源是统一计划；相互依赖的 Paint 操作不得拆散，重复/重叠操作先合并，单操作超限不得截断。execution_audit.py batch-plan 的离线格式不直接作为 Figma 区域输入。

## 6. 阶段产物与通过条件

### Phase 0：解析与初始化

#### 必须执行

- 解析唯一目标 Frame、新 KV 完整视觉单元及旧 KV 载体/图片 Paint；先判定 `single-image|composite-kv`，复合 KV 不得降格为某个内层 IMAGE。
- 确认可用 Figma 写入与截图能力。
- 用 `scripts/run_workspace.py init` 创建唯一临时 `runWorkspace`；所有任务级证据只写入该目录，不读取历史任务文件猜测当前输入。
- 初始化四个执行产物及 `mutationPlan.executionPhaseLog`；若为恢复任务，先读取既有 runId、副本、快照、批次和门禁记录，不创建第二份副本。

#### 通过条件

目标、新 KV 完整视觉单元、旧 KV 载体/Paint 均唯一且可访问；否则在任何写入前停止。

### Phase 1：只读原稿审计（1P 提案门禁 + 1W 写入门禁）

Phase 1 分为两个只读门禁。Phase 1P 在 Phase 2 前完成，只收集生成可靠配色提案所需的最小证据；用户选色后返回 Phase 1W，完整执行《Figma 执行规范》的检查与快照要求。Phase 1W 通过前禁止进入 Phase 3、复制页面、替换 KV 或写 UI。

#### Phase 1P 必须产出 `sourceAudit.proposalBasis`

- 唯一目标 UI 与新 KV 完整视觉单元的 ID、类型、尺寸、顶层关系，以及原 UI/新 KV 各一张真实截图；不截图 PAGE。
- `sourceUiMode`、页面/卡片/容器/普通 Icon 底托/选中 Tab/主要按钮与 CTA 的原始显著性顺序和业务优先级；只读精简代表，不枚举所有实例。
- 原 UI Hero 与新 KV 的画风比较、旧 Hero 可见下缘与新 KV 可见下缘证据；能判断普通换肤或是否需要进一步检查画风迁移。
- 影响提案的保护风险摘要：Hero 功能入口、媒体、前三名和独立营销 Banner 是否存在。此时只定位风险范围，不建立最终节点白名单。

#### Phase 1P 通过条件

目标与新 KV 唯一；截图可读；`sourceUiMode`、显著性骨架、画风差异和接缝证据足以支持 Phase 2。缺失时只定向补读相应区域，不回传全树。通过后允许进入只读 Phase 2，但不表示完整原稿审计通过。

#### Phase 1W 必须产出完整 `sourceAudit`

- 原稿结构快照、所有 Paint/Effect/IMAGE 分类、`paintPresenceMask` 与第 5.2 节全量颜色通道清单；全部通道分类完成，不留未知角色。
- 可先用 `scripts/source_channel_triage.py <source-before.json> --region-depth 2 --out <triage.json>` 把同一次快照中的有效通道按真实节点、祖先和区域汇成审查索引；该输出固定为 `review-index-only`，仅帮助逐层定位，不能充当语义分类、保护判定或 Phase 1W 通过证据。分类后仍以完整 `colorManifest` 的逐路径覆盖差集为门禁；`unknown/unclassified/pending/todo/tbd` 等占位角色即使路径齐全也必须失败。
- 大页用 `python3 scripts/visual_unit_review_workbench.py <source-before.json> <source-native.png> --out-dir <runWorkspace>/review-workbench` 生成只读本地审查页；已有局部 `decision-report.json` 时加 `--decision-report` 仅显示 `unresolvedPaths`。它把原生整页图、位置框、视觉单元层级、具体节点、文字、IMAGE/mask 提示及逐条颜色路径并排显示，输出 `review-units.json`、按区域排列的 `review-queue.md` 和候选精确选择器/命中哈希；候选若碰到已审路径则不提供可直接追加的规则，并列出重叠差集。页面里的框仅辅助找位置，导入组件可能有特殊局部坐标，必须对照原生图核对。按 `review-queue.md` 从上到下逐组审完整成员与例外，累计人工决策后重新运行展开器；只有 `unresolvedPaths=[]` 才结束这一步。展开器的同旧 RGB 大组若跨场景，改从工作台的场景/单元组审，**不要因 153 条等大组跨语义就停止，也不要整组套色**。工作台不推断语义/配方/保护，不输出 manifest 或 PASS；看完每个组的**全部节点与例外**后，才把合适的规则手动写入 `decisions.json`，并用展开器复核完整命中集合。更改 `--unit-depth` 只改变审查分组，不改变通道门禁。
- 对有大量重复实例的页面，用 `scripts/expand_channel_decisions.py <source-before.json> <decisions.json> --out <decision-report.json> --out-manifest <color-manifest.json>` 安全展开人工审核的规则表。初次可让 `rules:[]`，先看报告 `suggestedGroups` 按旧 RGB＋节点类型折叠的所有路径和上下文；它是审查索引，不会自动选角色。`decisions.json` 须有 `schemaVersion:1`、本次完整快照的 `sourceHash` 和 `rules`；每条规则写 `id`、`selector`、`role`、`disposition`、`reason`、`ruleId`，换色再写 `recipeId`、`sceneId`、`target`（`#RRGGBB` 或 RGB）。选择器可按精确 `path`/`nodeId`/`subtreeId`，或合取 `nodeType`、`name`、`sourceHex`、`channelKind` 限定；不允许无条件根子树兜底。命中多于一条有效通道的规则必须先看报告中**全部** `matchedPaths`，再填入对应的 `reviewedPathsHash`，不得只复制哈希而不审查成员。交叉命中默认冲突；精确 `path` 例外须声明 `overrides:[原规则 id]`。工具自动列出未覆盖/冲突/可编辑操作被保护的风险，以及逐文字区间和 Vector/Boolean/Ellipse 的待审清单；`needs-review` 时不会输出可用 manifest。`ready-for-semantic-review` 只表示机器全通道覆盖和规则一致，不等于 Phase 1W PASS；仍须逐卡确认标题/Icon 本体、保护、真实宿主、材质、状态、视觉单元、对比关系和截图。相同源 RGB 不能脱离上下文全局绑定一个角色。
- 同一冻结快照运行 `python3 scripts/surface_system_audit.py discover <source-before.json>`，审核其全部可见非文字 Fill 和裁切边候选，建立《表面系统硬门禁》规定的 `surfaceSystemPlan`。尺寸只是理解结构的证据，不是候选过滤条件；每张已确认卡片下的所有可见非文字 Fill 都须先分类，再由真实职责决定容器、交互、图标或装饰门禁。收益卡、任务卡、作品卡等同源同级稳定底板必须在写入前成组；不能等看到目标稿偏色后再决定是否同族。发现列表中的节点和裁切线不得省略。
- 全部小按钮、大按钮、状态和卡片氛围的 `layerStacks`，按实际层级区分基底、反射、罩染、塑形暗部、蒙版和位图；不能只读取单层颜色。
- 语义组件到真实 `visualSurfaceCarrier` 的映射。
- 每张卡片的 `titlePaintInventory` 与 `iconGlyphInventory`：标题逐 TEXT/文字区间列出全部可见 Fill、渐变色标、Stroke、颜色 Effect 与相关标题装饰；Icon 逐图形子节点列出 Vector/Boolean/IMAGE Paint、材质层与底托，明确 `glyph`、`container`、`protected` 或 `raster-blocked`。视觉上的标题或 Icon 不得仅因其父容器、光晕或底托已登记就算完成本体清点。
- `sourceAudit.textRangeInventory`：逐个可见 TEXT 保存 `getStyledTextSegments(...).fills` 的完整起止范围和全部颜色通道；同节点多个颜色、数字/链接/说明混排不得压成一个节点级颜色。精确保护记录到区间，封面外文字不得继承媒体卡祖先保护。
- 第 4.8 节的 `visualUnits`：完整结构到全部实际颜色承载层、宿主/叠层依赖与审核根的登记表，与全量通道清单逐项对照；深层列表/裁切 Frame 不能漏掉。
- `sourceColorRelations`：需保持的等价实例同色通道与连续同色表面，包含精确颜色通道和角色/材质/状态依据；按《颜色决策规则》第 9 节建立，不仅凭旧 RGB 或共享 Style/Variable 强制跨角色同色。所有非保护角色仍按新 KV 换色，变体在写入前明确。
- 组件实例、复合异形表面、卡片氛围层、KV 衔接信息带、Tab 状态、媒体保护区、前三名颜色保护清单与独立营销 Banner 整棵保护清单；Hero 外框、旧图偏移、祖先裁切/蒙版链及可见安全窗口。营销 Banner 须以构图/语义证据区分于普通业务卡，并从写色和残留清理目标中排除。
- 按《验收规则》第 5.1 节建立全实例对应的 `contrastRelationships` 与实际合成基线。
- 原稿整页及关键区域的真实灰度证据，以及 `sourceSalienceMap`、`sourceLuminanceTopology` 与不含目标色的 `semanticPriorityMap`；明确页面、卡片、文字、数字、Icon、Tab 和操作的原有优先级。
- 前置 `themeDecision.kvStyleComparison`：先读取新旧 KV，比较材质、体积、插画方式、线条和纹理，记录差异为轻微/明显/证据不足；再核对原 UI 的冲突节点。仅颜色或 IP 改变不触发迁移，明显画风变化也不等于全页重做。

有效通道超过 100 条时，第一份工作台队列就用 `--max-unit-channels 25 --merge-channel-kinds`，按本轮剩余路径数量自适应选更深的树节点，并把同单元、同旧 RGB、同节点类型的 Paint/文字区间/矢量镜像等放在同一审查卡。审子单元时仍须复核父卡叠层、标题/Icon、状态和新 KV 宿主；跨类组标 `crossKind`，必须逐类确认是否真同一视觉职责，渐变端点/描边/镜像若角色不同就手动拆成更窄规则。固定 `--unit-depth` 仅用于补充查看其他层级上下文。候选 hash 不能代替审查；两个参数均不改变 `sourceHash`、颜色覆盖清单或保护边界。

#### Phase 1W 通过条件

页面背景、卡片、容器、普通文字、标题、关键数据、Icon、标签、Tab、小按钮和 CTA 中实际存在的角色均已识别；新旧 KV 画风比较及原 UI 冲突检查已完成，普通换肤或局部画风迁移已确定。不允许边写边第一次判断角色。Phase 1W 可复用 Phase 1P 的截图与稳定结论，但必须补齐完整快照、全通道、逐实例材质、保护清单、视觉单元、同色关系和对比度基线。

标题和 Icon 的可见 Paint 清单若有未分类层，Phase 1W 不通过。`raster-blocked` 是明确素材限制，不能写成 `protected` 或完成；也不授权叠加替代图形。

### Phase 2：新 KV 分析

完整执行《KV 色彩分析》，本阶段禁止修改 Figma。

#### 必须产出

- `visualIntentProfile`、颜色角色、环境/主体/材质/高光证据。
- `adaptationMode=color-only/style-adaptation` 及画风差异证据；启用画风迁移时记录 `visualLanguage` 的体积、材质、光影、边缘与纹理证据及角色分配，不默认手绘或任何特定画风。
- `sourceKvTone/sourceUiMode/targetKvTone`、`requestedUiMode`，以及 `source/targetHeroEdgeTone`、`candidateTargetUiModes/candidateSurfaceDepths`；半透明卡按实际合成表面判断 UI 模式，不从 KV 深浅或 Paint Alpha 直接推断。
- `uiContinuationPalette`、`highlightOnlyColors`、光照方向与材质空间模式；在既有 `kvAnalysis` 内保留有真实像素/区域依据的 `colorAnchors`，区分稳定环境、环境光、主体与反光。主体或标题存在明确金属视觉时，另登记 `metalAccentEvidence` 的来源区域、金属家族、稳定本色/中间调/暗部/高光/环境反射、显著性与可信度；没有时明确为 `null`，不能由色名或题材补造。多个环境候选须记录环境身份、连续面积/横向覆盖、空间稳定性、实际可见 Hero 下缘接触、纹理具体程度、前景风险和延展适合度。另生成 `heroBottomExtensionDecision`：底部杂乱或由局部前景主导时排除；大片环境纯色或低纹理渐变时列为强候选，再与整张 KV 的大范围环境锚点比较。记录 `selected-solid|selected-gradient|eligible-not-selected|not-suitable|existing-transition`、采样区域、代表色/渐变、覆盖率、空间身份、是否采用、理由和衔接证据，不能只写主观结论。
- 在生成 Hex 前，继承 Phase 1 的显著性与业务优先级证据，并按《颜色决策规则》第 3.0–4 节为每套候选依次冻结 `surfaceFamilyPlan`、`targetSalienceOrder / roleLightnessPlan / targetLuminanceTopology`、`controlColorSalienceOrder=icon-container < selected-tab < primary-button` 与 `colorClarityPlan.lightnessAndChroma`；同一模式的同色系/撞色方案默认共用表面家族和明度拓扑，撞色不扩散到大面积表面。浅色 UI 须明确页面有彩且不近白，并为卡片冻结 `cardSurfaceStrategy=tinted-near-white|pure-white-atmosphere`：撞色方案优先降低卡片 S、提高明度，必要时使用纯白稳定底且只让原有顶部氛围保留淡主题色；容器层级仍可辨；主要按钮/CTA 记录 `buttonToneDirection=bright|clean-deep`，偏浅宿主上的干净深色必须有 KV/金属证据并比明亮候选形成更清楚分离。功能 Icon 图形须清楚并有独立 `icon` 锚点；同时冻结 `iconPairPlan`，联合说明卡片宿主、底托与图形的 H/S/B 方向。普通鲜亮 Icon 的稳定主体色标可为 `B=100`，不得据此单独判过亮；原可见渐变逐 stop 保留低/高饱和或明度职责，不能把全部 stop 复制为同一稳定主体 Hex；普通 Icon 底托只淡淡带色但在 1:1 下必须与卡片可辨，选中 Tab 比底托明显，主要按钮/CTA 再明显一层，且底托与 Tab 都不暗沉。
- 在生成 Hex 前为每套候选冻结 `accentFamilyPlan`：普通功能 Icon 的稳定主体从背景/卡片连续环境家族提取；深色 UI 的高亮数字代表 `number` 与 `icon` 锚点使用同一 Hex，按钮可成为第二高彩家族。浅色 UI 的数字可另选，但默认不形成第三高彩家族；有证据的例外按《配色方案提案》登记，局部金属反射不算稳定主体。
- 按《配色方案提案》从锚点整理 3–5 个来源色、`kvPrimaryHue`、`metalAccentEvidence` 及表面撞色基准 `surfaceContrastBasis`。先比较可行背景方向，保留基础模式/交互覆盖并补充背景备选，数量按《配色方案提案》第 3 节；无可靠金属证据时覆盖同色系/撞色方向；撞色先比较约 180° 对向色与 KV 中有证据的高彩高明度色，再明确 `contrastDerivation=hue-opposition|kv-vivid-accent`；有可靠金属证据时覆盖 `metallic-analogous / gold-bright / clean-deep` 三个按钮方向，并展示有依据的背景备选。正常明亮金色优先落在规定的暖亮金范围，主体中间调呈现金黄、高明度和有效彩度，不得用暗铜、棕橙或土黄替代，并默认规划深棕按钮字。缺少用户要求方案类型的必要基准时先处理输入阻塞，不伪造或静默减量。内部保留完整门禁与角色方向，面向用户只展示 `background/card/number/icon/button/tab` 六色投影；逐套完成 `proposalColorPreflight` 和面积化预览复核，只把全部通过的方案写入 `themeDecision.paletteProposal`。本阶段不复制页面、不替换 KV、不写 UI。

#### 通过条件

旧/新 KV tone 与原 UI mode 均有独立证据；新 KV 深浅由稳定环境场、暗部连续性、接缝、主体曝光性质和整页灰度共同支持，不由 KV 底部或中央高光单独决定。主表面锚点已按环境身份、连续面积、稳定性、实际接缝和延展适合度比较；底部只在满足可见、连续、面积、纯度/稳定性与环境身份条件时作为延伸依据。方案数量和角色内容符合《配色方案提案》，且每套均有来源锚点、单一表面家族、目标显著性顺序、明度拓扑、彩度/受光目标、代表 Hex、角色映射、风险说明及 `proposalColorPreflight=pass`。浅色 UI 另须正向证明页面背景明亮且保留主题彩度、卡片按 `cardSurfaceStrategy` 成为低彩近白或纯白稳定面、顶部氛围没有污染整张卡片、内部层级清楚；主要操作为明亮有彩，或为在偏浅宿主上更清楚且有来源证据的干净深色，二者都不得灰闷、近黑或只靠局部高光。普通 Icon 底托、选中 Tab、主要按钮/CTA 的颜色显著性依次增强；Icon 图形与底托成组后没有底托偏重、渐变塌缩成纯色或整页重复抢焦点；底托与 Tab 淡淡带色且不暗沉，三者不能近似或倒置。任何表面跨家族、暗沉、灰闷、只靠局部高光成立或大面积色相过多的方案不得进入用户选择。尚未得到用户选择时状态为 `awaiting-user-palette-choice`，在此处暂停后续写入。

每套还须通过 `accent-family-economy`：`accentFamilyPlan` 与六个公开锚点相符，Icon 主体有连续背景环境来源；深色方案的 `number==icon` Hex 精确相等，二者在各自宿主均清楚；不能用宽泛的“同属冷色/蓝色”标签放行第三种肉眼割裂的亮色。

### Phase 3：已选方案的换肤预检

完整执行《颜色决策规则》，形成 `themeDecision`。

#### 必须产出

- 进入本阶段前确认 Phase 1W 完整写入门禁已通过；只有 Phase 1P 或配色提案证据时不得继续。
- 进入本阶段前确认用户已从 Phase 2 展示的 `themeDecision.paletteProposal` 中明确选择方案，并记录 `paletteSelection.status=selected`、方案 ID、原始指令和选择时间；用户未选择时仍停留在 Phase 2，不得开始本 Phase 的配方冻结或任何 Figma 写入。
- 继承 Phase 1 的 `semanticPriorityMap` 以及 Phase 2 已通过的 `surfaceFamilyPlan`、`targetSalienceOrder / roleLightnessPlan / targetLuminanceTopology` 与 `colorClarityPlan.lightnessAndChroma`，把用户选定的关系色板展开为具体颜色配方。`targetUiMode` 和 `hueStrategy` 必须与选定方案一致，不由 AI 在预检中偷偷换成另一套；若逐层展开暴露冲突，退回 Phase 2 修正并重新展示，不得静默降低明快感或改换表面家族。
- 冻结用户选中方案的 `schemeAnchorContract: background/card/number/icon/button/tab`、`cardSurfaceStrategy` 与 `iconPairPlan`，再展开表面、卡片氛围、文字阶梯、标题、关键数据、Icon 图形与底托、标签、Tab、小按钮和 CTA 的 Paint Recipe。六个锚点各自至少绑定一个稳定可见 `anchorId` 通道，目标 RGB 与公开方案完全一致；表面由 `surfaceFamilyPlan` 引用 KV 锚点并明确家族/层级，关键数字引用 `number`，功能 Icon 图形引用或有依据地派生自 `icon`，主要小按钮与 CTA 的稳定主体共同引用 `button`，Tab 选中态引用 `tab`。Tab 不得因执行方便改绑按钮/Icon 色。存在底托时记录颜色来源与承托关系，并把 `controlColorSalienceOrder=icon-container < selected-tab < primary-button` 写入 `hierarchy` acceptance、场景配方依赖和可比较的 `emphasisOrders`；这个顺序按最终合成存在感验收，不转成单一数值递增公式。按《颜色决策规则》第 3.0 节冻结 `hueRelationshipPlan`；撞色另冻结 `contrastDerivation`、使用的 `metalAccentEvidence` 或 `surfaceContrastBasis`、`buttonToneDirection`、面积主次及可见反差，并写进 `theme-consistency` 的 acceptance 和场景配方依赖，不能只登记“各角色都来自 KV”。
- 全量 `colorManifest` 的语义、保护和目标已逐路径审核后，使用 `python3 scripts/compile_color_mutation_plan.py <source-before.json> <kv-source.json> <color-manifest.json> <compiler-options.json> --out-dir <runWorkspace>/compiled`，生成 `expectedClone.json`、`writePlan.json`、`policy.json`、`nodeMap.json`。`compiler-options.json` 写 `schemaVersion:1`、本次 manifest 的 `sourceHash`、完整 KV 根 `kvSourceId`、选定 `schemeId` 和现场 `sourceFingerprint`；按实际证据显式列 `detachInstanceIds`、`opacityOps`（节点或现有 Fill Paint 的 `sourceId/property/before/after/reason`，Fill 另给 `paintIndex`）、`textPaintAlphaOps`（`sourceId/start/end/paintIndex/before/after/reason`）及精确 `protectedPaths`。节点 `opacityOps.path` 由编译器从唯一源树派生，输入可不写；若显式写入则必须与派生路径完全相同。`before` 必填并精确匹配原属性。没有证据的 Alpha/解绑例外留空，编译器不会自动猜。它只对已审核 RGB 和允许的绑定/Alpha 改动生成 setter 与离线投影，检查完整通道覆盖、原稿/KV 匹配、颜色绑定清除、矢量镜像、实例能力和写入代码预算；不生成或替代 `ruleLedger`、`visualUnits`、`colorRelations`、`materialRelations`、Icon/文字宿主及 1:1 视觉结论。若报告不支持的 Effect、颜色 Alpha、混合文本或超预算，保持未通过并处理能力缺口，不能改写 `expectedClone` 伪造通过。
- 对 `titlePaintInventory` 与 `iconGlyphInventory` 的每个非保护、可编辑可见通道逐一给出目标 Paint Recipe 与写入路径；标题多层渐变按层保留空间结构，Icon 图形与底托分别定目标。每张卡片的 `titleGlyphCoverage` 必须列出 `planned / protected / raster-blocked` 的完整差集与证据；任何未计划通道或把 `raster-blocked` 计为已换色，Phase 3 不通过。
- 生成 `textRangePlan`，严格镜像 `sourceAudit.textRangeInventory` 的全部区间；每段绑定颜色清单路径、处理结论、真实宿主和对比关系。跨深浅模式的可见非保护文字关系须有 `minimumContrast >= 3` 的内部机器底线并进入 `readability` 范围；它只防止接近消失，不替代角色化 1:1 视觉判断。
- 在冻结账本前，从 `themeTransition` 确认 `contrast-baseline.verifier.policy/decisionContext`：深→浅/浅→深必须 contextual，context 内模式与过渡一致且有真实宿主/职责原因；同模式纯换色用 source-baseline。`freeze_rule_ledger.py` 和静态预检都拒绝错配，避免预演后才发现对比策略无效。复杂渐变文字不能取抗锯齿字形边缘像素当纯色前景；用真实属性合成可证明的色标/宿主或保留明确未验证项。
- 对 Hero 建立旧 IMAGE 载体清单：含根层和嵌套实例的旧 KV，逐个核对绝对边界、祖先裁切、新 KV 实际高度/宽度与叠放顺序。新图比旧图短时，须在计划里显式视觉移除可能露出的精确旧图节点并纳入静态投影/预演读回；仅给新图置顶不是遮挡证明。对每张卡分别核对大面积非文字 Vector/Boolean 的真实宿主职责、内层容器合成色，以及超出标题栏的装饰蒙版；原稿已有的子标题底板不因视觉浅带被误删。
- `sourceUiMode != targetUiMode` 时生成 `crossModeCompositePlan`：从完整清单自动枚举有效 Alpha、全部文字区间、卡片氛围与渐变色标，逐项区分外观重算、视觉移除、状态保留或结构保留；渐变/氛围节点另列 `boundaryGroups` 和真实宿主 1:1 场景。不得把旧 Alpha 百分比直接作为目标或靠整页缩略图证明接缝连续。
- 同时继承所选方案的 `accentFamilyPlan` 到 Icon/数字/按钮配方及 `theme-consistency` acceptance；不得因金属梯度或组件变体，在已确认的六色锚点之外另设稳定高亮 Icon 主体。
- 扩展 `colorClarityPlan`：保留 Phase 2 已确认的彩度、感知明度与受光目标，补充第 3.2 节浅→浅比较基线的适用性、最终是否沿用及精确通道、逐角色对比关系和渲染检查方法；用户授权参考设计师版本时，包含同角色参考研究与可迁移范围。不得把“后续会加材质”作为压暗当前主体色或放行灰闷方案的理由。
- 按钮背景与浅/深文字的组合候选及真实背景对比度计划：先按 KV 来源、彩度/明度、面积及宿主效果标记特别鲜艳的无金属撞色按钮 `buttonTextPriority=vivid-contrast-white`，这类按钮先以白/近白字提案和 1:1 试色，小按钮与 CTA 共用方向；白字在真实文字覆盖区对比度不足时再试深字，登记白字截图、采样、原因及最终选择依据。其他按钮用 `buttonTextPriority=contextual`，依据材质、实际宿主与可读性选择浅字或深字并记录依据，不强制白字起步。`gold-bright` 仍默认验证深棕字，不得为白字压暗金色；预览脚本不得把特别鲜艳撞色的白字仅因深字静态比值较高而自动替换。
- 六色锚点必须在审过的决策规则中以 `anchorId` 标到稳定可见换色通道；单一载体用精确 `selector.path`，多处同职责载体可用已核对全部命中路径并冻结哈希的有界规则。`expand_channel_decisions.py` 将标记传入 manifest；选色契约、规则和实际目标 RGB 三者必须一致，不能在展开后临时给随机条目补锚点来消除静态报错。
- 画风迁移时，`styleAdaptationPlan` 须包含原形状家族、风格载体、逐属性允许差异与裁切安全范围。
- 第 5.1 节 `ruleLedger`、全量 `colorManifest` 分类和覆盖差集校验通过；规则清单及目标在任何 UI 写入前冻结，场景引用同一指纹。
- 冻结 `visualUnits`、同色关系及对应对比关系；可比较的同宿主强弱顺序进入 `emphasisOrders`。整组配方的计划快照先通过关系预检，普通写入与局部修正继承同一套约束。
- `preflightThemeDecision=pass`，并绑定 `paletteSelection.schemeId` 与所选方案指纹。

#### 通过条件

用户已明确选定一个方案；六色 `schemeAnchorContract`、来源锚点、模式、表面与交互关系完整，六个 `anchorId` 的目标值已通过机器预检，CTA 和主要操作拥有正确显著性；色相不由题材或材质标签机械推出，旧 UI 色相未进入新方案。背景、卡片、主要按钮/CTA 的色相关系满足第 3.0 节。无金属 `contrast` 方案须有可靠 `surfaceContrastBasis`、两类候选的取舍证据，并与 `contrastDerivation=hue-opposition|kv-vivid-accent` 一致；金属方案须有可靠 `metalAccentEvidence` 并标明 `buttonVariant`。选择 `gold-bright` 时，实际按钮主体中间调必须保持正常明亮金黄、高彩度与清楚受光，不得落成暗铜、棕橙、土黄或由窄高光勉强显金，并已用深棕字作为默认方向验证。功能 Icon 图形引用 `icon`，小按钮与 CTA 共同引用 `button`，Tab 引用表面同系 `tab`，普通 Icon 底托与二者共同满足 `icon-container < selected-tab < primary-button`；缺任一关系不得通过。

`accentFamilyPlan` 必须与已选六色及各角色稳定主体相符；Icon 无连续背景环境来源，或深色 UI 的 `number` 与 `icon` 锚点 Hex 不同，均不得通过。公开锚点若本身违反该计划，应回 Phase 2 重新展示并确认，不能在 Phase 3 偷改。

### Phase 4：生成完整写入计划（本地，不改 Figma）

从唯一原稿快照投影 clone、KV 适配、必要实例解绑、颜色绑定解除、节点映射和全部目标 Paint。产出一个 `mutationPlan.writePlan`，其中每个操作都有源路径、目标路径推导、before、after、保护/排除规则和失败条件。`regionPlan` 只用于证明页面内每个视觉区域与颜色通道恰有归属，不拆成多次写入。

必须同时冻结 `kvFitPlan`、`kvLockedSubtreeRootIds`、`reviewScenes`、`iconGlyphPlan`、`materialRelationPlan`、全部表面/容器关系、状态 `stateGroupId` 与完整 `emphasisOrders`。映射未确认的可见 Paint 保持阻塞，不用 `decoration` 兜底。

#### 通过条件

`writePlan` 能从原稿快照确定性生成 `expectedClone`；保护范围与写集无交集；KV 锁定子树无写入；所有结构与颜色副作用均已建模。无需、也禁止先创建 Figma 副本基线。

### Phase 5：离线投影与可回收原生预演全量预检

本节首轮机器命令必须使用 `--stage static`，只接受 `ready-for-preview`；截图落盘后补齐 `contrastSamples`，第二轮使用 `--stage full` 并取得 `pass`。静态结果不是完整通过。

对 `expectedClone` 运行与最终审计相同的机器检查，包括结构许可、颜色覆盖、Icon 图形逐路径覆盖、材质角色组、文字区间、颜色绑定清零、合成表面对比、状态组强弱顺序、六色锚点和残留色。再用原稿整页/局部截图与本地渲染预览检查页面、卡片、内部容器、Icon、Tab、按钮、CTA 和状态关系。

把新鲜原稿、目标投影、颜色清单、写入计划、白名单、冻结规则、视觉单元、颜色/对比度/材质关系及节点映射的文件路径写入本次运行的 `preflight-spec.json`；执行 `python3 scripts/preflight_full.py preflight-spec.json --out preflight-machine.json`。脚本逐项运行机器门禁，包括 `preflight_instance_writes.py` 的实例 setter 能力检查，以及 `derive_vector_mirrors.py` 的同节点 Fill/Stroke→`vectorNetwork` 来源/目标精确镜像关系，并输出具体 `failedChecks`。派生矢量路径虽不直接写，预演与终审仍必须逐路径读回目标值。只看 `coverage=pass` 或手写总状态不算预检。冻结计划先通过不依赖预览像素的静态检查，再执行第 2 节的可回收整页预演；拿到 1:1 PNG 后补齐合成与文字采样，重跑完整机器门禁，并以真实尺寸预览独立记录 KV 接缝、卡片内外表面、Icon、按钮字、禁用状态、媒体标签及整页层级的人工视觉结论。特别核对拟写 `vectorNetwork/vectorPaths` 的实例祖先与空绑定造成的无效 setter。机器或视觉任一失败时，不创建**正式** Figma 副本。

大面积浅色内部容器不能只因为 Fill 不是同一个 Hex 就通过；必须按最终 Alpha 合成色满足冻结的 `minimumDeltaE` 并在 1:1 预览中边界清楚。功能 Icon 不能只通过“渐变仍存在”或“至少有两个颜色”；重复金属色标的源角色组必须保持。状态组件不能只抽查一个节点；同一 `stateGroupId` 的所有非等强源关系都必须存在于 `emphasisOrders`。

#### 通过条件

`offlinePreflight=pass`，`instance-preflight=pass`，`stagedPreview.cleanup.status=pass` 且整页预演验收通过，没有未分类通道、未映射节点、未解释保护、关系塌缩、残留旧主题色或 UNKNOWN。每个 PASS 必须指向实际执行的检查结果或已查看的原生预览；不得把自写摘要、六色静态对比度和通道覆盖率当成以上门禁的替身。任何失败只修改本地计划/配方、重新投影并重做可回收预演，不创建或修改正式副本。

#### 审核计划编排工具（不替代原生预演）

完整颜色 manifest 后，可先用 `scripts/generate_visual_unit_declarations.py <source> <workbench/review-units.json> --out <draft>` 提取同源工作台的唯一单元根，得到 `status:needs-review` 且 basis/规则范围为空的模板；它**不能直接**作为已审证据。人工核对/合并/拆分单元，补每个根的实际截图/层级 basis、受影响兄弟/宿主依赖和视觉规则 ID 后，再用 `scripts/compile_visual_unit_registry.py <source> <manifest> <reviewed-units.json> --out-registry ... --out-report ...` 展开全部存储通道的精确单一归属；过宽或漏根会失败。`reviewed-units.json` 为 `{schemaVersion:1,sourceHash,units:[{id,rootNodeId,basis,reviewRuleIds,extraDependencyNodeIds,reviewNodeIds?}]}`。隐藏通道也必须归属，不自动获得写入权限。

再用 `scripts/prepare_semantic_preflight.py <source> <manifest> <reviewed-choices.json> --out-dir ...`，在显式提供功能 Icon 根/中性保留证据、媒体保护根、50% 禁用根、旧图移除根、状态根、跨模式接缝根、`surfaceSystemPlan` 和上述 reviewed units 后，组合现有 Icon、文字区间和跨模式派生工具，产出待冻结 manifest、视觉单元及文字对比关系。选择文件包含 `iconRootIds/neutralIconEvidence/mediaCoverIds/disabledRootIds/hiddenRootIds/stateRootIds/boundaryRootIds/surfaceSystemPlan/visualUnits`；没有证据的列表必须留空并触发不适用/缺项审核，不得填页面根充数。派生的宿主和关系只构成预览与取样义务，不证明真实像素可读。

`scripts/freeze_rule_ledger.py template --out <draft>` 建全量规则索引；人工填写每条适用性、来源、验收条件、视觉范围、对比与同色 verifier。`freeze` 子命令在账本与 visualUnits、Icon、文字宿主、颜色关系哈希吻合后才把账本 hash 绑定 manifest。它的 `ready-for-static-preflight` 不是机器预检结果。最后仍须运行 `preflight_full.py --stage static`，只有其实际 `ready-for-preview` 才允许可回收整页预演；全量原生场景、采样和独立视觉判断不可由这三个编排工具代替。

### Phase 6：唯一批量写入

只执行一个 `use_figma` 写入调用。程序先核对原稿指纹，再依次 clone、KV 放置/锁定、必要解绑与颜色绑定解除、应用 `writePlan` 全部原子操作，并在同一调用内返回每个操作的完成/冲突状态、最终副本 ID、映射和紧凑指纹。禁止以坐标、名称、面积或旧色相临场发现并追加写入。

#### 通过条件

调用完整成功，`completedOperations == plannedOperations`，没有冲突、漏项、白名单外修改或 KV 锁定子树命中。若部分失败，任务保持未完成并保留恢复证据；不得自动发起第二次写入。

### Phase 7：最终审计

一次 `use_figma` 调用取得原稿不变指纹和完整副本 `KVSS1` 快照，另用 Figma 截图接口取得同一副本的 1:1 整页 PNG；两份文件落盘校验后，本地裁取全部预登记细节。随后完整执行[《验收规则》](validation.md)第 1–10 节，逐项填写第 11 节的唯一闸门清单并生成 `finalAudit`。不得为不同检查重复读取整树或逐卡远程截图。

本阶段必须覆盖原稿/副本结构、KV 适配、全部精确保护、文字与状态、真实合成材质、全 Paint/IMAGE 与渲染残留、逐实例上下文，以及完整五种本地派生视图和整页累计显著性。核对真实副本与 `expectedClone`、`regionPlan` 全覆盖和跨区同族一致性；不得有待更新实例、待恢复操作或未解决冲突。

任一失败都记录未完成状态及精确节点、通道、关系和截图证据，不沿用投影 PASS 覆盖真实失败。在已确认方案和原授权范围内继续有界修复：复用已校验基线，冻结修复计划，重算影响闭包，使旧证据失效，重新投影/预演后批量修复并集中终审。不是盲目反复读整树或现场试色；如需改变方案锚点、扩大范围、突破保护或权限不足，再请求所缺决策/授权。

通过后先提取完成回复需要的结果，再按第 3.1 节清理 `runWorkspace`；用户明确要求保留审计包时登记 `kept-by-user`。不得因为清理临时证据而省略最终审计，也不得在完成前提前删除恢复所需文件。
