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

例如任务卡场景包含底色、标题/正文、强调数字、Icon/底托、小按钮及邻近标签；CTA 场景包含 CTA 材质、字色和实际宿主背景。不存在的角色不补造。材质、状态或背景非等价时分别选代表，不以名称/颜色相同直接合并。

若实际背景由页面根或跨区域表面承载，可将该节点的**确切背景 Paint 通道**预先登记为 `sharedContextPaths`，在 Phase 5 随代表场景写入。它可以影响全页背景像素，但不授权其他区域的文字、按钮或整树换色；不新增临时遮罩或假底色。所有依赖该表面的场景都引用它，修改后一起失效。首次试色前缺少必要背景依赖时先修订白名单，不能静默越界补改。

### Phase 5 的通过范围

在真实祖先环境中完成场景全部计划写入和读回后，再检查该场景彩色 1:1、灰度、模糊和缩略图；可以从同一有效截图派生。整页图只检查上下文、衔接和意外影响，明确标出未扩展区域。

`trialGateStatus=pass` 表示所有必需代表场景在其目标上下文中通过。此时只对已换肤范围检查残留色、可读性、局部层级和材质；未扩展区域的旧皮肤、临时明暗失配不作为该方案失败，也不能据此声称整页视觉通过。整页累计视觉重量、完整残留和全实例覆盖必须在 Phase 7 验收。

### 修正与收敛

每轮记录可见问题、待验证原因、改变变量、前后截图和改善结果；恢复最佳已验证配方后再继续。无新依据不重复相同失败方案。连续两轮没有改善是重新诊断的默认触发点，不是强制通过或立即停止的次数上限：先核对承载层、背景、祖先与合成贡献，再决定是否有依据继续。确认允许范围内无法兼顾保护和真实视觉要求时，记录具体冲突及已试路径，按主流程报告阻塞；没有确认证据时保持待解决，不凭“审美难”直接索要审批。

## 2. 门禁跟随配方与依赖失效

每个场景分别记录 `mutationPlan.trialGates[sceneId]`，包含视觉结论、实际读回的依赖状态、配方/映射/保护和写入范围指纹、截图引用及审核时间。`trialGateStatus` 只是这些记录的汇总，不能独立充当扩展凭证。

- 配方、局部/共享背景、材质、祖先、保护范围、节点映射或状态变化：使受影响门禁失效；实例解绑后的新 ID 也需重新映射、读回和局部复验。
- 只改不相关区域：已通过场景保留。依赖覆盖不足时不能据此认定不相关，先补全依赖。
- 每批扩展前用**新鲜读回**核对对应门禁。仅有一个历史 PASS 或时间早于扩展不够；缺失、过期或有失败的相关场景不得扩展。新发现的非等价场景补试后，只恢复对应组。
- 共享配方修改后，已扩展实例也加入待更新/待复验清单。最终审计须确认所有实际配方为最终版本，不能留下试色 A、扩展 B 的混用。

所有局部修正与首次执行共用第 4.8 节的视觉单元登记表、冻结同色组、对比关系和状态强弱顺序。改动前用 `impact` 算受影响闭包，追加门禁失效事件；改动后读回完整单元及相关宿主并重新取图。影响清单包含只读/保护成员，不表示它们都要改色。不得为局部修正另建缩水验收，或把修正批次的属性完成报告当作控件通过。

扩展仍按明确角色映射写入，但按**完整视觉区域**安排检查：区域内背景→材质→文字/Icon→操作状态的依赖完成后一起截图，不能每改一种角色就把半成品判为视觉失败。每批仍做属性读回；写入中发现结构或保护错误立即处理，不等区域完成。一次截图可为同区域多项检查提供证据，最终逐实例覆盖记录不能省略。

## 3. 中断恢复与证据持久化

四个顶层产物不变。快照和截图可以是旁文件，用路径和哈希引用；不把大树反复嵌入日志。每次完成实际动作就原子保存本地产物，不在末尾补写历史时间。

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

颜色读回按预先声明的目标配方校验；只有第 3.2 节浅→浅保留条件或当前明确锁定的通道才与源值保持，不复用历史任务中强制保留源 S/V 的专用校验代码。属性差异通过不代表按钮、CTA 或 Icon 已在背景上突出，视觉门禁仍按《颜色决策规则》第 3.2 节执行。

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

`reviewRequirements` 在写入前登记 `{id,acceptance,nodeIds}`，至少包含 `theme-consistency/clarity/hierarchy`；存在表面边界或控件状态时，分别登记 `surface-discernibility/state-discernibility`，不能合并成文字可读或笼统 clarity；按实际角色再包含按钮显著性、CTA 最强操作、Icon 清晰度、文字、材质和用户专属规则。规则 ID/验收条件来自第 5 节冻结的清单，`recipe.ruleLedgerHash` 引用其指纹。验收条件不得由失败结果反推或临时放宽。

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

关系成员按原稿语义、状态、材质职责和真实宿主在选新色前确定；**不得把目标 RGB/Recipe 值放进分组键**，也不得在成员不一致时拆组让审计通过。源稿已存在的宿主变体按其证据区分，不按错误目标色区分。`relationType` 缺省为 `source-equivalence`；有预先声明的 `basis` 时可用 `target-shared` 检查跨角色共享目标 RGB，或用 `hue-family` 加本次场景的 `maximumHueDistanceDegrees` 检查同族有彩色主体。高光/中性色单独分工，不用不稳定 Hue 判断中性表面。普通小按钮与 CTA 的主体路径必须共同进入交互家族，不能只比较两处 Tab。

同一显示表面由不同底色/Alpha/宿主合成时，另加 `displayed-surface-continuity` 机器规则，verifier 为 `{type:"displayed-relations",groups:[{id,nodeIds,xy:[原生截图坐标,...],nativePixels:[宽,高],maximumChannelDelta:本次容差}]}`。Phase 3 冻结同职责空白采样点；采样覆盖 Tab 底与下方实际容器，避开媒体、字形、指示条及局部高光。`finalize` 的 `displayedSamples` 指向 `{sourceHash,actualHash,groups:[{id,source:[{image:{path,sha256},xy},...],actual:[...]}]}`，绑定对应快照并核验源/新像素关系。实际图片必须同时属于新鲜视觉门禁证据。该检查验最终合成，不要求参与合成的裸 RGB 相同，也不能以“基底同色”抵消最终断层。没有可验证样本或源稿关系不成立时，重新定位关系，不声称已经完成机器验收。

先从原稿建立分组，再由预检配方生成内存中的计划快照运行同一检查，明确标为计划验证；试色、扩展后以实际读回快照再次验证。语义拆分理由另记 `themeDecision` 并更新成员关系，不从错误结果反推预期。跨场景关系在双方已完成换肤后验证，未换肤成员不得误报为已通过。

原稿存在同族主要小按钮和 CTA 时，`button-appearance-family` 是额外必需机器规则，verifier 仍用 `displayed-relations`，组为 `{id,relationType:"appearance-family",basis,carrierPaths,nodeIds,xy,nativePixels,additionalLightnessSpread,additionalColorSpreadDeltaE76}`。`button.material/cta.base/cta.material` 专指该主要交互家族；次级、禁用或源稿明确非等价的控件用有依据的独立语义角色，不能把失败成员事后改为次级。`carrierPaths` 包含该家族全部实际参与的对应材质通道，每组同时包含小按钮与 CTA；源通道清单自动核对联合组与 `control-family-consistency` 的完整范围，不能仅登记 Tab 或把大小按钮拆成两个各自通过的组。

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

基线机器规则 ID：`source-unchanged/clone-allowed-differences/color-coverage/plan-complete/contrast-baseline/color-relations/visual-unit-coverage`，全部必验。基线视觉规则 ID：`kv-fit/theme-consistency/clarity/hierarchy/button-salience/cta-salience/icon-clarity/readability/material-layers/surface-discernibility/state-discernibility/control-family-consistency`；存在对应角色就必验，KV、整页颜色/清晰度/层级/可读性不能跳过。同族控件跨区域出现时，`control-family-consistency` 的 scope 覆盖全部相关控件根；不存在可比较的同族实例才可附读取证据标不适用。其他用户规则用独立 ID 加入，例如浅→浅保留色标 S/V、保护区域、指定模式、数据强调。相互冲突时先按用户最新明确要求确定本次有效条件，不能并列执行互斥旧规则；确定性项目接入真实校验器，不手写一个机器 PASS。

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

- 原稿未变化时，复用已经完成的视觉单元登记表、关系图、通道分类和灰度分析；颜色配方变化不重建结构关系。每次局部修正先用 `impact` 列闭包，按完整单元一次读回/截图/复验，其他有效证据保留；共享背景实际影响全页时仍复验全部相关单元。最终全页检查不能省略。记录分析、写入、读回传输、截图及验收各段实际耗时，再评价性能，不把本地脚本耗时当作整次换肤耗时。

- 普通换肤复用完整快照、样式/材质分组及真实承载映射，不为每个阶段重新输出整树；原稿首次与最终、副本结构变化后和最终需完整核对。中间按具体操作与依赖读回，未变快照不再次传输；截断结果不能冒充完整文件。只读分析在依赖独立时合并调用，写入、读回和依赖变化保持顺序。
- 从全实例清单按实际材质/状态/背景等价关系选最少代表，同组只试一个完整场景。试色接近全页操作量时先检查分组是否过碎；非等价项仍补试，不为省时合并。Phase 3 可以按《配色方案提案》展示 4 套或 2 套只读色板；用户选定后，真实 Figma 试色只执行这一套完整方案，仅对失败或关键疑点增加局部对照，不把全部候选都写进页面。
- 用 `batch-plan` 合并同一阶段、同一有效门禁组的原子操作，默认每批至多 64 项、约 48KB，是可调起点。每批输入只带涉及的节点映射/操作，不反复带全页映射和大快照；不把 Phase 5 与 Phase 6 合并，不把 detach/clone 混入颜色批次。实际 API 限制或耗时决定调整，超时后先读回，不盲目重发。

- 大树传输先核对本次接口预算。本次实测 `use_figma.code` 上限 50,000 字符，返回文本约 20,500 字符会截断；代码预算建议留到 45,000，分片使用至多 17,500 ASCII 字符。操作数预算之外还须检查包含 helper 的实际代码长度。颜色批次复用 `snapshot_fingerprint.js` 与 `figma_apply_color_diff.js`；生成 after 指纹前须把已声明目标 RGB(A) 规范为 Figma 原生 float32，避免 Fill 自动同步 Vector region 后因 double/float32 表达差异误报冲突，实际 before 仍精确保留。只传原子属性的 before/after 指纹和精确颜色差异，在实际节点完整 Paint/Vector 数据副本上应用，不能把差异片段直接覆盖为完整 Paint。支持普通属性标量与混色文字范围；Fill 引发的 Vector region 自动同步仅在完整 after 指纹吻合时作为完成项跳过，否则仍为冲突。

- 已有完整基准/精确目标模板时，可复用 `snapshot_fingerprint.js` / `snapshot_fingerprint.py` 减少读回传输：仍执行 `snapshotThemeTree` 全量真实采集，以 ID、父子顺序和全部属性的逐行指纹逐一核对；返回真实采集时间、错误、节点数、模板指纹与差异数。只有所有节点匹配且无错误、无缺失时，才可结合本地模板重建该次读回，并保留 live proof；不能只传声称 PASS，不能忽略差异/截断，不能给未重读的模板换时间戳。指纹是传输校验，不是视觉验收，也不是面向恶意输入的密码学证明。首次无完整基准时使用完整无损传输；`decode_snapshot_transport.py` 拒绝缺片、不一致和解码散列错误。禁止为每个小分片重复采集全树；若运行环境不能保留只读传输缓存，优先改善序列化或批量传输，并记录实际开销。
- 一张真实上下文截图可支持多条验收；彩色/灰度/模糊/缩略图由本地派生。完整区域组合完成后取图，不每改一个角色或一小批就远程截图。可从足够分辨率、包含真实祖先合成的整页图按真实边界派生局部视图；仅需更细材质或合成证据时追加原尺寸局部截图。原稿衍生图一次生成，未变区域复用；改过的区域必须新证据。
- 一次新鲜读回可同时重验多个共享场景、覆盖和保护检查，不能为每个检查单独重新取全树。批间任何关联依赖改变均需重验，不能用“已批量检查”掩盖过期状态。派生图与确定性分析在本地完成，只展示失败、统计和路径，避免工具输出占满上下文。

- 场景指纹按 Figma 数值语义规范化 JSON 中等值的 `1/1.0` 和 `0/-0.0`，避免格式差异误报过期；布尔值与数值仍区分，真实数值变化不放宽。`stateHashVersion=2` 闸门沿用真实审查时间和证据，不重写历史时间。升级旧格式门禁时，保留旧文件，仅使用已有完整状态和同一实际 review 重新计算指纹；没有这两份真实证据时重新读取/审查，不能直接把 stale 改成 pass。
- 在 `mutationPlan.batches` 与阶段事件记录真实 `startedAt/endedAt`、操作/节点/字节数、读写/截图调用数、重试原因和结果；区分分析、传输、写入、截图、审阅、修正耗时。从 actual 时间定位瓶颈，不补造耗时；超过预期时先诊断碎批次、重复载荷和无改善试色，不能以时间预算省略必需验收。没有同规模实测前不承诺固定完成分钟数。

```sh
python3 scripts/execution_audit.py batch-plan atomic-operations.json --max-operations 64 --max-bytes 48000 --out batches.json
python3 scripts/render_views.py whole-page.png region-views --regions pixel-regions.json
```

`pixel-regions.json` 为 `{sceneId:[x,y,width,height]}`，坐标是截图像素，必须从实际设计边界和截图比例换算；包含真实宿主及邻近比较控件，禁止低分辨率放大冒充 1:1。局部视图保存原截图指纹与裁切边界，裁切不代表新 Figma 渲染。

批次命令不写 Figma、不授予操作权限；输入操作是 `{path,before,after}`，path 使用副本 ID，来源必须是预声明配方。不得把一个 Paint 数组拆到不同批次，重复/重叠操作先合并，单原子操作超限时显式处理，不能静默截断。

## 6. 阶段产物与通过条件

### Phase 0：解析与初始化

#### 必须执行

- 解析唯一目标 Frame、新 KV 和旧 KV 图片 Paint。
- 确认可用 Figma 写入与截图能力。
- 初始化四个执行产物及 `mutationPlan.executionPhaseLog`；若为恢复任务，先读取既有 runId、副本、快照、批次和门禁记录，不创建第二份副本。

#### 通过条件

目标、KV、旧 KV Paint 均唯一且可访问；否则在任何写入前停止。

### Phase 1：只读原稿审计

完整执行《Figma 执行规范》的检查与快照要求。

#### 必须产出 `sourceAudit`

- 原稿结构快照、所有 Paint/Effect/IMAGE 分类、`paintPresenceMask` 与第 5.2 节全量颜色通道清单；全部通道分类完成，不留未知角色。
- 全部小按钮、大按钮、状态和卡片氛围的 `layerStacks`，按实际层级区分基底、反射、罩染、塑形暗部、蒙版和位图；不能只读取单层颜色。
- 语义组件到真实 `visualSurfaceCarrier` 的映射。
- 第 4.8 节的 `visualUnits`：完整结构到全部实际颜色承载层、宿主/叠层依赖与审核根的登记表，与全量通道清单逐项对照；深层列表/裁切 Frame 不能漏掉。
- `sourceColorRelations`：需保持的等价实例同色通道与连续同色表面，包含精确颜色通道和角色/材质/状态依据；按《颜色决策规则》第 9 节建立，不仅凭旧 RGB 或共享 Style/Variable 强制跨角色同色。所有非保护角色仍按新 KV 换色，变体在写入前明确。
- 组件实例、复合异形表面、卡片氛围层、KV 衔接信息带、Tab 状态、媒体保护区与前三名颜色保护清单；Hero 外框、旧图偏移、祖先裁切/蒙版链及可见安全窗口。
- 按《验收规则》第 5.1 节建立全实例对应的 `contrastRelationships` 与实际合成基线。
- 原稿整页及关键区域的真实灰度证据，以及 `sourceSalienceMap` 与 `sourceLuminanceTopology`；明确页面、卡片、文字、数字、Icon、Tab 和操作的原有优先级。
- 前置 `themeDecision.kvStyleComparison`：先读取新旧 KV，比较材质、体积、插画方式、线条和纹理，记录差异为轻微/明显/证据不足；再核对原 UI 的冲突节点。仅颜色或 IP 改变不触发迁移，明显画风变化也不等于全页重做。

#### 通过条件

页面背景、卡片、容器、普通文字、标题、关键数据、Icon、标签、Tab、小按钮和 CTA 中实际存在的角色均已识别；新旧 KV 画风比较及原 UI 冲突检查已完成，先确定普通换肤或局部画风迁移，再进入配色分析。不允许边写边第一次判断角色。

### Phase 2：新 KV 分析

完整执行《KV 色彩分析》，本阶段禁止修改 Figma。

#### 必须产出

- `visualIntentProfile`、颜色角色、环境/主体/材质/高光证据。
- `adaptationMode=color-only/style-adaptation` 及画风差异证据；启用画风迁移时记录 `visualLanguage` 的体积、材质、光影、边缘与纹理证据及角色分配，不默认手绘或任何特定画风。
- `sourceKvTone/sourceUiMode/targetKvTone`、`requestedUiMode`，以及 `source/targetHeroEdgeTone`、`candidateTargetUiModes/candidateSurfaceDepths`；半透明卡按实际合成表面判断 UI 模式，不从 KV 深浅或 Paint Alpha 直接推断。
- `uiContinuationPalette`、`highlightOnlyColors`、光照方向与材质空间模式；在既有 `kvAnalysis` 内保留有真实像素/区域依据的 `colorAnchors`，区分稳定环境、环境光、主体与反光。
- 按《配色方案提案》从锚点整理 3–5 个来源色及 `kvPrimaryHue`，生成规定的 4 套或 2 套完整只读方案，写入 `themeDecision.paletteProposal`；本阶段不复制页面、不替换 KV、不写 UI。

#### 通过条件

旧/新 KV tone 与原 UI mode 均有独立证据；新 KV 深浅由稳定环境场、暗部连续性、接缝、主体曝光性质和整页灰度共同支持，不由 KV 底部或中央高光单独决定。方案数量和角色内容符合《配色方案提案》，且每套均有来源锚点、代表 Hex、角色映射和风险说明。尚未得到用户选择时状态为 `awaiting-user-palette-choice`，在此处暂停后续写入。

### Phase 3：用户选定方案与换肤预检

完整执行《颜色决策规则》，形成 `themeDecision`。

#### 必须产出

- 展示 `themeDecision.paletteProposal` 中全部适用方案并等待用户选择。记录 `paletteSelection.status=selected`、方案 ID、原始指令和选择时间；用户未选择时禁止继续本 Phase 的配方冻结和任何 Figma 写入。
- 先依据原稿灰度与业务语义建立不含 Hue 的 `semanticPriorityMap`、`targetSalienceOrder`、`roleLightnessPlan` 和 `targetLuminanceTopology`，再把用户选定的关系色板展开为具体颜色配方。`targetUiMode` 和 `hueStrategy` 必须与选定方案一致，不由 AI 在预检中偷偷换成另一套。
- 表面、卡片氛围、文字阶梯、标题、关键数据、Icon 图形与底托、标签、Tab、小按钮和 CTA 的独立 Paint Recipe；表面由 `surfaceFamilyPlan` 引用 KV 锚点并明确家族/层级，其他角色在自己的 Recipe 引用来源；存在底托时，记录其颜色来源与承托关系。按《颜色决策规则》第 3.0 节冻结其中的 `hueRelationshipPlan`，将默认相近家族或有依据的撞色关系、面积主次及可见反差写进 `theme-consistency` 的 acceptance 和场景配方依赖，不能只登记“各角色都来自 KV”。
- `colorClarityPlan`：记录第 3.2 节浅→浅保留条件是否适用及对应范围，结合 KV 明暗/色彩力度与实际宿主确定按钮/CTA/Icon 的突出方向；记录页面各层、主要操作、文字与状态应达到的彩度、感知明度、受光感和对比关系及渲染检查方法；用户授权参考设计师版本时，包含同角色参考研究与可迁移范围。
- 按钮背景与浅/深文字的组合候选及真实背景对比度计划。
- 画风迁移时，`styleAdaptationPlan` 须包含原形状家族、风格载体、逐属性允许差异与裁切安全范围。
- 第 5.1 节 `ruleLedger`、全量 `colorManifest` 分类和覆盖差集校验通过；规则清单及目标在任何 UI 写入前冻结，场景引用同一指纹。
- 冻结 `visualUnits`、同色关系及对应对比关系；可比较的同宿主强弱顺序进入 `emphasisOrders`。整组配方的计划快照先通过关系预检，普通写入与局部修正继承同一套约束。
- `preflightThemeDecision=pass`，并绑定 `paletteSelection.schemeId` 与所选方案指纹。

#### 通过条件

用户已明确选定一个方案；其来源锚点、模式、表面与交互关系完整，CTA 和主要操作拥有正确显著性；色相不由题材或材质标签机械推出，旧 UI 色相未进入新方案。背景、卡片、主要按钮/CTA 的色相关系满足第 3.0 节；`complementary` 方案以用户固定候选约定和本次 `kvPrimaryHue` 为依据，不要求 KV 自身预先存在撞色，但必须保持对立色集中在按钮/CTA/突出高亮、表面环境家族统一。

### Phase 4：复制并替换 KV

按照《Figma 执行规范》只复制一次并替换副本 KV。本阶段不得写入任何 UI 颜色。

#### 必须产出 `mutationPlan`

- 原 Frame ID、副本 ID、位置、KV 替换记录和 `kvFitPlan`（实际窗口、等比缩放、主图边界、补底、节点/属性白名单和渲染证据）。
- `trialScenes` 与 `representativeNodeIds`：按完整局部场景覆盖实际角色及非等价材质、状态、背景，登记依赖、保护、写入通道和实例→代表映射；具体定义见《局部试色与执行工具》第 1 节。页面根/跨区域共享背景只允许预登记的确切 Paint 通道，不授权整树换色。
- 每个目标节点的 Paint 职责、目标 Recipe、允许差异和计划解绑理由。
- 映射未确认的可见 Paint 保持待处理，不用 `decoration` 等兜底角色自动上色；节点类型、宽度和旧色明度只能辅助检索，不能代替角色及材质职责判断。

#### 通过条件

原稿未改变；只有一个副本；新 KV 已按 `kvFitPlan.fitMode` 和选定尺度真实显示且无拉伸：`preserve-scale-bottom-crop` 允许仅截去下方超高部分，只有用户明确要求完整显示时才要求四边全部可见；Hero 外框、下方 UI 布局及功能叠层受保护；代表节点白名单在首次 UI 写色前确定。

### Phase 5：代表性试色与视觉门禁

首次 UI 颜色写入仅限预登记场景的代表节点、必要 Paint 后代及共享背景通道。背景、材质、文字、Icon 和操作状态组成完整局部场景后再视觉检查；禁止顺便循环换色其他实例。

按《局部试色与执行工具》第 1 节查看场景 1:1、灰度、模糊和缩略图；整页截图用于上下文和意外影响检查。只验已换肤场景的残留、层级、可读性和材质，未扩展旧皮肤不作为局部失败，也不声称整页通过。

按《颜色决策规则》第 3、5–8 节和《叠层合成审计》验证各实际角色，记录 `buttonCompositeReview` / `cardAtmosphereReview` 及针对问题的对照试色。按第 3.0 节将 KV 原始环境区域与实际背景、卡片和主要操作并排验证 `themeColorConsistencyAudit`，再看同一截图派生的彩色模糊图与缩略图，确认相近家族或撞色反差及面积分工实际成立；色相有疑点时比较该维度，不用按钮 V/字色比较代替。锚点、表面家族与色相关系计划引用纳入场景配方依赖。无改善时按执行工具规则重新诊断，不用数值、文字说明或单层颜色代替真实视觉证据。

画风迁移模式还须执行《画风迁移规则》的代表性检查：强调数字、Icon、按钮与 Tab、外卡/内卡、裁切边缘。仅完成换色或添加统一描边不能通过。

#### 通过条件

所有必需场景形成带真实截图和配方/依赖指纹的 `trialGates`，汇总为 `trialGateStatus=pass`。修正先更新计划，重新验受影响场景。代表试色和全页扩展不得发生在同一次写入调用中；PASS 的失效规则见《局部试色与执行工具》第 2 节。

### Phase 6：全页扩展

只有对应场景门禁通过且新鲜读回确认配方、映射与上下文指纹仍有效，才能将该方案扩展到剩余节点；历史 PASS 本身不够。

- 只按 `mutationPlan` 写入，不以坐标、面积、名称或旧色相进行全页猜测。
- 每次写入按批次保存前值、目标值并读回实际 `mutatedNodeIds`；超时/部分失败按执行工具第 3 节恢复，不盲目重复。解绑后重新映射并使相关门禁失效。
- 按完整区域组织扩展和截图，区域内相互依赖的角色处理完再判断视觉；每批属性检查仍立即执行。一次截图复用到同区域多项检查，发现问题在同一副本修正。
- 每个按钮和氛围实例都核对实际背景、祖先透明度及状态；材质相同不代表换到另一背景也合格。新发现的非等价配方须先补入代表白名单并单独试色通过，再扩展该组。

#### 通过条件

所有已识别角色已处理或有明确保护/跳过理由；扩展使用有效场景门禁及对应最终配方，没有冲突批次、待更新实例或未解决的失效场景。

### Phase 7：最终审计

完整执行[《验收规则》](validation.md)第 1–10 节，逐项填写第 11 节的唯一闸门清单；再执行第 5.3 节 finalize，生成 `finalAudit`。不得因入口不重复列出字段而省略检查。

本阶段必须覆盖原稿/副本结构、KV 适配、全部精确保护、文字与状态、真实合成材质、全 Paint/IMAGE 与渲染残留、逐实例上下文，以及完整五种视图和整页累计显著性。核对有效场景门禁、最终配方一致性和批次读回，无待更新实例、待恢复操作或未解决冲突；局部 PASS 不代替整页通过。

任一失败返回对应 Phase，只修正并重验受影响依赖，最终刷新相关审计；不沿用修正前的截图/PASS，不带已知失败交付。
