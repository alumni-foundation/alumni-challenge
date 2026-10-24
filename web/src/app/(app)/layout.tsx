"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { Alert, Button, Spinner } from "@/components/ui";
import { useMe, useMyProfile, useRoles } from "@/lib/api/hooks";
import { isAnyAdmin } from "@/lib/roles";
import { worksWithoutProfile } from "@/lib/routes";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const profile = useMyProfile();
  const roles = useRoles();
  const router = useRouter();
  const pathname = usePathname();
  const noProfile = profile.data === null;
  const onOnboarding = pathname === "/onboarding";
  // Staff accounts are separate from member accounts and may have no alumni profile. They can
  // work in their own area without one; the member pages still ask them to create it.
  // Staff also need to open other people's profiles (to review a report, or to verify someone).
  const viewingProfile = pathname.startsWith("/alumni/") && isAnyAdmin(roles.data);
  const staffArea = worksWithoutProfile(pathname) || viewingProfile;

  useEffect(() => {
    // Wait for the roles: they decide whether a missing member profile matters on this page.
    if (noProfile && !roles.isLoading && !onOnboarding && !staffArea) router.replace("/onboarding");
    if (profile.data && onOnboarding) router.replace("/start");
  }, [noProfile, roles.isLoading, onOnboarding, staffArea, profile.data, router]);

  if (me.isError || profile.isError) {
    return (
      <div className="mx-auto max-w-md p-8">
        <Alert>We couldn’t load your account. Check your connection and try again.</Alert>
        <Button className="mt-4" onClick={() => { void me.refetch(); void profile.refetch(); }}>Retry</Button>
      </div>
    );
  }
  if (me.isLoading || profile.isLoading || (noProfile && roles.isLoading)) return <Spinner label="Loading your account" />;
  if (noProfile) {
    if (onOnboarding) return <main id="main" className="mx-auto max-w-2xl p-4 sm:p-8">{children}</main>;
    return staffArea ? <AppShell profile={null}>{children}</AppShell> : <Spinner />;
  }
  if (!profile.data || onOnboarding) return <Spinner />;
  return <AppShell profile={profile.data}>{children}</AppShell>;
}
