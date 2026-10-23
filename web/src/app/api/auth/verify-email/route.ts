import type { NextRequest } from "next/server";
import { forwardPublicPost } from "@/lib/server/auth";

export const POST = (req: NextRequest) => forwardPublicPost(req, "auth/email/verify/confirm");
