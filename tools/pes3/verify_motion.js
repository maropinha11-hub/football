#!/usr/bin/env node
/* Compare the laboratory decoder to the supplied v0.14 corpus, not hardware. */
"use strict";
const fs = require("node:fs"), zlib = require("node:zlib");
const crypto = require("node:crypto"), assert = require("node:assert/strict");
const motion = require("./motion.js");

function bufferArray(data) {
  return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
}

function readChannels(hex) {
  const data = Buffer.from(hex, "hex");
  assert.equal(data.length, 1536);
  const bones = [];
  for (let bone = 0; bone < 19; bone++) {
    const at = 16 + bone * 80, array = offset => [0, 1, 2, 3].map(i => data.readFloatLE(at + offset + i * 4));
    bones.push({rotationA: array(0), rotationB: array(16), translationA: array(32), translationB: array(48),
      rotationDuration: data.readFloatLE(at + 64), rotationElapsed: data.readFloatLE(at + 68),
      translationDuration: data.readFloatLE(at + 72), translationElapsed: data.readFloatLE(at + 76)});
  }
  return {clampedTime: data.readFloatLE(0), intervalIndex: data.readUInt32LE(4),
    channelCount: data.readUInt32LE(8), reserved: data.readUInt32LE(12), bones};
}

function channelBytes(state) {
  const data = Buffer.alloc(1536);
  data.writeFloatLE(state.clampedTime, 0); data.writeUInt32LE(state.intervalIndex, 4);
  data.writeUInt32LE(state.channelCount, 8); data.writeUInt32LE(state.reserved, 12);
  state.bones.forEach((b, i) => {
    const at = 16 + i * 80;
    [b.rotationA, b.rotationB, b.translationA, b.translationB].flat().forEach((v, j) => data.writeFloatLE(v, at + j * 4));
    [b.rotationDuration, b.rotationElapsed, b.translationDuration, b.translationElapsed]
      .forEach((v, j) => data.writeFloatLE(v, at + 64 + j * 4));
  });
  return data;
}

function poseBytes(pose) {
  const data = Buffer.alloc(608);
  pose.forEach((b, i) => [...b.rotation, ...b.translation].forEach((v, j) => data.writeFloatLE(v, i * 32 + j * 4)));
  return data;
}

function verify(bundlePath, vectorsPath) {
  const bundle = fs.readFileSync(bundlePath);
  const bundleSha = crypto.createHash("sha256").update(bundle).digest("hex");
  assert.equal(bundleSha, "c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5");
  const clips = motion.parseBundle(bufferArray(bundle));
  const stored = fs.readFileSync(vectorsPath);
  const data = JSON.parse(vectorsPath.endsWith(".gz") ? zlib.gunzipSync(stored, {maxOutputLength: 64 * 1024 * 1024}) : stored);
  assert.equal(clips.length, 1105); assert.equal(data.cases.length, 6565);
  assert.equal(data.captured_channels_pose.length, 132);
  let comparisons = 0;
  for (const [index, [clip, time, initial, expectedChannels, expectedPose]] of data.cases.entries()) {
    const state = motion.decode(clips[clip], time, readChannels(data.initials[initial]));
    assert.equal(channelBytes(state).toString("hex"), expectedChannels, "channels case " + index);
    assert.equal(poseBytes(motion.evaluate(state)).toString("hex"), expectedPose, "pose case " + index);
    comparisons += 2;
  }
  for (const [index, [channels, expected]] of data.captured_channels_pose.entries()) {
    assert.equal(poseBytes(motion.evaluate(readChannels(channels))).toString("hex"), expected, "captured case " + index);
    comparisons++;
  }
  let malformed = 0;
  for (const [offset, value] of [[8, 20001], [12, 0], [16, 15], [20, 20], [24, 160], [40, 0], [44, 0xffffffff]]) {
    const bad = Buffer.from(bundle); bad.writeUInt32LE(value, offset);
    assert.throws(() => motion.parseBundle(bufferArray(bad))); malformed++;
  }
  for (const offset of [17712, 17716, 17724, 17728]) {
    const bad = Buffer.from(bundle); bad.writeUInt32LE(0xffffffff, offset);
    assert.throws(() => motion.parseBundle(bufferArray(bad))); malformed++;
  }
  assert.throws(() => motion.parseBundle(bufferArray(bundle.subarray(0, -1)))); malformed++;
  const initial = readChannels(data.initials[0]), before = channelBytes(initial).toString("hex");
  assert.throws(() => motion.decode(clips[0], NaN, initial)); malformed++;
  assert.equal(channelBytes(initial).toString("hex"), before);
  const badChannels = {...initial, channelCount: 0};
  assert.throws(() => motion.evaluate(badChannels)); malformed++;
  return {schema_version: 1, result: "passed", animation_blocks: clips.length,
    pose_records: clips.reduce((n, c) => n + c.poses, 0), decode_pose_cases: data.cases.length,
    captured_channel_cases: data.captured_channels_pose.length, byte_buffer_comparisons: comparisons,
    rejected_invalid_inputs: malformed, bundle_sha256: bundleSha,
    scope: "JavaScript local decoder/evaluator against supplied v0.14 fixtures; no PS2 final hierarchy, mirror, clip blend, action selection or hardware equivalence."};
}

if (require.main === module) {
  if (process.argv.length !== 5) {
    console.error("Usage: node verify_motion.js TRACKS.fpsa animation_pose_vectors.json.gz OUTPUT.json");
    process.exit(2);
  }
  const result = verify(process.argv[2], process.argv[3]);
  fs.writeFileSync(process.argv[4], JSON.stringify(result, null, 2) + "\n", {flag: "wx"});
  console.log(JSON.stringify(result, null, 2));
}
module.exports = {verify};
