# 局部试色、增量验收与执行工具

Phase 0 读取第 3–5 节以初始化执行记录，Phase 3–6 读取第 1–2 节；详细阶段产物按第 6 节当前阶段读取。本文是覆盖清单、试色范围、门禁失效、重试、工具和性能安排的唯一执行定义；颜色标准仍以《颜色决策规则》为准，保护边界以《Figma 执行规范》为准。

## 1. 以完整局部场景试色

先从原稿真实灰度图提取 `sourceLuminanceTopology`，结合业务语义形成不含 Hue 的目标层级，再选新颜色。保留信息优先级，不机械保留每个像素亮度；跨深浅模式可反转明暗方向。不得用局部试色替代此前的原稿分析。

### 场景与写入范围

在 `mutationPlan.trialScenes` 建立最小完整局部场景：

- `sceneId`、覆盖的角色/材质/状态/宿主背景类别及实例→代表映射。
- `dependencyNodeIds`：完整材质根、相关背景、相邻对照控件和会影响该区域的兄弟叠层；祖先的 Alpha、裁切、混合模式也属于依赖。只读依赖不等于允许写入。
- `writePaths`、`representativeNodeIds`：本场景实际需要换色的节点与通道，包含文字、Icon、按钮、稳定底色与氛围。不能只换按钮却留着旧背景/旧文字，也不能将整个父级子树自动授权。
- 场景配方、原稿→副本映射、保护清单、预期局部层级与截图范围。配方包含实际引用的颜色锚点内容/证据指纹及表面家族映射，不能只存锚点 ID；KV→首卡衔接场景还引用实际 KV 图像/补底载体作为只读依赖。取色来源、家族或衔接层变化后使相关门禁失效，不能仅因节点底色未变沿用旧结论。

例如任务卡场景包含底色、标题/正文、强调数字、Icon/底托、小按钮及邻近标签；CTA 场景包含 CTA 材质、字色和实际宿主背景。优先把角色较齐全的一张卡片选作完整代表场景，避免把同一配方的代表底色、文字和按钮分散在多张卡上反复截图；该卡没有的角色及材质/状态/背景非等价项仍在其他实际区域补试，不为凑齐角色重造控件或强行合并。

若实际背景由页面根或跨区域表面承载，可将该节点的**确切背景 Paint 通道**预先登记为 `sharedContextPaths`，在 Phase 5 随代表场景写入。它可以影响全页背景像素，但不授权其他区域的文字、按钮或整树换色；不新增临时遮罩或假底色。所有依赖该表面的场景都引用它，修改后一起失效。首次试色前缺少必要背景依赖时先修订白名单，不能静默越界补改。

### Phase 5 的通过范围

在真实祖先环境中完成场景全部计划写入和读回后，再检查该场景彩色 1:1、灰度、模糊和缩略图；可以从同一有效截图派生。整页图只检查上下文、衔接和意外影响，明确标出未扩展区域。

`trialGateStatus=pass` 表示所有必需代表场景在其目标上下文中通过。此时只对已换肤范围检查残留色、可读性、局部层级和材质；未扩展区域的旧皮肤、临时明暗失配不作为该方案失败，也不能据此声称整页视觉通过。整页累计视觉重量、完整残留和全实例覆盖必须在 Phase 7 验收。

含标题或功能 Icon 的代表场景，必须对照 `titlePaintInventory` / `iconGlyphInventory` 逐路径读回标题本体与图形本体，再按 `iconPairPlan` 在同一 1:1 截图中联合核对图形、底托与卡片；旧色残留、仅底托已换色、`raster-blocked` 被当作完成，均使该场景失败。标为 `vivid-contrast-white` 的按钮须先保存白/近白字在真实尺寸的试色结果；没有白字失败证据不能提交深字版本作代表 PASS。其他按钮按已登记的情境字色方向与真实宿主验收。缩小整页图不能代替这些 1:1 检查。

### 修正与收敛

每轮记录可见问题、待验证原因、改变变量、前后截图和改善结果；恢复最佳已验证配方后再继续。无新依据不重复相同失败方案。连续两轮没有改善是重新诊断的默认触发点，不是强制通过或立即停止的次数上限：先核对承载层、背景、祖先与合成贡献，再决定是否有依据继续。确认允许范围内无法兼顾保护和真实视觉要求时，记录具体冲突及已试路径，按主流程报告阻塞；没有确认证据时保持待解决，不凭“审美难”直接索要审批。

## 2. 门禁跟随配方与依赖失效

每个场景分别记录 `mutationPlan.trialGates[sceneId]`，包含视觉结论、实际读回的依赖状态、配方/映射/保护和写入范围指纹、截图引用及审核时间。`trialGateStatus` 只是这些记录的汇总，不能独立充当扩展凭证。

- 配方、局部/共享背景、材质、祖先、保护范围、节点映射或状态变化：使受影响门禁失效；实例解绑后的新 ID 也需重新映射、读回和局部复验。
- 只改不相关区域：已通过场景保留。依赖覆盖不足时不能据此认定不相关，先补全依赖。
- 每批扩展前用**新鲜读回**核对对应门禁。仅有一个历史 PASS 或时间早于扩展不够；缺失、过期或有失败的相关场景不得扩展。新发现的非等价场景补试后，只恢复对应组。
- 共享配方修改后，已扩展实例也加入待更新/待复验清单。最终审计须确认所有实际配方为最终版本，不能留下试色 A、扩展 B 的混用。

所有局部修正与首次执行共用第 4.8 节的视觉单元登记表、冻结同色组、对比关系和状态强弱顺序。改动前用 `impact` 算受影响闭包，追加门禁失效事件；改动后读回完整单元及相关宿主并重新取图。影响清单包含只读/保护成员，不表示它们都要改色。不得为局部修正另建缩水验收，或把修正批次的属性完成报告当作控件通过。

扩展仍按明确角色映射写入，执行单位改为**一张卡片或一个完整视觉区域**，不是跨全页的“先所有底色、再所有文字、再所有按钮”。区域包括视觉上归属该卡片、但在 Frame 子树外的叠层/兄弟节点；Hero、页级 CTA、独立 Banner 和其他非卡片区域也须有归属，不能漏掉。每个区域内按背景/表面→材质→文字/Icon→操作状态完成全部计划写入，再一次性取 1:1 图审查，不把半成品判为失败。每个技术批次仍立即读回属性；发现结构或保护错误立即处理。当前区域未通过读回、残色预筛和真实视觉检查前，不切换到下一区域。一次截图可供该区域多项检查复用，最终逐实例覆盖记录不能省略。

## 3. 中断恢复与证据持久化

四个顶层产物不变。快照和截图可以是旁文件，用路径和哈希引用；不把大树反复嵌入日志。每次完成实际动作就原子保存本地产物，不在末尾补写历史时间。这里的“持久化”只指**当前未完成任务的中断恢复**，不是跨任务积累历史配色或长期归档。

Phase 0 先运行：

```sh
python3 scripts/run_workspace.py init --file-key ACTUAL_FILE_KEY --target-id ACTUAL_TARGET_ID
```

把返回的绝对路径登记为 `mutationPlan.runWorkspace`。当前运行产生的下载 KV、原稿/副本快照、配色 JSON/PNG、截图、派生视图、差异、批次、门禁和最终审计旁文件全部写入此目录；Skill 根目录只保留规则与可复用脚本。不得自动枚举或读取稳定 `artifacts/`、`work-*.png`、旧 `run-*` 目录来猜测当前 KV、目标或方案。当前输入必须来自本轮用户消息与当前 Figma 文件的实时读取。

只有用户明确要求恢复同一个未完成任务时，才读取既有 `runWorkspace`；恢复前同时核对标记中的 `fileKey/targetNodeId`、新 KV 身份或文件哈希、原稿快照指纹和 Figma 中唯一副本。任一不匹配即新建运行目录并重新只读分析，绝不把旧色板、旧截图或旧 PASS 带入新任务。

`mutationPlan` 保存 `runId`、源/副本 ID、`sourceToCloneNodeMap`、`trialScenes`、`trialGates`、`batches` 和 `executionPhaseLog`。恢复时先核对输入、原稿快照及既有副本，再从已验证阶段继续；首次仍遵循 Phase 0–7，局部回退允许追加事件，不删除历史事件，也不重新执行 clone。

每批写入前落盘：`batchId`、阶段/场景、依赖门禁、每个原子属性操作的实际 `before` 与计划 `after`。一个 Fill 数组、一个文字区间 API 调用等作为可读回的最小原子单元；同一操作内不混入解绑、增删节点和普通换色。

调用完成或异常后读回：

| 当前属性 | 处理 |
|---|---|
| 等于目标值 | 已完成，跳过重复写入 |
| 等于前值 | 尚未完成，依赖及白名单仍有效时可补写 |
| 既非前值也非目标值、节点缺失 | 冲突，停止该批；先定位部分写入、用户修改或失效映射 |

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

封存工具验证完整性与证据哈希，不识别图片好坏，也不自动生成审核理由。只有已实际查看目标上下文并满足视觉标准后才写 pass；封存成功不等于脚本证实审美成立。复核必须使用审核后实际新读取的快照，不改旧快照时间或重用旧 payload；条件、配方、依赖或证据变更会返回 stale/error。升级前只有一段说明的旧门禁不能继续使用。各场景门禁放入 `mutationPlan.trialGates`，旁文件只是输入/输出视图。

### 4.5 截图派生

```sh
python3 scripts/render_views.py scene-screenshot.png scene-views --blur-radius 3 --thumbnail-width 240
```

从同一真实截图生成彩色原尺寸、灰度、模糊和缩略图，清单记录源哈希及参数。输入必须包含真实背景；透明图被拒绝，不默认铺白。1:1 需另确认截图像素与设计尺寸比例，不能用低分辨率整页图放大冒充。工具不裁图、不改 Figma、不调用生成式模型。

审计命令用 `--out` 保存完整 JSON：退出码 0 表示本命令成功，1 表示差异失败/冲突/过期，2 表示输入或读取错误。派生视图用输出目录，错误时退出非零。任何非零结果先排查，不算门禁通过。本地验证：`python3 -m unittest discover -s tests -p 'test_*.py'`、`node --test tests/figma_snapshot.test.js`。

### 4.6 同色关系检查

```sh
python3 scripts/theme_audit.py color-relations source-before.json clone-now.json color-relations.json --map node-map.json --out color-relation-audit.json
```

`color-relations.json` 是 `sourceAudit.sourceColorRelations` 的输入视图：`{schemaVersion:1,groups:[{id,reason,paths:[颜色通道路径,...]}]}`。每组至少两个成员，`reason` 记录同角色/状态/材质/等价宿主或连续同色表面证据；不能按旧 RGB 全局分桶强制不同角色使用同一新色。它检查组内对应通道一起换成一致的新颜色，不检查新旧 RGB 相同。路径指向源 ID 命名空间下的完整 RGB(A) 对象，如 `/nodes/1:2/props/fills/0/color` 或 `/nodes/1:3/props/fills/0/gradientStops/0/color`，不能只填 r 通道。同色文字不同状态的 Alpha 单独保留，不进入 RGB 等价比较；Paint/祖先 Alpha、渐变几何和实际合成仍由结构及视觉检查负责。

关系成员按原稿语义、状态、材质职责和真实宿主在选新色前确定；**不得把目标 RGB/Recipe 值放进分组键**，也不得在成员不一致时拆组让审计通过。源稿已存在的宿主变体按其证据区分，不按错误目标色区分。`relationType` 缺省为 `source-equivalence`；有预先声明的 `basis` 时可用 `target-shared` 检查跨角色共享目标 RGB，或用 `hue-family` 加本次场景的 `maximumHueDistanceDegrees` 检查同族有彩色主体。高光/中性色单独分工，不用不稳定 Hue 判断中性表面。普通小按钮与 CTA 的稳定主体路径必须共同引用 `schemeAnchorContract.button` 并进入 `target-shared`/交互外观家族；不能只检查 Hue 接近，也不能只比较两处 Tab。

同一显示表面由不同底色/Alpha/宿主合成时，另加 `displayed-surface-continuity` 机器规则，verifier 为 `{type:"displayed-relations",groups:[{id,nodeIds,xy:[原生截图坐标,...],nativePixels:[宽,高],maximumChannelDelta:本次容差}]}`。Phase 3 冻结同职责空白采样点；采样覆盖 Tab 底与下方实际容器，避开媒体、字形、指示条及局部高光。`finalize` 的 `displayedSamples` 指向 `{sourceHash,actualHash,groups:[{id,source:[{image:{path,sha256},xy},...],actual:[...]}]}`，绑定对应快照并核验源/新像素关系。实际图片必须同时属于新鲜视觉门禁证据。该检查验最终合成，不要求参与合成的裸 RGB 相同，也不能以“基底同色”抵消最终断层。没有可验证样本或源稿关系不成立时，重新定位关系，不声称已经完成机器验收。

先从原稿建立分组，再由预检配方生成内存中的计划快照运行同一检查，明确标为计划验证；试色、扩展后以实际读回快照再次验证。语义拆分理由另记 `themeDecision` 并更新成员关系，不从错误结果反推预期。跨场景关系在双方已完成换肤后验证，未换肤成员不得误报为已通过。

原稿存在同族主要小按钮和 CTA 时，`colorManifest.schemeAnchorContract.button` 必须保存共同 RGB；每个主要小按钮与 CTA 至少一个稳定主体通道标记 `anchorId=button`，执行审计直接核对这些目标值等于共同锚点。`button-appearance-family` 仍是必需机器规则，verifier 用 `displayed-relations`，组为 `{id,relationType:"appearance-family",basis,carrierPaths,nodeIds,xy,nativePixels,additionalLightnessSpread,additionalColorSpreadDeltaE76}`，检查派生暗部、高光和真实合成没有造成可见异色分裂。`button.material/cta.base/cta.material` 专指该主要交互家族；次级、禁用或源稿明确非等价的控件用有依据的独立语义角色，不能把失败成员事后改为次级。`carrierPaths` 包含该家族全部实际参与的对应材质通道，每组同时包含小按钮与 CTA；源通道清单自动核对联合组与 `control-family-consistency` 的完整范围，不能仅登记 Tab 或把大小按钮拆成两个各自通过的组。

六色方案的精确执行由 `scripts/execution_audit.py` 的 `scheme-anchor-conformance` 统一检查：`schemeAnchorContract` 必须且只能包含 `background/card/number/icon/button/tab`，每个角色至少有一个稳定可见通道标记相同 `anchorId`，且 `target` 与锚点 RGB 完全一致。只保持 Hue 家族、不绑定代表值，或把 Tab 错绑到按钮/Icon，都不能通过。该机器检查在最终审计中必跑；代表试色阶段使用同一逻辑做扩展前预检。

`xy` 冻结原生截图中各成员的同职责主体取样，稳定主体、对应受光区分别比较，不拿小按钮主体与 CTA 窄高光相比，也不只取最有利的单点。样本沿用 `displayedSamples` 证据格式与新鲜门禁绑定。工具从实际合成 sRGB 计算 CIELAB L* 和 ΔE76，要求新稿的组内明度跨度/色差不超过原稿跨度加写入前明确的情境余量；两个余量分别给出、须有限且非负，无统一默认值。这里约束的是同族内部接近关系，不冻结原稿绝对 L*，也不恢复跨模式逐点对比度下限。数值通过仍须检查完整按钮与各自真实宿主上的视觉重量、材质和全局操作优先级。失败后改颜色或重新诊断源稿关系，不能从失败数值反推放宽余量。

`color-relations` 是必需机器规则，verifier 为 `{type:"color-relations",groupsHash:完整关系文件的digest}`；Phase 3 冻结，finalize 必须引用 `colorRelations` 并重新比较实际结果。确无同色关系时仍提供 `{schemaVersion:1,groups:[]}`，verifier 另附 `emptyEvidence` 说明原稿事实，不能漏掉整条规则。有依据的角色/宿主变体须在写入前更新登记表与冻结规则，并使相关门禁失效；不能从实际错误颜色反推拆组。

工具默认检验原稿组内 RGB 确实相等、新稿组内仍相等（`comparison:"float"`，仅容许 `1e-6` 浮点误差）；缺路径/不完整快照报错。只有证据确认跨节点类型的存储量化、且要求保持的是同一色板 Hex 时，个别组可显式使用 `comparison:"srgb8"`，保留原始 RGB、最大差异和量化依据，不全局放宽，更不能用于豁免保护属性或合成颜色差异。它能抓到同色底板因 Vector/Frame 分流而拆色，不能发现未登记成员、判定语义分组或自动通过视觉检查。原稿全量同色检索只用于建议分组，最终映射需核对真实角色；禁止用默认装饰角色吞掉未分类节点。保存结果于 `finalAudit.colorRelationAudit`，失败回到对应映射和场景。

### 4.7 原稿对比度基线检查

执行标准与覆盖职责只维护在《验收规则》第 5.1 节。复用 `contrast_audit.py`，不临时重写亮度公式或手写 PASS：

普通半透明文字/图形叠在复杂宿主上时，颜色 spec 可用 `{host:{image:{path,sha256},xy:[x,y]},layers:[{colorPath,alphaPaths}]}`：宿主来自经哈希验证的原生截图无字形区域，前景来自真实快照的 NORMAL SOLID Paint；只乘一次实际 Paint/节点/祖先 Alpha，不能用抗锯齿字形像素代替前景。

```sh
python3 scripts/contrast_audit.py source-before.json clone-now.json contrast-samples.json contrast-relationships.json --map node-map.json --out contrast-baseline-audit.json
```

`contrast-relationships.json` 为 `{policy:"source-baseline"|"contextual",decisionContext:{sourceUiMode,targetUiMode,adaptationMode,reason},pairs:[{id,kind,nodeIds,sampleIds,minimumContrast?}],emphasisOrders:[{id,strongerPairId,weakerPairId,sampleId}]}`，kind 为 `text/surface/state/icon/button`，nodeIds 使用源 ID，sampleIds 为已声明的采样职责 ID。无可比较顺序时 `emphasisOrders:[]`，旧数组输入仅兼容无顺序情形。顺序的两项必须在源/新各自共享相同的实际宿主颜色和采样职责，且原稿 stronger 的比值确实更大。写入前确定范围，不能从失败结果反推验收条件。

`contrast-samples.json`：`{schemaVersion:1,policy,decisionContext,sourceHash,actualHash,pairs:[{id,kind,nodeIds,samples:[{id,basis,source:{foreground,background},actual:{foreground,background}}]}]}`。两种颜色输入：`{layers:[{colorPath,alphaPaths:[]},...]}` 为自下而上的 NORMAL 纯色实际属性路径、以不透明宿主开始；或 `{image:{path,sha256},xy:[x,y]}` 为包含真实背景的原生截图像素。basis 写明叠层/取样依据。不能把复杂渐变或其他混合伪装为纯色叠层；脚本不推断真实遮挡、语义与采样代表性，须按视觉门禁核实。颜色/透明度路径采用源 ID 的规范化空间；sourceHash/actualHash 使用 `theme_audit.digest(snapshot_document(...))`，actual 文档先用 `mapped_document` 完整映射。

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

## 5. 执行覆盖、严格验收与性能

### 5.1 先把适用规则落到对象

在 `themeDecision.ruleLedger` 登记本次适用规则：`{schemaVersion:1,rules:[{id,kind,applicable,source,acceptance,scopeNodeIds}]}`。source 指向用户要求或维护的规则章节；acceptance 写明可观察的通过条件。`scopeNodeIds` 使用源 ID，覆盖该视觉规则涉及的全部实际实例；最终映射到副本。机器规则不必提供该字段。不适用项仍保留，附 `notApplicableEvidence`；不以名称不熟、嵌套深或旧色不明显作为不适用依据。

基线机器规则 ID：`source-unchanged/clone-allowed-differences/color-coverage/plan-complete/contrast-baseline/color-relations/visual-unit-coverage/color-bindings-clear`，全部必验。基线视觉规则 ID：`kv-fit/theme-consistency/clarity/hierarchy/button-salience/cta-salience/icon-clarity/readability/material-layers/surface-discernibility/state-discernibility/control-family-consistency`；存在对应角色就必验，KV、整页颜色/清晰度/层级/可读性不能跳过。同族控件跨区域出现时，`control-family-consistency` 的 scope 覆盖全部相关控件根；不存在可比较的同族实例才可附读取证据标不适用。其他用户规则用独立 ID 加入，例如浅→浅保留色标 S/V、保护区域、指定模式、数据强调。相互冲突时先按用户最新明确要求确定本次有效条件，不能并列执行互斥旧规则；确定性项目接入真实校验器，不手写一个机器 PASS。

Phase 3 写入前冻结清单哈希；清单变更使关联门禁失效。规则位置不重复搬进 ledger，仅记录适用范围和验收条件。脚本不能自动判断是否完整提取了自然语言规则，必须对照本次用户要求和适用参考章节逐项核对；也不能以脚本支持的字段为由缩减设计规则。

### 5.2 全量枚举防漏，目标校验防未执行

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

spec 是旁文件视图，引用 `sourceBefore/sourceNow/cloneNow/manifest/policy/nodeMap/ruleLedger` 的 JSON 路径和 `visualScenes:[{spec,gate}]`，必须同时引用 `colorRelations/contrastSamples/visualUnits`。finalize 先从全量源通道核对主要按钮/CTA 联合验收范围及必需的主体明度/色差关系，再逐项重算冻结同色关系、原稿与新稿合成对比度及可比较的强调顺序，并验证完整视觉单元的通道覆盖及新鲜上下文检查；缺证据、任一样本/关系失败均不放行。至少包含一个 `reviewScope:"whole-page"` 的最终整页场景，依赖种子为最终根，`hierarchy` 覆盖根并有整页截图，不能只凭局部 PASS 放行。finalize 同时重算原稿不变、差异许可、全量覆盖和目标完成；核对每个视觉场景、规则哈希及全部 scopeNodeIds。旧执行记录缺少新增规则或登记表时不能直接沿用旧 PASS，须补建原稿证据、冻结新规则并完成相关复验，历史记录保留。其他机器规则使用 `verifier`：`{type:"preserve-values",paths:[源属性路径]}` 精确保留；`{type:"preserve-hsv",paths:[源 RGB 对象路径],channels:["s","v","a"]}` 核对指定源通道；`{type:"target-values",targets:[{path,expected}]}` 核对声明目标。可比较的数值只容许已定义的浮点读回误差；目标路径使用源 ID 的规范化比较空间。当前工具未支持的能力应补实际 verifier，不能改为人工声称的机器 PASS。

`control-family-consistency` 还要求至少一个有效场景在同一次比较中覆盖该规则全部冻结 scope，不能由多个各只覆盖一张卡的 PASS 累加通过。可从同一原生全页图裁出并排片段，保留裁切来源/比例，并实际查看相邻与远处同族实例；整页层级检查可共用图像，不额外反复渲染。

任一必需项 FAIL/UNKNOWN、缺规则、漏实例、过期证据或允许差异未完成，整体均 FAIL；不能按通过比例、平均分或大多数区域正确放行。警告只用于全部必需门禁已通过后的非阻塞信息，不能容纳不可读、暗沉、不突出、漏改或违反保护。若保护色与新 KV 可读性无法兼顾，保留保护并准确报告未完成及具体冲突，不降级为警告。最终整页累计焦点仍必须实际查看，不能用局部代表的 PASS 推导全页美观。

### 5.4 缩短调用链，保持检查覆盖

- **配色提案使用快速只读路径。** Phase 0/1P 首次远程读取只返回：页面与两个候选顶层节点的 ID/类型/尺寸、原 UI 缩略图、新 KV 原生截图、直接影响 `sourceUiMode`/显著性/同族控件的精简摘要，以及新旧 KV 画风比较所需证据。禁止在同一返回中附带全树 Paint/Gradient、全部文字、全部路径或大段节点 JSON；预计超过约 12KB 时先聚合计数，再按明确缺口定向读取。不要对 `PAGE` 截图，也不要用 `figma.io.write` 代替视觉截图；直接对 UI/KV 节点使用 `get_screenshot` 或 `node.screenshot()`。高长 UI 先取一张缩略整页图，只有看不清的关键区域才补原尺寸局部图。
- 新 KV 截图只下载一次到本次 `runWorkspace`。优先运行 `python3 scripts/analyze_kv_preview.py <kv.png> --out <runWorkspace>/kv-analysis-fast.json` 生成候选色群和底边连续性统计，再由视觉判断环境/前景/材质身份；不为聚类临时引入 NumPy、科学计算依赖或重复导出。配色预览只在候选通过前置门禁后生成一次，修改色值才重渲染。
- 用户选色前不采集或传输完整 `snapshotThemeTree`，不建立逐实例 `layerStacks`、全量 `visualUnits`、所有文字区间和对比度关系。用户选色后进入 Phase 1W，一次性采集完整原稿快照并建立写入级基线，然后才允许 Phase 3；若用户未选择，昂贵审计不会白做。此延迟只优化时机，不降低任何写入或最终验收要求。
- **Phase 1W 固定快照路径。** 用 `python3 scripts/generate_figma_baseline_js.py <sourceFrameId> --page-id <pageId>` 生成经本地测试、长度小于 45,000 字符的 `use_figma` 程序；仅在当前页已是目标页或平台无需切页时可省 `--page-id`。一次 `snapshotThemeTree` 完整遍历（含隐藏实例子层），同次返回紧凑的区域/颜色/变量与样式绑定风险摘要，并以 `figma.io.write` 产出带长度与校验和的无损二进制 image block；这是数据传输，不是视觉截图。把该 block 原样保存到本次 `runWorkspace`，用 `python3 scripts/decode_theme_snapshot_png.py <artifact> <runWorkspace>/source-before.json` 解码；若保存的是 base64 文本，增加 `--base64`。节点数、根 ID、读取错误、校验和及字节长度必须全部核对后才建立基线。不得把缩略图、截断文本或仅有摘要当完整基线。若 image block 缺失/被转码，只记录一次失败；仅在后备分片能对应**同一次稳定采集**、校验总长度/分片数/指纹时改用后备路径，否则报告真实传输阻塞。不能为每片重新遍历全树，也不得在正式设计上轮流试文件、缓存、PNG 和原始大文本。Phase 1W 与 Phase 6 分别记录采集、编码、传输、解码耗时。
- 调用 `use_figma` 的编排层须直接读取返回的 `image` content block；不要把 40 万字符级 base64 打印给模型。若使用 `functions.exec`，在同一次编排中取 `result.content.find(x=>x.type==="image")`，以 `tools.apply_patch` 把 `block.data` 按约 120 字符分行写到 `runWorkspace/source-snapshot.b64`，随后只返回块数量、长度与工具状态；再以 `--base64` 解码。缺少 image block 时不要从原生视觉 screenshot 反推数据，也不要把 `figma.io.write` 的文件名误认为本地可访问路径。
- `figma_source_preflight.js` 的绑定风险摘要是写入前的风险入口：逐组处理 Paint 色标、文字区间、局部样式/变量绑定，再冻结目标 `afterHash`。本技能交付固定色副本，因此颜色变量与 Paint/带颜色 Effect 样式必须在副本 UI 范围解绑，精确保护内容也只解除引用而保留当前显示色；新 KV 锁定子树保持直接使用，不解绑、不重着色；非颜色变量保持原样。不得通过修改共享变量或样式来换肤，也不得先试写再从截图发现颜色回弹。摘要有 `omittedBindingGroups>0` 或读取错误时定向补查，不能视为“无绑定”。

- 原稿未变化时，复用已经完成的视觉单元登记表、关系图、通道分类和灰度分析；颜色配方变化不重建结构关系。每次局部修正先用 `impact` 列闭包，按完整单元一次读回/截图/复验，其他有效证据保留；共享背景实际影响全页时仍复验全部相关单元。最终全页检查不能省略。记录分析、写入、读回传输、截图及验收各段实际耗时，再评价性能，不把本地脚本耗时当作整次换肤耗时。

- 普通换肤复用完整快照、样式/材质分组及真实承载映射，不为每个阶段重新输出整树；原稿首次与最终、副本结构变化后和最终需完整核对。中间按具体操作与依赖读回，未变快照不再次传输；截断结果不能冒充完整文件。只读分析在依赖独立时合并调用，写入、读回和依赖变化保持顺序。
- 从全实例清单按实际材质/状态/背景等价关系选最少代表，同组只试一个完整场景。试色接近全页操作量时先检查分组是否过碎；非等价项仍补试，不为省时合并。Phase 2 按《配色方案提案》展示无金属 4/2 套或金属 6/3 套只读色板；用户选定后，真实 Figma 试色只执行这一套完整方案，仅对失败或关键疑点增加局部对照，不把全部候选都写进页面。
- Phase 6 先按 `regionPlan` 将操作分成各区域的清单；只在**同一区域、同一有效门禁组**内合并原子操作。每区建立 `{schemaVersion:1,regionId,operations,oldUiColors,protectedNodeIds,excludedSubtreeRootIds}`，其中 `excludedSubtreeRootIds` 必须包含全部 `kvLockedSubtreeRootIds`，`operations` 使用已冻结的 `figma_apply_color_diff.js` 精确 diff 格式；卡片视觉单元有外置兄弟叠层时加 `scopeNodeIds` 完整列出扫描范围，需在真实祖先合成下截图时加 `screenshotNodeId`。运行 `scripts/split_region_plan.py <region-plan.json>` 按真实完整代码长度与最多 60 项自动切分，再用 `scripts/generate_figma_region_js.py <part.json>` 生成 `use_figma` 程序。单次装得下时一张卡一次调用；装不下只拆该卡，前面批次仅守卫写入和即时读回，最后一批在同次调用中做紧凑旧色扫描及原生区域截图。不把两张未验收卡片混入一批，不把 Phase 5 与 Phase 6 合并，不把 detach/clone 混入颜色批次。返回 `visual-review` 不是区域 PASS：仍需查看 1:1 图、材质、保护、文字与跨区依赖；`old-color-review` 必须逐项解释或修正，`needs-recovery` 必须先读回已写项再恢复。若单批真实执行过慢、超时或接近上限，再依据测量拆分并先读回，不盲目重发。
- 完整快照的**校验**不等于重复传输完整快照。已有本地冻结模板时，先用 `scripts/generate_figma_snapshot_verify_js.py --compact <snapshot>` 在 Figma 内完整遍历并返回全树指纹、节点数和全部读取错误；不匹配再定向读取差异或做分段传输。副本完成换色后，若已经有 KV/解绑后的完整副本基线及全部精确区域操作，用 `scripts/project_clone_snapshot.py <clone-baseline.json> <region-plan-1.json> ... --out <expected-clone.json>` 推导目标；仅在投影支持全部差异且经过一张新鲜全树 Figma 指纹证明时，才能以该模板进入本地最终审计。投影失败、指纹不符、存在未建模的 Figma 侧效应或特殊属性时，不能伪造模板，改传完整副本快照定位差异。副本最终审计仍须完成结构/保护、全量目标、材质/文字和真实渲染门禁；紧凑指纹只省传输，不替代视觉检查。任何紧凑证明都不能跳过节点、隐藏实例子层、原稿差异或已批准读取异常的单独披露。

- 大树传输先核对本次接口预算。本次实测 `use_figma.code` 上限 50,000 字符，返回文本约 20,500 字符会截断；生成器统一留到 45,000，后备文本分片使用至多 17,500 ASCII 字符。操作数预算之外还须检查包含 helper 的实际代码长度。颜色批次复用 `snapshot_fingerprint.js` 与 `figma_apply_color_diff.js`；生成 after 指纹前须把已声明目标 RGB(A) 规范为 Figma 原生 float32，避免 Fill 自动同步 Vector region 后因 double/float32 表达差异误报冲突，实际 before 仍精确保留。只传原子属性的 before/after 指纹和精确颜色差异，在实际节点完整 Paint/Vector 数据副本上应用，不能把差异片段直接覆盖为完整 Paint。每项写入后**同次读取完整属性或文字区间**并核对 after 指纹；变量回弹立即返回冲突，不把“setter 没报错”当成功。Fill 引发的 Vector region 自动同步仅在完整 after 指纹吻合时作为完成项跳过，否则仍为冲突。

- 已有完整基准/精确目标模板时，可复用 `snapshot_fingerprint.js` / `snapshot_fingerprint.py` 减少读回传输：仍执行 `snapshotThemeTree` 全量真实采集，以 ID、父子顺序和全部属性的逐行指纹逐一核对；返回真实采集时间、错误、节点数、模板指纹与差异数。只有所有节点匹配且无错误、无缺失时，才可结合本地模板重建该次读回，并保留 live proof；不能只传声称 PASS，不能忽略差异/截断，不能给未重读的模板换时间戳。指纹是传输校验，不是视觉验收，也不是面向恶意输入的密码学证明。首次无完整基准时使用完整无损传输；`decode_snapshot_transport.py` 拒绝缺片、不一致和解码散列错误。禁止为每个小分片重复采集全树；若运行环境不能保留只读传输缓存，优先改善序列化或批量传输，并记录实际开销。
- 一张真实上下文截图可支持多条验收；彩色/灰度/模糊/缩略图由本地派生。完整区域组合完成后取图，不每改一个角色或一小批就远程截图。可从足够分辨率、包含真实祖先合成的整页图按真实边界派生局部视图；仅需更细材质或合成证据时追加原尺寸局部截图。原稿衍生图一次生成，未变区域复用；改过的区域必须新证据。
- 一次新鲜读回可同时重验多个共享场景、覆盖和保护检查，不能为每个检查单独重新取全树。批间任何关联依赖改变均需重验，不能用“已批量检查”掩盖过期状态。派生图与确定性分析在本地完成，只展示失败、统计和路径，避免工具输出占满上下文。

- 场景指纹按 Figma 数值语义规范化 JSON 中等值的 `1/1.0` 和 `0/-0.0`，避免格式差异误报过期；布尔值与数值仍区分，真实数值变化不放宽。`stateHashVersion=2` 闸门沿用真实审查时间和证据，不重写历史时间。升级旧格式门禁时，保留旧文件，仅使用已有完整状态和同一实际 review 重新计算指纹；没有这两份真实证据时重新读取/审查，不能直接把 stale 改成 pass。
- 在 `mutationPlan.batches` 与阶段事件记录真实 `startedAt/endedAt`、操作/节点/字节数、Figma 只读/写入/截图调用数、临时文件操作数、实际人工审批的工具名与原因、重试原因和结果；未取得弹窗原文时记 `approvalCause=unknown`，不得推定为 Figma、终端或 0 次。区分分析、传输、写入、截图、审阅、修正耗时。从 actual 时间定位瓶颈，不补造耗时；首次基线传输失败一次即走后备路径，同一区域连续两次无改善先诊断而非继续试色。不得为减少审批切换 Full Access、绕过产品权限或把有副作用的调用伪装成只读。下一次与约三卡片页面的对照目标是把先前约 51 次 Figma 调用压到 `10–15 次`、争取 `墙上耗时 <25 分钟`；50,000 字符代码预算可能仍迫使某卡拆批。这些只用于发现瓶颈，不是略过质量门禁或承诺固定时长的理由；未达标须按实测阶段说明原因。没有同规模实测前不承诺固定完成分钟数。

```sh
python3 scripts/split_region_plan.py region-plan.json
python3 scripts/generate_figma_region_js.py region-plan-part-0.json
python3 scripts/render_views.py whole-page.png region-views --regions pixel-regions.json
```

`pixel-regions.json` 为 `{sceneId:[x,y,width,height]}`，坐标是截图像素，必须从实际设计边界和截图比例换算；包含真实宿主及邻近比较控件，禁止低分辨率放大冒充 1:1。局部视图保存原截图指纹与裁切边界，裁切不代表新 Figma 渲染。

前两条命令只切分/生成待审查代码，不自行调用 Figma 或授予操作权限；`region-plan.json` 中的 `operations` 使用 clone ID、完整属性 before/after 指纹及原子 diff，来源必须是预声明配方。不得把一个 Paint 数组内部的相互依赖写入拆散，重复/重叠操作先合并，单原子操作超限时显式处理，不能静默截断。原 `execution_audit.py batch-plan` 的 `{path,before,after}` 格式仍可用于离线原子变更校验，但不是此处 `use_figma` 区域写入的输入格式。

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
- 全部小按钮、大按钮、状态和卡片氛围的 `layerStacks`，按实际层级区分基底、反射、罩染、塑形暗部、蒙版和位图；不能只读取单层颜色。
- 语义组件到真实 `visualSurfaceCarrier` 的映射。
- 每张卡片的 `titlePaintInventory` 与 `iconGlyphInventory`：标题逐 TEXT/文字区间列出全部可见 Fill、渐变色标、Stroke、颜色 Effect 与相关标题装饰；Icon 逐图形子节点列出 Vector/Boolean/IMAGE Paint、材质层与底托，明确 `glyph`、`container`、`protected` 或 `raster-blocked`。视觉上的标题或 Icon 不得仅因其父容器、光晕或底托已登记就算完成本体清点。
- 第 4.8 节的 `visualUnits`：完整结构到全部实际颜色承载层、宿主/叠层依赖与审核根的登记表，与全量通道清单逐项对照；深层列表/裁切 Frame 不能漏掉。
- `sourceColorRelations`：需保持的等价实例同色通道与连续同色表面，包含精确颜色通道和角色/材质/状态依据；按《颜色决策规则》第 9 节建立，不仅凭旧 RGB 或共享 Style/Variable 强制跨角色同色。所有非保护角色仍按新 KV 换色，变体在写入前明确。
- 组件实例、复合异形表面、卡片氛围层、KV 衔接信息带、Tab 状态、媒体保护区、前三名颜色保护清单与独立营销 Banner 整棵保护清单；Hero 外框、旧图偏移、祖先裁切/蒙版链及可见安全窗口。营销 Banner 须以构图/语义证据区分于普通业务卡，并从写色和残留清理目标中排除。
- 按《验收规则》第 5.1 节建立全实例对应的 `contrastRelationships` 与实际合成基线。
- 原稿整页及关键区域的真实灰度证据，以及 `sourceSalienceMap`、`sourceLuminanceTopology` 与不含目标色的 `semanticPriorityMap`；明确页面、卡片、文字、数字、Icon、Tab 和操作的原有优先级。
- 前置 `themeDecision.kvStyleComparison`：先读取新旧 KV，比较材质、体积、插画方式、线条和纹理，记录差异为轻微/明显/证据不足；再核对原 UI 的冲突节点。仅颜色或 IP 改变不触发迁移，明显画风变化也不等于全页重做。

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
- 按《配色方案提案》从锚点整理 3–5 个来源色、`kvPrimaryHue`、`metalAccentEvidence` 及表面撞色基准 `surfaceContrastBasis`。无可靠金属证据时生成规定的 4 套或 2 套同色系/撞色方案；撞色先比较约 180° 对向色与 KV 中有证据的高彩高明度色，再明确 `contrastDerivation=hue-opposition|kv-vivid-accent`；有可靠金属证据时生成规定的 6 套或 3 套 `metallic-analogous / gold-bright / clean-deep` 方案。正常明亮金色优先落在规定的暖亮金范围，主体中间调呈现金黄、高明度和有效彩度，不得用暗铜、棕橙或土黄替代，并默认规划深棕按钮字。缺少用户要求方案类型的必要基准时先处理输入阻塞，不伪造或静默减量。内部保留完整门禁与角色方向，面向用户只展示 `background/card/number/icon/button/tab` 六色投影；逐套完成 `proposalColorPreflight` 和面积化预览复核，只把全部通过的方案写入 `themeDecision.paletteProposal`。本阶段不复制页面、不替换 KV、不写 UI。

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
- 对 `titlePaintInventory` 与 `iconGlyphInventory` 的每个非保护、可编辑可见通道逐一给出目标 Paint Recipe 与写入路径；标题多层渐变按层保留空间结构，Icon 图形与底托分别定目标。每张卡片的 `titleGlyphCoverage` 必须列出 `planned / protected / raster-blocked` 的完整差集与证据；任何未计划通道或把 `raster-blocked` 计为已换色，Phase 3 不通过。
- 同时继承所选方案的 `accentFamilyPlan` 到 Icon/数字/按钮配方及 `theme-consistency` acceptance；不得因金属梯度或组件变体，在已确认的六色锚点之外另设稳定高亮 Icon 主体。
- 扩展 `colorClarityPlan`：保留 Phase 2 已确认的彩度、感知明度与受光目标，补充第 3.2 节浅→浅比较基线的适用性、最终是否沿用及精确通道、逐角色对比关系和渲染检查方法；用户授权参考设计师版本时，包含同角色参考研究与可迁移范围。不得把“后续会加材质”作为压暗当前主体色或放行灰闷方案的理由。
- 按钮背景与浅/深文字的组合候选及真实背景对比度计划：先按 KV 来源、彩度/明度、面积及宿主效果标记特别鲜艳的无金属撞色按钮 `buttonTextPriority=vivid-contrast-white`，这类按钮先以白/近白字提案和 1:1 试色，小按钮与 CTA 共用方向；白字在真实文字覆盖区对比度不足时再试深字，登记白字截图、采样、原因及最终选择依据。其他按钮用 `buttonTextPriority=contextual`，依据材质、实际宿主与可读性选择浅字或深字并记录依据，不强制白字起步。`gold-bright` 仍默认验证深棕字，不得为白字压暗金色；预览脚本不得把特别鲜艳撞色的白字仅因深字静态比值较高而自动替换。
- 画风迁移时，`styleAdaptationPlan` 须包含原形状家族、风格载体、逐属性允许差异与裁切安全范围。
- 第 5.1 节 `ruleLedger`、全量 `colorManifest` 分类和覆盖差集校验通过；规则清单及目标在任何 UI 写入前冻结，场景引用同一指纹。
- 冻结 `visualUnits`、同色关系及对应对比关系；可比较的同宿主强弱顺序进入 `emphasisOrders`。整组配方的计划快照先通过关系预检，普通写入与局部修正继承同一套约束。
- `preflightThemeDecision=pass`，并绑定 `paletteSelection.schemeId` 与所选方案指纹。

#### 通过条件

用户已明确选定一个方案；六色 `schemeAnchorContract`、来源锚点、模式、表面与交互关系完整，六个 `anchorId` 的目标值已通过机器预检，CTA 和主要操作拥有正确显著性；色相不由题材或材质标签机械推出，旧 UI 色相未进入新方案。背景、卡片、主要按钮/CTA 的色相关系满足第 3.0 节。无金属 `contrast` 方案须有可靠 `surfaceContrastBasis`、两类候选的取舍证据，并与 `contrastDerivation=hue-opposition|kv-vivid-accent` 一致；金属方案须有可靠 `metalAccentEvidence` 并标明 `buttonVariant`。选择 `gold-bright` 时，实际按钮主体中间调必须保持正常明亮金黄、高彩度与清楚受光，不得落成暗铜、棕橙、土黄或由窄高光勉强显金，并已用深棕字作为默认方向验证。功能 Icon 图形引用 `icon`，小按钮与 CTA 共同引用 `button`，Tab 引用表面同系 `tab`，普通 Icon 底托与二者共同满足 `icon-container < selected-tab < primary-button`；缺任一关系不得通过。

`accentFamilyPlan` 必须与已选六色及各角色稳定主体相符；Icon 无连续背景环境来源，或深色 UI 的 `number` 与 `icon` 锚点 Hex 不同，均不得通过。公开锚点若本身违反该计划，应回 Phase 2 重新展示并确认，不能在 Phase 3 偷改。

### Phase 4：复制并替换 KV

按照《Figma 执行规范》只复制一次并替换副本 KV。本阶段不得改换 UI 配色；但必须在副本上完成固定色交付所需的颜色绑定解绑。先冻结当前有效显示色与绑定清单，再先冻结新 KV 的 `kvLockedSubtreeRootIds`、完整子树指纹和截图；随后只解除副本 UI 范围的颜色变量、Fill/Stroke 样式、文字局部颜色样式和带颜色 Effect 样式，包含隐藏层与实例子层但遇到 KV 锁定根必须停止下钻，不对原稿、共享变量/样式或主组件写入。若解绑引发显示色或结构变化，先在副本上恢复到冻结值并复查，不把未处理项静默跳过。解绑前后核对 Paint/渐变色标/Effect 值、文字区间、六色锚点、保护层与 1:1 渲染；排除 KV 锁定子树后的 UI 颜色绑定清零、且 KV 指纹未变后，才采集下述副本基线。

#### 必须产出 `mutationPlan`

- 原 Frame ID、副本 ID、位置、KV 替换记录和 `kvFitPlan`（实际窗口、等比缩放、主图边界、补底、节点/属性白名单、`kvLockedSubtreeRootIds`、锁定指纹和渲染证据）。
- 为 Phase 7 的紧凑证明，在 KV 和预先登记的必要副本解绑完成、UI 换色开始前，用同一固定基线生成器对副本 ID 采集一次完整副本基线（使用独立的 `--file-name theme-clone-baseline.png`）；后续未建模的新增/解绑/布局侧效应使该模板失效时必须重新采集或走完整副本读回，不得只把颜色 diff 叠到过期结构上。
- `trialScenes` 与 `representativeNodeIds`：按完整局部场景覆盖实际角色及非等价材质、状态、背景，登记依赖、保护、写入通道和实例→代表映射；具体定义见《局部试色与执行工具》第 1 节。页面根/跨区域共享背景只允许预登记的确切 Paint 通道，不授权整树换色。
- 每个目标节点的 Paint 职责、目标 Recipe、允许差异和计划解绑理由。
- `regionPlan`：按页面视觉顺序列卡片及其他完整区域；每区记录语义/视觉边界、归属的视觉单元与精确写入通道、保护/内容素材、预期截图范围和共享依赖。每个待换肤通道恰有一个写入区域；页面背景、Hero 衔接等跨区通道单列为 `sharedContextPaths`，各区只读引用，不重复写入。卡片子树外但视觉上归属该卡的兄弟叠层也须归入该区；没有卡片外框的完整模块仍独立成区。
- 映射未确认的可见 Paint 保持待处理，不用 `decoration` 等兜底角色自动上色；节点类型、宽度和旧色明度只能辅助检索，不能代替角色及材质职责判断。

#### 通过条件

原稿未改变；只有一个副本；新 KV 已按 `kvFitPlan.fitMode` 和选定尺度真实显示且无拉伸：`preserve-scale-bottom-crop` 允许仅截去下方超高部分，只有用户明确要求完整显示时才要求四边全部可见；Hero 外框、下方 UI 布局及功能叠层受保护；代表节点白名单在首次 UI 写色前确定。

### Phase 5：代表性试色与视觉门禁

首次 UI 颜色写入仅限预登记场景的代表节点、必要 Paint 后代及共享背景通道。背景、材质、文字、Icon 和操作状态组成完整局部场景后再视觉检查；禁止顺便循环换色其他实例。

按《局部试色与执行工具》第 1 节查看场景 1:1、灰度、模糊和缩略图；整页截图用于上下文和意外影响检查。只验已换肤场景的残留、层级、可读性和材质，未扩展旧皮肤不作为局部失败，也不声称整页通过。

按《颜色决策规则》第 3、5–9 节和《叠层合成审计》验证各实际角色，记录 `buttonCompositeReview` / `cardAtmosphereReview` 及针对问题的对照试色。复核 `heroBottomExtensionDecision`：选择底部延伸时在 KV→页面接缝的 1:1 图中验证起点连续及纯色/渐变趋势合理；底部不适合或未选择时，验证大范围环境背景与实际衔接方式自然，不能出现无解释的断层。同时在实际尺寸、灰度、模糊和整页重复中检查浅色 UI 的卡片是否按 `cardSurfaceStrategy` 成为干净的低彩近白/纯白稳定面，主题色只留在允许的顶部氛围；再检查 `iconPairPlan` 的图形与底托是否出现 `gradient-stop-collapse / container-too-heavy / pair-low-separation / pair-over-salient`，以及 Tab 与 Icon 底托是否淡淡带色且没有暗沉、沉重色块或高频暗点，并与主要按钮一起满足 `Icon 底托 < 选中 Tab < 主要按钮/CTA`；标签底板与文字不得淡成水印。`dark-to-light` 的卡顶光影逐层完成 keep/fade/remove-visually 判定，冗余氛围视觉移除后不得残留顶部暗块。禁用按钮须与正常态同配方，只以整体有效 50% 透明度区分。按第 3.0 节将 KV 原始环境区域与实际背景、卡片和主要操作并排验证 `themeColorConsistencyAudit`，再看同一截图派生的彩色模糊图与缩略图，确认相近家族或撞色反差及面积分工实际成立；色相有疑点时比较该维度，不用按钮 V/字色比较代替。代表写入后先读回六个 `anchorId` 与 `schemeAnchorContract` 完全一致，锚点、表面家族与色相关系计划引用纳入场景配方依赖。无改善时按执行工具规则重新诊断，不用数值、文字说明或单层颜色代替真实视觉证据。

同一代表场景还要按 `accentFamilyPlan` 并排看数字、Icon、按钮的稳定主体；深色 UI 在真实宿主上同时验证数字/Icon 共色的清晰度。1:1 保材质细节，模糊/缩略图检查高频 Icon 是否形成额外亮色焦点。若问题在已确认的公开 `number/icon` 锚点本身，不能偷偷换值来试色，回 Phase 2 重新展示方案并取得选择；只在已选锚点周围修复金属暗部/高光时，仍须保留原色标关系并重验受影响场景。

画风迁移模式还须执行《画风迁移规则》的代表性检查：强调数字、Icon、按钮与 Tab、外卡/内卡、裁切边缘。仅完成换色或添加统一描边不能通过。

#### 通过条件

所有必需场景形成带真实截图和配方/依赖指纹的 `trialGates`，汇总为 `trialGateStatus=pass`。修正先更新计划，重新验受影响场景。代表试色和全页扩展不得发生在同一次写入调用中；PASS 的失效规则见《局部试色与执行工具》第 2 节。

### Phase 6：全页扩展

只有对应场景门禁通过且新鲜读回确认配方、映射与上下文指纹仍有效，才能将该方案扩展到剩余节点；历史 PASS 本身不够。

先读回 Hero/页面背景等已登记的全局共享通道；未到目标值时按原门禁写入并确认一次，再按 `regionPlan` 的视觉顺序逐区推进。Phase 5 已试色的代表卡片也要在此补齐未写通道，不能把代表场景 PASS 直接当作整卡 PASS。`regionPlan` 的每区状态只按 `pending → writing → reviewing → pass` 更新；失败保持在当前区修复，不把半张卡片标为完成。跨区域共享配方或祖先变化会使已通过的相关区域失效，须返回重验，不能沿用旧截图。

- 只按 `mutationPlan` 写入，不以坐标、面积、名称或旧色相进行全页猜测。
- 每次写入按批次保存前值、目标值并读回实际 `mutatedNodeIds`；超时/部分失败按执行工具第 3 节恢复，不盲目重复。解绑后重新映射并使相关门禁失效。
- 当前区域内完成表面、材质、文字、Icon、状态和操作的计划写入，技术批次只为请求大小/失败恢复而拆，不在批次间切换到另一张卡片。每批属性检查仍立即执行；组合完成后取一次足够分辨率的区域截图复用到多项检查，需诊断细节时才补图。
- 区域完成前跑紧凑的 Selection colors 等价聚合，与已登记的旧 UI 色及新角色配方比较；给残留通道标注可见贡献、精确保护或内容素材归属。发现可编辑旧色时先补入 `mutationPlan` 的确切节点/通道和配方，再按本阶段门禁修正并复看 1:1 图；聚合结果本身不授权按色值批量写入。读回、保护、覆盖、残色与真实画面均通过，才标记本区 `pass` 并进入下一区。Phase 7 仍对整个副本重做完整 Paint＋渲染残留审计。
- 每个按钮和氛围实例都核对实际背景、祖先透明度及状态；材质相同不代表换到另一背景也合格。新发现的非等价配方须先补入代表白名单并单独试色通过，再扩展该组。

#### 通过条件

`regionPlan` 覆盖全部待处理 UI 通道且各区均为新鲜 `pass`；所有已识别角色已处理或有明确保护/跳过理由；扩展使用有效场景门禁及对应最终配方，没有冲突批次、待更新实例或未解决的失效场景。随后才进入 Phase 7 的跨区域同族比较和整页最终审计。

### Phase 7：最终审计

完整执行[《验收规则》](validation.md)第 1–10 节，逐项填写第 11 节的唯一闸门清单；再执行第 5.3 节 finalize，生成 `finalAudit`。不得因入口不重复列出字段而省略检查。

本阶段必须覆盖原稿/副本结构、KV 适配、全部精确保护、文字与状态、真实合成材质、全 Paint/IMAGE 与渲染残留、逐实例上下文，以及完整五种视图和整页累计显著性。核对 `regionPlan` 每区的归属覆盖、新鲜 `pass` 证据与跨区同族一致性，再核对有效场景门禁、最终配方一致性和批次读回；不得有待更新实例、待恢复操作或未解决冲突，局部 PASS 不代替整页通过。

任一失败返回对应 Phase，只修正并重验受影响依赖，最终刷新相关审计；不沿用修正前的截图/PASS，不带已知失败交付。

通过后先提取完成回复需要的结果，再按第 3.1 节清理 `runWorkspace`；用户明确要求保留审计包时登记 `kept-by-user`。不得因为清理临时证据而省略最终审计，也不得在完成前提前删除恢复所需文件。
