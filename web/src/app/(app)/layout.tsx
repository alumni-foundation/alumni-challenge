"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { Alert, Button, Spinner } from "@/components/ui";
import { useMe, useMyProfile } from "@/lib/api/hooks";
import { isStaffArea } from "@/lib/routes";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const profile = useMyProfile();
  const router = useRouter();
  const pathname = usePathname();
  const noProfile = profile.data === null;
  const onOnboarding = pathname === "/onboarding";
  // Staff accounts are separate from member accounts and may have no alumni profile. They can
  // work in their own area without one; the member pages still ask them to create it.
  const staffArea = isStaffArea(pathname);

  useEffect(() => {
    if (noProfile && !onOnboarding && !staffArea) router.replace("/onboarding");
    if (profile.data && onOnboarding) router.replace("/start");
  }, [noProfile, onOnboarding, staffArea, profile.data, router]);

  if (me.isError || profile.isError) {
    return (
      <div className="mx-auto max-w-md p-8">
        <Alert>We couldn’t load your account. Check your connection and try again.</Alert>
        <Button className="mt-4" onClick={() => { void me.refetch(); void profile.refetch(); }}>Retry</Button>
      </div>
    );
  }
  if (me.isLoading || profile.isLoading) return <Spinner label="Loading your account" />;
  if (noProfile) {
    if (onOnboarding) return <main id="main" className="mx-auto max-w-2xl p-4 sm:p-8">{children}</main>;
    return staffArea ? <AppShell profile={null}>{children}</AppShell> : <Spinner />;
  }
  if (!profile.data || onOnboarding) return <Spinner />;
  return <AppShell profile={profile.data}>{children}</AppShell>;
}
