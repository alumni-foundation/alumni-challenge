import type { Metadata } from "next";
import Link from "next/link";
import { Prose } from "@/components/public/prose";

export const metadata: Metadata = { title: "Community rules" };

export default function CommunityRules() {
  return (
    <Prose title="Community rules" intro="We want this to feel like a school reunion: warm, honest and safe for everyone.">
      <h2>Be yourself</h2>
      <p>Use your real name and tell the truth about your school, your years there and your work. Do not pretend to be someone else.</p>

      <h2>Be kind</h2>
      <ul>
        <li>No harassment, bullying, threats or hate towards anyone.</li>
        <li>No sexual or violent content.</li>
        <li>Respect people who do not want to connect. If someone says no, leave it there.</li>
      </ul>

      <h2>Keep it safe</h2>
      <ul>
        <li>Do not share other people’s private details without their permission.</li>
        <li>No scams, spam or unwanted selling.</li>
        <li>Vouch only for people you really know went to your school.</li>
      </ul>

      <h2>If something is wrong</h2>
      <p>
        Use <strong>Report</strong> on a profile and tell us what happened. Moderators read every report. You can also
        <strong> Block</strong> anyone to stop them contacting you.
      </p>

      <h2>What happens if rules are broken</h2>
      <p>
        We may remove content, suspend an account while we look into it, or close it. See the{" "}
        <Link href="/terms">terms of use</Link> for more.
      </p>
    </Prose>
  );
}
