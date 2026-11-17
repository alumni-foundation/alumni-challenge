import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Body, SiteImage } from "@/components/site/parts";
import { loadPost, postSlugs } from "@/lib/site-content";

// Every post is written to a static page at build time from its collected Markdown file.
export const dynamicParams = false;
export const generateStaticParams = () => postSlugs().map((slug) => ({ slug }));

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  if (!postSlugs().includes(slug)) return {};
  const post = loadPost(slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { type: "article", title: post.title, description: post.excerpt, publishedTime: post.date, images: [{ url: post.image.src, width: post.image.width, height: post.image.height }] },
  };
}

export default async function PostPage({ params }: Props) {
  const { slug } = await params;
  if (!postSlugs().includes(slug)) notFound();
  const post = loadPost(slug);
  return (
    <article className="mx-auto max-w-2xl">
      <Link href="/blog" className="inline-flex min-h-11 items-center gap-1.5 text-small font-medium text-brand-ink hover:underline">
        <ArrowLeft className="size-4" aria-hidden /> All posts
      </Link>
      <time dateTime={post.date} className="mt-4 block text-caption text-muted">{post.dateLabel}</time>
      <h1 className="mt-1 text-title sm:text-display">{post.title}</h1>
      <div className="mt-6 overflow-hidden rounded-[1.75rem] shadow-raised">
        <SiteImage pic={post.image} alt="" sizes="(min-width: 768px) 672px, 100vw" priority className="object-cover" />
      </div>
      <Body blocks={post.blocks} className="mt-8" />
    </article>
  );
}
