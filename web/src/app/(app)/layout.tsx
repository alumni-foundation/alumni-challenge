import { cookies } from "next/headers";
import { AppLayoutClient } from "./app-layout-client";

/** Reads the saved sidebar choice, so the server draws the sidebar at the right width on the first paint. */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const saved = (await cookies()).get("ac_sidebar")?.value;
  return <AppLayoutClient sidebar={saved === "expanded" || saved === "collapsed" ? saved : null}>{children}</AppLayoutClient>;
}
