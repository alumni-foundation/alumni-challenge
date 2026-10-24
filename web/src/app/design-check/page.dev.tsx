"use client";

import { Compass, HeartHandshake, Search, ShieldCheck, Sparkles, Trophy } from "lucide-react";
import { Badge, Button, Card, Icon3D, type Icon3DSize, type Icon3DTone } from "@/components/ui";

// Development only: the file name page.dev.tsx is a route only under `next dev` (next.config.ts),
// so this page is not part of a production build. It shows the design system in both themes.

const SWATCHES = [
  "canvas", "surface", "sunken", "line", "line-strong", "ink", "muted", "faint",
  "brand", "brand-dark", "brand-soft", "brand-ink", "gold", "gold-soft", "verified", "ok", "warn", "side",
];
const TONES: Icon3DTone[] = ["ember", "gold", "moss", "sky", "ink"];
const SIZES: Icon3DSize[] = ["sm", "md", "lg"];
const GLYPHS = [Search, HeartHandshake, Trophy, ShieldCheck, Compass];

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
        <h3 className="text-heading">Icon3D: five tones, three sizes, pressed</h3>
        {SIZES.map((s) => (
          <div key={s} className="flex flex-wrap items-center gap-5">
            <span className="w-10 text-caption text-muted">{s}</span>
            {TONES.map((t, i) => (
              <Icon3D key={t} icon={GLYPHS[i]} tone={t} size={s} />
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

export default function DesignCheck() {
  return (
    <main id="main" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8">
      <h1 className="text-display">Design check</h1>
      <p className="text-small text-muted">Development only. Both themes are forced on their own panels, whatever the device setting.</p>
      <div className="grid gap-6 xl:grid-cols-2">
        <Theme theme="light" />
      </div>
    </main>
  );
}
