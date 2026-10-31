/**
 * Core API credentials for the server-side proxies. Server only: the tokens are not
 * NEXT_PUBLIC_ variables, and nothing the browser loads may import this file.
 * A missing token sends no header, so this is safe to ship before any enforcement.
 */
export function coreApiHeaders(
  write: boolean = false,
): Record<string, string> {
  const headers: Record<string, string> = {};
  const read = process.env.LILITH_OS_READ_TOKEN;
  if (read) headers["x-lilith-os-read"] = read;
  const token = process.env.LILITH_OS_WRITE_TOKEN;
  if (write && token) headers["x-lilith-os-write"] = token;
  return headers;
}
