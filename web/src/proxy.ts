import { NextResponse, type NextRequest } from "next/server";
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
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icon.svg|images/|.*\\..*).*)"],
};
