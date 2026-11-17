import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { SectionHead } from "@/components/landing/sections";
import { Reveal } from "@/components/ui/reveal";
import { allPosts, loadPage, pageImage } from "@/lib/site-content";
import { InvolvedBand } from "./involved-band";
import { PostCard } from "./post-card";
import { Inline, SiteImage, paras } from "./parts";

const pill =
  "inline-flex h-11 items-center gap-2 rounded-full bg-ink px-6 text-small font-medium text-white shadow-raised transition-[background-color,transform] duration-150 hover:bg-black active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

/** A short introduction to who we are, in the old site's own words, linking to /about. */
function WhoWeAre() {
  const { blocks } = loadPage("home");
  const eyebrow = blocks.find((b) => b.type === "heading" && b.level === 4);
  const title = blocks.find((b) => b.type === "heading" && b.level === 3);
  const welcome = paras(blocks).find((p) => p.text.startsWith("Welcome"));
  // The first list on the old home page is the picture slider's captions; the objectives list follows the welcome line.
  const objective = blocks.slice(welcome ? blocks.findIndex((b) => b === welcome) : 0).find((b) => b.type === "list");
  return (
    <section aria-labelledby="who-title" id="who" className="scroll-mt-8 grid items-center gap-8 md:grid-cols-2 md:gap-12">
      <Reveal from="left">
        <div className="overflow-hidden rounded-[1.75rem] shadow-lifted">
          <SiteImage pic={pageImage("home.jpg")!} alt="A golfer hitting out of a sand bunker" sizes="(min-width: 768px) 50vw, 100vw" className="object-cover" />
        </div>
      </Reveal>
      <div>
        <p className="text-caption font-semibold uppercase tracking-widest text-brand-ink">{eyebrow?.type === "heading" ? eyebrow.text : "Who we are"}</p>
        <h2 id="who-title" tabIndex={-1} className="mt-2 text-display outline-none sm:text-[2.5rem] sm:leading-[1.1]">{title?.type === "heading" ? title.text : "Who we are"}</h2>
        {welcome && <p className="mt-4 text-lead text-muted">{welcome.text}</p>}
        {objective?.type === "list" && <p className="mt-3 text-muted"><Inline text={objective.items[0]} /></p>}
        <Link href="/about" className={`${pill} mt-6`}>More about us <ArrowRight className="size-4" aria-hidden /></Link>
      </div>
    </section>
  );
}

const PROGRAMS = [
  { title: "Alumni Golf Challenge", image: "kenya-high-school-alumni.jpg", alt: "Four women golfers smiling together on a golf course" },
  { title: "Mentorship & Development", image: "mentorship.jpg", alt: "A speaker addressing a school hall full of students" },
] as const;

function FeaturedPrograms() {
  const { blocks } = loadPage("programs");
  const home = loadPage("home").blocks;
  const eyebrow = home.find((b) => b.type === "heading" && b.level === 4 && b.text.startsWith("We"));
  const title = home.find((b) => b.type === "heading" && b.level === 3 && b.text.startsWith("Featured"));
  const tagline = (name: string) => {
    const at = blocks.findIndex((b) => b.type === "heading" && b.text === name);
    return paras(blocks.slice(at + 1, at + 3))[0]?.text ?? "";
  };
  return (
    <section aria-labelledby="programs-title" id="programs" className="scroll-mt-8">
      <SectionHead eyebrow={eyebrow?.type === "heading" ? eyebrow.text : "Programs"} id="programs-title" href="/programs" linkLabel="All programs">
        {title?.type === "heading" ? title.text : "Featured Programs and Events"}
      </SectionHead>
      <ul className="grid gap-5 md:grid-cols-2">
        {PROGRAMS.map((p, i) => (
          <li key={p.title}>
            <Reveal from={i === 0 ? "left" : "right"} className="h-full">
              <article className="group relative flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface shadow-resting transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-lifted motion-reduce:transition-none">
                <div className="aspect-[3/2] overflow-hidden bg-sunken">
                  <SiteImage pic={pageImage(p.image)!} alt={p.alt} sizes="(min-width: 768px) 50vw, 100vw" className="h-full object-cover" />
                </div>
                <div className="flex flex-1 flex-col p-5 sm:p-6">
                  <h3 className="text-heading font-semibold">
                    <Link href="/programs" className="after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink">{p.title}</Link>
                  </h3>
                  <p className="mt-1 text-muted">{tagline(p.title)}</p>
                  <span className="mt-4 inline-flex items-center gap-1.5 text-small font-medium text-brand-ink group-hover:underline">Read More <ArrowRight className="size-4" aria-hidden /></span>
                </div>
              </article>
            </Reveal>
          </li>
        ))}
      </ul>
    </section>
  );
}

function LatestPosts() {
  const posts = allPosts().slice(0, 3);
  return (
    <section aria-labelledby="latest-title" id="latest" className="scroll-mt-8">
      <SectionHead eyebrow="Latest Blog" id="latest-title" href="/blog" linkLabel="All posts">
        Stories from the <em className="accent-serif">community</em>.
      </SectionHead>
      <ul className="grid gap-5 md:grid-cols-3">
        {posts.map((p) => (
          <li key={p.slug}><Reveal className="h-full"><PostCard post={p} /></Reveal></li>
        ))}
      </ul>
    </section>
  );
}

/** Everything the landing page shows below the schools and partners sections, in order. */
export function LandingMore() {
  return (
    <>
      <WhoWeAre />
      <FeaturedPrograms />
      <InvolvedBand />
      <LatestPosts />
    </>
  );
}
