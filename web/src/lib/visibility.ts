import type { Visibility } from "@/lib/api/types";

/** The four privacy choices, each with the one plain sentence people see next to it. */
export const VISIBILITY_OPTIONS: { value: Visibility; label: string; help: string }[] = [
  { value: "public", label: "Public", help: "Anyone can see your profile, even without an account." },
  { value: "members_only", label: "Members only", help: "Only people who are signed in can see it. This is the usual choice." },
  { value: "connections_only", label: "Connections only", help: "Only people you have connected with. You won’t appear in search." },
  { value: "private", label: "Private", help: "Only you. You won’t appear in search." },
];
