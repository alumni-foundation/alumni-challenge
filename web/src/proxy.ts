import { NextResponse, type NextRequest } from "next/server";
import { buildCsp, newNonce } from "@/lib/csp";
import { isPublicPath, isSignedOutOnly } from "@/lib/routes";

// Next only allows this file to export `proxy` and `config`, so the route lists live in lib/routes.
export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const signedIn = req.cookies.has("ac_refresh");

  if (!signedIn && !isPublicPath(pathname)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  if (signedIn && isSignedOutOnly(pathname)) {
    const url = req.nextUrl.clone();
    url.pathname = "/start";
    url.search = "";
    return NextResponse.redirect(url);
  }
  // Next reads the nonce from the request's CSP header and stamps it on its own inline scripts.
  const https = (req.headers.get("x-forwarded-proto")?.split(",")[0].trim() ?? req.nextUrl.protocol.replace(":", "")) === "https";
  const csp = buildCsp(newNonce(), { dev: process.env.NODE_ENV === "development", https });
  const headers = new Headers(req.headers);
  headers.set("content-security-policy", csp);
  const res = NextResponse.next({ request: { headers } });
  res.headers.set("content-security-policy", csp);
  return res;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icon.svg|images/|.*\\..*).*)"],
};
