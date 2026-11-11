/**
 * CI ONLY: replace the Git LFS pointer for the Hsin avatar with a small, valid
 * synthetic GLB so the build, packaging and the end-to-end install exercise
 * real GLB checks. CI does not fetch LFS objects (the real model is 116 MB and
 * would exhaust the LFS bandwidth quota). Never used for a real release: a
 * real release is packaged from a checkout with `git lfs pull`, and
 * scripts/package-web.mjs refuses an LFS pointer.
 */
import { readFileSync, writeFileSync } from "node:fs";

const AVATAR = "public/assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm";
if (!process.env.CI) {
  console.error("ci-synthetic-avatar: refusing to run outside CI");
  process.exit(2);
}
const current = readFileSync(AVATAR);
if (!current.toString("utf8", 0, 64).startsWith("version https://git-lfs.github.com/spec/")) {
  console.log("ci-synthetic-avatar: the real avatar is present; leaving it unchanged");
  process.exit(0);
}

const pad4 = (b, fill) => (b.length % 4 ? Buffer.concat([b, Buffer.alloc(4 - (b.length % 4), fill)]) : b);
const json = pad4(Buffer.from(JSON.stringify({ asset: { version: "2.0", generator: "lilith-ci-synthetic" } })), 0x20);
const bin = Buffer.alloc(2 * 1024 * 1024, 0x2a); // 2 MiB, compressible like a real model
const total = 12 + 8 + json.length + 8 + bin.length;
const header = Buffer.alloc(12);
header.writeUInt32LE(0x46546c67, 0); // "glTF"
header.writeUInt32LE(2, 4);
header.writeUInt32LE(total, 8);
const chunk = (data, type) => {
  const h = Buffer.alloc(8);
  h.writeUInt32LE(data.length, 0);
  h.writeUInt32LE(type, 4);
  return Buffer.concat([h, data]);
};
writeFileSync(AVATAR, Buffer.concat([header, chunk(json, 0x4e4f534a), chunk(bin, 0x004e4942)]));
console.log(`ci-synthetic-avatar: wrote a ${total}-byte synthetic GLB in place of the LFS pointer`);
