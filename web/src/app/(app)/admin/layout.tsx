"use client";

import { Alert, Button, EmptyState, LinkButton, Spinner } from "@/components/ui";
import { useRoles } from "@/lib/api/hooks";
import { isAnyAdmin } from "@/lib/roles";

/** Gate for everything under /admin. Pages inside still check their own, narrower permission. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const roles = useRoles();

  if (roles.isLoading) return <Spinner label="Checking access" />;
  if (roles.isError) {
    return (
      <div className="max-w-md space-y-4">
        <Alert>We couldn’t check your access. Check your connection and try again.</Alert>
        <Button variant="dark" onClick={() => void roles.refetch()}>Retry</Button>
      </div>
    );
  }
  if (!isAnyAdmin(roles.data)) {
    return (
      <EmptyState
        title="This area is for administrators"
        body="Your account doesn’t hold an admin role. If you think it should, ask a platform administrator."
        action={<LinkButton href="/home" variant="secondary">Back to home</LinkButton>}
      />
    );
  }
  return <div>{children}</div>;
}
