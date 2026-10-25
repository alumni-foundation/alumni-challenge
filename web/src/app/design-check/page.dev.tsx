"use client";

import { Bell, Compass, HeartHandshake, MessageCircle, Search, ShieldCheck, Sparkles, Trophy } from "lucide-react";
import { useState } from "react";
import { MessagesView } from "@/components/messages/messages-view";
import { SAMPLE_CONVERSATIONS, SAMPLE_MESSAGES } from "@/components/messages/sample";
import { DashboardBody } from "@/components/admin/dashboard/parts";
import { EMPTY_FIXTURE, MODERATOR_FIXTURE, PLATFORM_FIXTURE, SCHOOL_FIXTURE } from "@/components/admin/dashboard/fixtures";
import type { OverviewPeriod } from "@/lib/admin-overview";
import { Badge, Button, Card, Icon3D, type Icon3DSize, type Icon3DTone } from "@/components/ui";
import { CountBadge } from "@/components/ui/count-badge";

// Development only: the file name page.dev.tsx is a route only under `next dev` (next.config.ts),
// so this page is not part of a production build. It shows the design system in both themes.

const SWATCHES = [
  "canvas", "surface", "sunken", "line", "line-strong", "ink", "muted", "faint",
  "brand", "brand-dark", "brand-soft", "brand-ink", "gold", "gold-soft", "verified", "ok", "warn", "side",
];
const TONES: Icon3DTone[] = ["ember", "gold", "moss", "sky", "ink", "paper"];
const SIZES: Icon3DSize[] = ["sm", "md", "lg"];
const GLYPHS = [Search, HeartHandshake, Trophy, ShieldCheck, Compass];

/** The top-bar icon buttons, each in every state, so the look is settled before the message feature exists. */
function TopBarIcons() {
  const ICONS = [
    { name: "Notifications (bell)", icon: Bell },
    { name: "Messages (chat icon)", icon: MessageCircle },
  ];
  const states: { label: string; hover?: boolean; pressed?: boolean; count?: number; dot?: boolean }[] = [
    { label: "Default" },
    { label: "Hover", hover: true },
    { label: "Pressed", pressed: true },
    { label: "With count", count: 3 },
    { label: "Count 9+", count: 12 },
    { label: "With dot", dot: true },
  ];
  return (
    <section className="space-y-4">
      <h3 className="text-heading">Top-bar icon buttons</h3>
      <p className="text-small text-ink">Both are in the top bar. The chat icon opens /messages, which says messaging is coming (there is no messaging backend yet), so it never shows a count today.</p>
      {ICONS.map(({ name, icon }) => (
        <div key={name} className="space-y-2">
          <p className="text-small font-semibold">{name}</p>
          <ul className="flex flex-wrap gap-6">
            {states.map((s) => (
              <li key={s.label} className="flex flex-col items-center gap-2">
                <span className="relative grid size-11 place-items-center">
                  <Icon3D icon={icon} tone="paper" size="sm" hover={s.hover} pressed={s.pressed} />
                  <CountBadge count={s.count} dot={s.dot} />
                </span>
                <span className="text-caption text-muted">{s.label}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function Theme({ theme }: { theme: "light" }) {
  return (
    <div data-theme={theme} className="space-y-10 rounded-sheet border border-line bg-canvas p-5 text-ink sm:p-8">
      <h2 className="text-title">Light</h2>

      <section className="space-y-3">
        <h3 className="text-heading">Colour</h3>
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {SWATCHES.map((n) => (
            <li key={n} className="space-y-1">
              <span className="block h-12 rounded-control border border-line-strong" style={{ background: `var(--${n})` }} />
              <span className="block text-caption text-muted">{n}</span>
            </li>
          ))}
        </ul>
      </section>

      <TopBarIcons />
      <section className="space-y-4">
        <h3 className="text-heading">Messages screen (made-up sample conversations, this page only)</h3>
        <MessagesView conversations={SAMPLE_CONVERSATIONS} messages={SAMPLE_MESSAGES} />
        <h3 className="text-heading">Messages screen as real people see it today</h3>
        <MessagesView conversations={[]} />
      </section>

      <section className="space-y-3">
        <h3 className="text-heading">Type</h3>
        <p className="text-hero">Where alumni <em className="accent-serif">belong</em></p>
        <p className="text-display">Display 36 <em className="accent-serif">serif accent</em></p>
        <p className="text-title">Title 26</p>
        <p className="text-heading">Heading 20</p>
        <p className="text-lead">Lead 18: a calm, readable line that introduces a section.</p>
        <p className="text-body">Body 16: the text most screens are made of.</p>
        <p className="text-small text-muted">Small 14, muted</p>
        <p className="text-caption text-faint">Caption 12, faint</p>
      </section>

      <section className="space-y-3">
        <h3 className="text-heading">Buttons</h3>
        <div className="flex flex-wrap items-center gap-3">
          <Button>Get started</Button>
          <Button variant="secondary">Log in</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Remove</Button>
          <Button loading>Saving</Button>
          <Button disabled>Disabled</Button>
          <Button size="sm">Small</Button>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-heading">Cards and shadows</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(["resting", "raised", "lifted"] as const).map((e) => (
            <Card key={e} elevation={e}><p className="font-semibold capitalize">{e}</p><p className="mt-1 text-small text-muted">Border and shadow at this level.</p></Card>
          ))}
          <Card interactive><p className="font-semibold">Interactive</p><p className="mt-1 text-small text-muted">Lifts on hover.</p></Card>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-heading">Badges</h3>
        <div className="flex flex-wrap gap-2">
          <Badge>Neutral</Badge><Badge tone="ok">Verified</Badge><Badge tone="warn">Waiting</Badge>
          <Badge tone="brand">Open</Badge><Badge tone="gold">Partner</Badge><Badge tone="blue">School</Badge>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-heading">Icon3D: six tones, three sizes, pressed</h3>
        {SIZES.map((s) => (
          <div key={s} className="flex flex-wrap items-center gap-5">
            <span className="w-10 text-caption text-muted">{s}</span>
            {TONES.map((t, i) => (
              <Icon3D key={t} icon={GLYPHS[i % GLYPHS.length]} tone={t} size={s} />
            ))}
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-5">
          <span className="w-10 text-caption text-muted">press</span>
          <Icon3D icon={Sparkles} tone="ember" size="lg" />
          <Icon3D icon={Sparkles} tone="ember" size="lg" pressed />
          <Icon3D icon={Sparkles} tone="gold" size="lg" onClick={() => {}} label="Try pressing me" />
          <span className="text-small text-muted">normal, pressed, and a real button (click and hold)</span>
        </div>
      </section>
    </div>
  );
}

/** The staff dashboard drawn from typed sample answers (never shown in the real app). */
function DashboardCheck() {
  const [period, setPeriod] = useState<OverviewPeriod>("30d");
  const cases = [
    { name: "Platform admin", o: PLATFORM_FIXTURE, kind: "platform" as const, org: null },
    { name: "School admin (no report counts)", o: SCHOOL_FIXTURE, kind: "school" as const, org: "s1" },
    { name: "Moderator (report counts only)", o: MODERATOR_FIXTURE, kind: "moderator" as const, org: null },
    { name: "A brand-new platform (zeros, empty states)", o: EMPTY_FIXTURE, kind: "platform" as const, org: null },
  ];
  return (
    <section className="space-y-10">
      <h2 className="text-title">Admin dashboard (sample data)</h2>
      {cases.map((c) => (
        <div key={c.name} className="space-y-4" data-case={c.name}>
          <h3 className="text-heading">{c.name}</h3>
          <DashboardBody overview={{ ...c.o, period }} scope={{ kind: c.kind, organizationId: c.org }} period={period} onPeriod={setPeriod} fetching={false} nameOf={() => "Amina"} activityHref="/admin/activity" />
        </div>
      ))}
    </section>
  );
}

export default function DesignCheck() {
  return (
    <main id="main" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8">
      <h1 className="text-display">Design check</h1>
      <p className="text-small text-muted">Development only. Both themes are forced on their own panels, whatever the device setting.</p>
      <div className="grid gap-6 xl:grid-cols-2">
        <Theme theme="light" />
      </div>
      <DashboardCheck />
    </main>
  );
}
