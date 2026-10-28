/* Evaluate this expression in functions.exec and inject its host APIs.
 * Retain the raw result first. Local retries never repeat the Figma capture.
 */
(async function transferThemeSnapshot({tools, store, load, callFigma, request,
    skillRoot, runWorkspace, expectedRoot, expectedNodes, python = 'python3',
    partManifestPath, partIndex, outputFile = 'source-before.json'}) {
  const quote = value => "'" + String(value).replace(/'/g, "'\\''") + "'";
  if (!runWorkspace.startsWith('/') || !skillRoot.startsWith('/') || !expectedRoot)
    throw Error('absolute workspace/skill paths and expectedRoot required');
  if (!/^[a-zA-Z0-9_.-]+\.json$/.test(outputFile)) throw Error('output must be a JSON basename');
  if (partManifestPath && (!partManifestPath.startsWith(runWorkspace + '/') || !Number.isInteger(partIndex) || partIndex < 0))
    throw Error('part requires a manifest in this workspace and an index');
  const key = 'kvss1:' + runWorkspace + ':' + expectedRoot + (partManifestPath ? ':part:' + partIndex : '');
  const identity = JSON.stringify({request, expectedRoot, expectedNodes, partManifestPath, partIndex, outputFile});
  let receipt = load(key);
  if (receipt && receipt.identity !== identity)
    throw Error('cached capture identity changed; do not reuse another source');
  if (!receipt) {
    receipt = {identity, state: 'capture-started', startedAt: Date.now()};
    store(key, receipt);
    const result = await callFigma(request);
    receipt = {...receipt, result, capturedAt: Date.now(), state: 'captured'};
    store(key, receipt);
  }
  if (!receipt.result)
    throw Error('capture outcome unknown; inspect the prior call, do not automatically recapture');
  const blocks = (receipt.result.content || []).filter(c => c.type === 'image' && c.mimeType === 'image/png');
  if (receipt.result.isError || blocks.length !== 1 || !blocks[0].data)
    throw Error('exactly one lossless KVSS PNG block required; capture retained');
  const data = blocks[0].data;
  const output = runWorkspace + '/' + outputFile;
  const command = [python, skillRoot + '/scripts/decode_theme_snapshot_png.py',
    '--stdin-base64-length', data.length, '--expected-root', expectedRoot,
    ...(expectedNodes === undefined ? [] : ['--expected-nodes', expectedNodes]),
    ...(partManifestPath ? ['--part-manifest',partManifestPath,'--part-index',partIndex] : []),
    '/dev/null', output].map(quote).join(' ');
  let proc;
  const started = Date.now();
  try {
    proc = await tools.exec_command({cmd: command, tty: true, yield_time_ms: 1000, max_output_tokens: 500});
    if (!proc.session_id) throw Error('decoder did not stay open');
    let ready = proc.output || '';
    for (let i = 0; !ready.includes('KVSS1_READY') && i < 3; i++) {
      const p = await tools.write_stdin({session_id: proc.session_id, chars: '', yield_time_ms: 1000, max_output_tokens: 500});
      ready += p.output || '';
      if (p.exit_code !== undefined) throw Error('decoder exited before raw input was ready');
    }
    if (!ready.includes('KVSS1_READY')) throw Error('raw input readiness not confirmed');
    let done;
    for (let i = 0; i < data.length; i += 24000) {
      const reply = await tools.write_stdin({session_id: proc.session_id,
        chars: data.slice(i, i + 24000), yield_time_ms: 1, max_output_tokens: 500});
      if (reply.exit_code !== undefined) {
        if (i + 24000 < data.length) throw Error('decoder exited before payload completed');
        done = reply;
      }
    }
    for (let i = 0; !done && i < 3; i++) {
      const reply = await tools.write_stdin({session_id: proc.session_id, chars: '', yield_time_ms: 1000, max_output_tokens: 500});
      if (reply.exit_code !== undefined) done = reply;
    }
    if (!done || done.exit_code !== 0) throw Error('snapshot decode failed or timed out; cached capture is reusable');
    const decoded = JSON.parse(done.output.trim());
    if (decoded.rootId !== expectedRoot || (expectedNodes !== undefined && decoded.nodes !== expectedNodes))
      throw Error('decoder receipt does not match the requested capture');
    const summary = {snapshotSaved: true, path: output, rootId: decoded.rootId,
      nodes: decoded.nodes, base64Characters: data.length, chunks: Math.ceil(data.length / 24000),
      captureMs: receipt.capturedAt - receipt.startedAt, transferAndDecodeMs: Date.now() - started};
    store(key, {...receipt, state: 'saved', summary});
    return summary;
  } catch (error) {
    // The decoder exits after 15 seconds without input; no orphaned raw TTY.
    store(key, {...receipt, state: 'transfer-failed', error: String(error), decoderSession: proc?.session_id});
    throw error;
  }
})
