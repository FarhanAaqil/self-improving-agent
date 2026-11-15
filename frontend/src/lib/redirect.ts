/** Where to go after logging in: only ever a page on this site, never another origin. */
export function safeNext(next: string | null | undefined): string {
  // "//host" and "/\host" are both read by browsers as a link to another site
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/'
  return next
}
