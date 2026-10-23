import type { Metadata } from "next";
import Link from "next/link";
import { Prose } from "@/components/public/prose";

export const metadata: Metadata = { title: "Privacy" };

export default function Privacy() {
  return (
    <Prose title="Privacy" intro="What we keep about you, who can see it, and the choices you have.">
      <h2>What we keep</h2>
      <ul>
        <li>Your email address and a protected form of your password.</li>
        <li>
          Your profile: name, school, graduation year, country, profession, company, a short bio, your skills and
          interests, and your photo once photos are available.
        </li>
        <li>Your connections, the people you have blocked, and the reports you have made.</li>
        <li>
          The devices you are signed in on: the device name, its network address and when it was last used. You
          can see this list in your settings and sign a device out.
        </li>
        <li>A record of administrative actions, such as a school verifying a profile or an account being suspended.</li>
      </ul>

      <h2>Who can see your profile</h2>
      <p>
        You decide. <strong>Public</strong> profiles can be seen by anyone. <strong>Members only</strong> profiles
        can be seen by people who are signed in. <strong>Connections only</strong> profiles can be seen only by
        people you have connected with. <strong>Private</strong> profiles are not shown to others. Only Public and
        Members-only profiles appear in the directory search. Some details may be hidden from people who are not
        signed in, even on a Public profile.
      </p>

      <h2>Schools and moderators</h2>
      <p>
        A school’s administrators can verify alumni of their own school and see that school’s member list. Moderators
        can open a profile only while there is an open report about it.
      </p>

      <h2>Cookies</h2>
      <p>
        We use cookies only to keep you signed in. We do not use them for advertising.
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>Change what you share, or who sees it, at any time from your profile.</li>
        <li>Sign out of any device from your settings.</li>
        <li>
          To have your account removed or your data exported, <Link href="/contact">contact us</Link>. We are building
          these as self-service tools.
        </li>
      </ul>

      <h2>Questions</h2>
      <p>
        Write to us through the <Link href="/contact">contact page</Link>.
      </p>
    </Prose>
  );
}
