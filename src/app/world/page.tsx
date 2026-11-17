import { permanentRedirect } from "next/navigation";

/**
 * The World Model now lives under Memory as Beliefs. Old /world bookmarks land
 * there (308). This runs after the auth proxy, like every other page.
 */
export default function WorldModelMoved(): never {
  permanentRedirect("/memory/beliefs");
}
