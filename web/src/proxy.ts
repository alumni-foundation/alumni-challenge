import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PAGES = new Set(["/login", "/register"]);

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const signedIn = req.cookies.has("ac_refresh");
  const isPublic = PUBLIC_PAGES.has(pathname);

  if (!signedIn && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    if (pathname !== "/") url.searchParams.set("next", pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  if (signedIn && isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/home";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icon.svg|.*\\..*).*)"],
};
