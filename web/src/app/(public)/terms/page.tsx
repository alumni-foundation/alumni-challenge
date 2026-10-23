import type { Metadata } from "next";
import Link from "next/link";
import { Prose } from "@/components/public/prose";

/*
 * LEGAL REVIEW REQUIRED BEFORE LAUNCH. This is a plain-language draft written from what the
 * product does today. It claims only features that exist now: it does not promise data export
 * or account deletion, which the backend has not shipped. Have a lawyer review it, and update it
 * whenever those features (or photos, messaging, events or payments) arrive.
 */

export const metadata: Metadata = { title: "Terms of use" };

export default function Terms() {
  return (
    <Prose title="Terms of use" intro="The simple rules for using Alumni Challenge.">
      <h2>Who can use it</h2>
      <p>
        Alumni Challenge is for people who are 18 or older. When you create an account you confirm that you
        are. You are responsible for what happens under your account, so keep your password to yourself.
      </p>

      <h2>Your profile</h2>
      <p>
        Share only what is true and what you are comfortable sharing. You choose who can see your profile:
        everyone, signed-in members only, only the people you are connected with, or no one. You can change
        this whenever you like.
      </p>

      <h2>Being verified</h2>
      <p>
        A Verified mark means a school has confirmed that someone went there. It can come from a school email
        address, from a school administrator, or from vouches by verified alumni of the same school. Please
        vouch only for people you genuinely know.
      </p>

      <h2>How we expect you to behave</h2>
      <p>
        Be respectful and honest. Our <Link href="/community-rules">community rules</Link> explain what is not
        allowed. If you break them, we may remove content, or suspend or close your account.
      </p>

      <h2>Reports and suspension</h2>
      <p>
        Anyone can report a profile. Moderators review reports and may suspend an account while they look into
        it. A suspended account cannot be used until it is reinstated.
      </p>

      <h2>Changes to the service</h2>
      <p>
        We are still adding features. We may change or remove parts of the service, and we may update these
        terms. If a change matters, we will tell you.
      </p>

      <h2>Questions</h2>
      <p>
        If anything here is unclear, <Link href="/contact">get in touch</Link>.
      </p>
    </Prose>
  );
}
