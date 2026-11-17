import Link from "next/link";
import type { Post } from "@/lib/site-content";
import { SiteImage } from "./parts";

/** A blog post in a list: picture, date, title, the first lines. The whole card is one link. */
export function PostCard({ post, priority = false }: { post: Post; priority?: boolean }) {
  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface shadow-resting transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-lifted motion-reduce:transition-none">
      <div className="aspect-[3/2] overflow-hidden bg-sunken">
        <SiteImage pic={post.image} alt="" sizes="(min-width: 1024px) 384px, (min-width: 640px) 50vw, 100vw" priority={priority} className="h-full object-cover" />
      </div>
      <div className="flex flex-1 flex-col p-5">
        <time dateTime={post.date} className="text-caption text-muted">{post.dateLabel}</time>
        <h3 className="mt-1 text-heading font-semibold">
          <Link href={`/blog/${post.slug}`} className="after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink">
            {post.title}
          </Link>
        </h3>
        <p className="mt-2 line-clamp-3 text-small text-muted">{post.excerpt}</p>
        <span className="mt-4 inline-flex items-center text-small font-medium text-brand-ink group-hover:underline">Continue reading</span>
      </div>
    </article>
  );
}
