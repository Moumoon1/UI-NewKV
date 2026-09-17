/* Paste this helper into use_figma, then:
 * return await snapshotThemeTree(figma, "ACTUAL_FRAME_ID");
 * Read-only: no font loads, component edits, clones or Paint writes.
 * Save the complete returned JSON locally; errors prevent audit acceptance.
 */
async function snapshotThemeTree(api, rootId) {
  const fields = [
    "type", "name", "visible", "locked", "opacity", "blendMode",
    "x", "y", "width", "height", "rotation", "relativeTransform",
    "constraints", "cornerRadius", "topLeftRadius", "topRightRadius",
    "bottomLeftRadius", "bottomRightRadius", "cornerSmoothing", "clipsContent",
    "layoutMode", "primaryAxisSizingMode", "counterAxisSizingMode",
    "primaryAxisAlignItems", "counterAxisAlignItems", "layoutWrap",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "itemSpacing", "counterAxisSpacing", "itemReverseZIndex", "strokesIncludedInLayout",
    "layoutAlign", "layoutGrow", "layoutPositioning", "layoutSizingHorizontal",
    "layoutSizingVertical", "minWidth", "maxWidth", "minHeight", "maxHeight",
    "fills", "strokes", "effects", "fillStyleId", "strokeStyleId", "effectStyleId",
    "strokeWeight", "strokeAlign", "strokeCap", "strokeJoin", "strokeMiterLimit",
    "strokeTopWeight", "strokeRightWeight", "strokeBottomWeight", "strokeLeftWeight",
    "dashPattern", "isMask", "maskType", "booleanOperation", "vectorPaths",
    "vectorNetwork", "arcData", "characters", "fontName", "fontSize", "fontWeight",
    "textStyleId", "textAlignHorizontal", "textAlignVertical", "textAutoResize",
    "lineHeight", "letterSpacing", "textCase", "textDecoration", "paragraphSpacing",
    "paragraphIndent", "listSpacing", "hangingPunctuation", "hangingList",
    "textTruncation", "maxLines", "autoRename", "componentProperties",
    "componentPropertyReferences", "boundVariables", "explicitVariableModes",
  ];
  const textFields = ["fontName", "fontSize", "fontWeight", "fontStyle", "textStyleId", "fillStyleId", "fills",
    "lineHeight", "letterSpacing", "textCase", "textDecoration", "paragraphSpacing",
    "paragraphIndent", "listOptions", "listSpacing", "indentation", "hyperlink", "textWrapStyle",
    "textDecorationStyle", "textDecorationOffset", "textDecorationThickness",
    "textDecorationColor", "textDecorationSkipInk"];
  const result = { schemaVersion: 1, collectorVersion: 1, rootId,
    capturedAt: new Date().toISOString(), nodes: [], errors: [] };
  const serial = (value) => {
    if (typeof value === "symbol") return { $mixed: true };
    if (value === undefined) return { $undefined: true };
    if (typeof value === "number" && !Number.isFinite(value)) {
      throw new Error("Nonfinite numeric property");
    }
    if (Array.isArray(value)) return value.map(serial);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.keys(value).map(k => [k, serial(value[k])]));
    }
    return value;
  };
  const fail = (id, property, error) => result.errors.push({id, property, error: String(error)});
  const previousSkip = api.skipInvisibleInstanceChildren;
  try {
    // Full integrity snapshots must include hidden instance children.
    api.skipInvisibleInstanceChildren = false;
    const root = await api.getNodeByIdAsync(rootId);
    if (!root) throw new Error("Root not accessible: " + rootId);
    const stack = [root];
    while (stack.length) {
      const node = stack.pop();
      const row = {id: node.id, parentId: node.parent?.id ?? null, children: [], props: {}};
      for (const key of fields) {
        if (!(key in node)) continue;
        try { row.props[key] = serial(node[key]); }
        catch (error) { fail(node.id, key, error); }
      }
      if (node.type === "TEXT") {
        try {
          // Store each property as its own run list. A color split must not change
          // typography runs or make an unchanged protected text range look modified.
          row.props.textRuns = {};
          const segments = node.getStyledTextSegments(textFields);
          for (const field of textFields) {
            const runs = [];
            for (const segment of segments) {
              const value = serial(segment[field]);
              const last = runs[runs.length - 1];
              if (last && last.end === segment.start && JSON.stringify(last.value) === JSON.stringify(value)) {
                last.end = segment.end;
              } else runs.push({start: segment.start, end: segment.end, value});
            }
            row.props.textRuns[field] = runs;
          }
        } catch (error) { fail(node.id, "textRuns", error); }
      }
      if (node.type === "INSTANCE") {
        try { row.props.mainComponentId = (await node.getMainComponentAsync())?.id ?? null; }
        catch (error) { fail(node.id, "mainComponentId", error); }
      }
      if ("children" in node) {
        const children = [...node.children];
        row.children = children.map(c => c.id);
        stack.push(...children.reverse());
      }
      result.nodes.push(row);
    }
  } catch (error) { fail(rootId, "tree", error); }
  finally {
    try { api.skipInvisibleInstanceChildren = previousSkip; }
    catch (error) { fail(rootId, "restoreSkipInvisibleInstanceChildren", error); }
  }
  // Absolute bounds depend on the permitted root translation. Capture them as
  // separate screenshot evidence when needed; local geometry above is audited.
  return result;
}

if (typeof module !== "undefined") module.exports = { snapshotThemeTree };
