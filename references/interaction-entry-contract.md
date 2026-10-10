# 功能入口保真

Phase 1W 在制定目标配方前读取并建立原稿清单；Phase 3 冻结进 `ruleLedger.sourceInteractions`；Phase 5/7 验证。只用同一次原稿快照和原生图，不增加 Figma 读取。该清单是 `sourceAudit` 的业务证据在账本中的冻结副本，不再维护另一套目标角色清单。

## 先识别入口，再决定颜色

逐卡对照原稿，记录主要/次级/三级操作、文字链接、纯图标入口及其真实宿主。名称、嵌套位置、旧色和 Figma 是否配置原型交互都不是充分依据。功能底板、装饰光影、结构蒙版分别辨认；在较小裁切框内实际承担按钮底板的渐变，不能因超出框的原始几何很大就判为卡顶装饰。

源入口职责和原有信息优先级优先于氛围淡化。原来有实体底板的入口，要保留可识别主体；原来只有文字或图标的入口，不凭空增加底板。次级操作不必升格为主要 CTA，也不必强制使用主要按钮色。透明度不是统一锁死或统一变淡：只要其变化削弱功能边界、状态或信息层级，便不通过。

## 冻结数据

在目标角色分类前形成 `sourceInteractions`，使用 `color_inventory(source).sourceHash`。它随整个账本被 manifest 的 `ruleLedgerHash` 绑定；目标配方不能为通过检查而删掉源入口或改写其业务职责。若发现源清单确有错误，先依据原稿更正并使旧预检/预演失效。

以下是字段示例，不是本任务的节点或通用色差阈值：

```json
{
  "schemaVersion": 1,
  "sourceHash": "原稿规范化快照哈希",
  "sourceReviewEvidence": "原生整页图及逐卡审查依据；包含纯图标入口核查",
  "entries": [{
    "rootId": "entry",
    "hostId": "card",
    "priority": "secondary",
    "affordance": "filled",
    "textNodeIds": ["label"],
    "carrierPaths": ["/nodes/body/props/fills/0/color"],
    "sourceEvidence": "原稿此区为有独立底板的次级入口；记录其相对标题/主要操作的层级",
    "boundaryPairId": "entry-body-to-card",
    "boundaryBasis": "主体和卡片的区分目标及原稿依据",
    "adjacentHostIds": ["card", "page"],
    "adjacentHostEvidence": "原生图中下边紧邻卡片，右边/上边紧邻页面；按实际裁切后轮廓判断",
    "boundaryComparisons": [
      {"hostId": "card", "pairId": "entry-body-to-card", "basis": "卡片侧实际主体和边缘",
       "sampleResponsibilities": {"card-body": "body", "card-edge": "edge", "card-weak": "weakest-body"}},
      {"hostId": "page", "pairId": "entry-body-to-page", "basis": "页面侧实际主体和边缘",
       "sampleResponsibilities": {"page-body": "body", "page-edge": "edge", "page-weak": "weakest-body"}}
    ],
    "visualReviewRuleId": "entry-review:entry"
  }],
  "nonInteractiveText": [{
    "nodeIds": ["title", "description"],
    "reason": "原稿静态标题与说明，不承担操作；不能包含入口文案"
  }]
}
```

- `priority` 为 `primary/secondary/tertiary`；`affordance` 为 `filled/outline/text/icon`。状态沿用既有状态登记；禁用入口仍在清单内，阈值按真实禁用状态另定，不强求主按钮显著性。
- `carrierPaths` 必须指向原稿实际可见的颜色通道，完整列出承担该入口主体/轮廓职责的所有 Paint 色标。填充按钮用非 TEXT 的 Fill，描边按钮用非 TEXT 的 Stroke；文字链接/纯图标用对应可见前景。正文对比不能冒充实体按钮边界。
- 功能底板的 manifest 角色使用 `button.* / cta.* / interaction.*`（已有英雄入口保护可用 `protected-hero-controls` 前缀）；文字/图标入口还允许 `text.* / icon.*`。不把源功能底板标为 `card.atmosphere` 或普通表面。
- 所有源可见 TEXT 必须在入口 `textNodeIds` 或有理由的 `nonInteractiveText` 中恰好出现一次。可复用现有文字清单和分组审查结果，不重新逐颜色分类。纯图标入口须通过逐卡原生图审查补齐；机器不能从没有交互标记的设计稿保证识别全部点击语义。
- 每个入口单独绑定 `contrast-baseline.verifier.relationships` 中的 `boundaryPairId`。实体按钮/描边入口必须为 `kind=button`，`nodeIds` 至少包含真实主体承载节点与宿主；文字链接可用 `text`，图标可用 `icon`。登记有依据的 `minimumContrast > 1` 或 `minimumDeltaE > 0` 及全部 `sampleIds`，不把“只有测量、没有接受条件”当作验收。不设跨页面统一数值；近零门槛不能替代清楚可辨的实际效果。
- 实体/描边入口必须显式登记 `adjacentHostIds`（包含 `hostId`）及 `adjacentHostEvidence`，按原生图的实际边界枚举全部相邻可见背景。不能从父节点层级推断唯一宿主；卡顶、跨卡边缘、异形入口尤其检查外侧页面。单一宿主也须明确登记，旧清单不默认通过。
- `boundaryComparisons` 为每个相邻宿主独立绑定一个 `kind=button` 的真实主体对比关系；主宿主使用原 `boundaryPairId`，其他宿主各有独立关系。每条关系有自己的接受条件、样本和 `basis`。`sampleResponsibilities` 的键必须与该关系 `sampleIds` 全集一致；实体入口至少有不同的 `body`、`edge` 样本，渐变另有 `weakest-body`；描边至少有 `edge`。数值检查仍由 contrast-baseline 计算。样本位于实际合成主体与相应邻接背景，边缘取轮廓内可稳定测量的位置；不把抗锯齿混合像素当成唯一主体，不用某个最好看的亮点代表整块按钮。最弱区域由原生预演核对，不假定某一个色标天然最弱。
- 每个实体/描边入口另有独立 `entry-review:<rootId>` 视觉规则，`kind=visual`、`applicable=true`、明确 `acceptance`，scope 包含入口和全部相邻宿主；在局部 1:1 场景逐一确认主体、边缘、文字和原信息层级。现有 finalize 要求这些额外规则全部有新鲜证据，整页笼统 PASS 不能覆盖缺失的入口规则。
- `button-salience` 与 `hierarchy` 视觉规则的 `scopeNodeIds` 必须显式包含每个入口根和全部相邻宿主。不通过“全页包含它”的笼统范围省掉局部检查。

## 执行与验收

`freeze_rule_ledger.py freeze`、`preflight_full.py` 的 static/full、`execution_audit.py finalize` 均调用 `interaction_entry_audit.py`。缺清单、角色误归装饰、只有文字关系、缺主体/相邻宿主/采样职责/独立局部视觉规则或漏掉源文字，会阻止通过。旧账本缺该字段必须补源审查，不能默认继承 PASS。

边界实际数值继续由现有 `contrast-baseline` 对同一冻结关系和新鲜样本计算，避免再造一套取样器。渐变、多层 Alpha 或有裁切的入口，须用包含真实不透明宿主的 1:1 原生图核对主体、边缘与文字覆盖区；孤立透明节点导出和少量最亮像素不能代替整块按钮。

对每个入口分别回答并记录到现有视觉场景检查：

1. 对所有相邻可见背景分别观察（包括卡外页面），忽略文案后，原来有底板的入口是否仍有完整可辨的操作区域？
2. 相对标题、邻近主要操作、标签和装饰，是否保留原有信息优先级？不能把次级按钮弱化成普通说明，也不能把它升级为最强焦点。
3. 为修复卡顶硬边而减弱的层是否确为装饰？是否连同按钮主体一起减弱？

数值通过仍须逐项视觉判断。`audit_delivered_theme.py` 只验证写入及预演一致性，不检查配方是否正确，不能代替 `finalize` 或入口层级验收。本门禁能拦住已记录职责与后续分类/验收不一致，不能证明人工源分类、采样位置和视觉判断永远正确。
