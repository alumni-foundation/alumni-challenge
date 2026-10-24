/**
 * The Content-Security-Policy for pages. A fresh nonce per request lets Next's own inline scripts
 * run and nothing else: no injected script can. The browser only ever talks to this origin (the
 * API is reached by the server), so everything is 'self'.
 */
export function buildCsp(nonce: string, opts: { dev: boolean; https: boolean }): string {
  const directives = [
    "default-src 'self'",
    // 'strict-dynamic' lets the nonced scripts load their own chunks. React needs eval only in dev.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${opts.dev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    // Style attributes (style={{ width }} on avatars, bars) cannot carry a nonce.
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  if (opts.https) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

export const newNonce = () => btoa(crypto.randomUUID());
