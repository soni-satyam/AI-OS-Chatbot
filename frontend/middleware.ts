// frontend/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that DON'T require auth
const PUBLIC_ROUTES = ["/login", "/signup"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Allow public routes through
  if (PUBLIC_ROUTES.some((route) => pathname.startsWith(route))) {
    return NextResponse.next();
  }

  // Check for token in cookies (more secure than localStorage for middleware)
  // OR check the Authorization header
  const token = request.cookies.get("auth_token")?.value;

  if (!token) {
    // Redirect to login, remembering where they wanted to go
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Apply middleware to all routes except static files and API routes
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};