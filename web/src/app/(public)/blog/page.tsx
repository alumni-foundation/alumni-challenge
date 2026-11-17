import type { Metadata } from "next";
import { PostCard } from "@/components/site/post-card";
import { Eyebrow } from "@/components/site/parts";
import { allPosts } from "@/lib/site-content";

export const metadata: Metadata = {
  title: "Blog",
  description: "Stories from Alumni Challenge: alumni, schools, teachers and students.",
};

export default function BlogPage() {
  const posts = allPosts();
  return (
    <div>
      <header className="mb-10">
        <Eyebrow>Latest Blog</Eyebrow>
        <h1 className="mt-2 text-title sm:text-display">Blog</h1>
      </header>
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {posts.map((p, i) => (
          <li key={p.slug}><PostCard post={p} priority={i < 3} /></li>
        ))}
      </ul>
    </div>
  );
}
