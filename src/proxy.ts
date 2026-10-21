import { NextResponse, type NextRequest } from "next/server";

// Signed-out visitors go straight to the sign-in page, which brings them back afterwards. (The cookie's signature is
// checked on every page; this only spares a wasted render.) /api/py checks the cookie itself.
export function proxy(req: NextRequest) {
  if (req.cookies.has("ms_session")) return NextResponse.next();
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = req.nextUrl.pathname === "/" ? "" : `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!login|_next|api/py|icon|favicon).*)"],
};
