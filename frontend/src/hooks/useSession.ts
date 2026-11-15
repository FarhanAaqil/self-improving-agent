import { useQuery } from '@tanstack/react-query'
import { getMe } from '../api/client'

/** The signed-in account (if any) and how this server authenticates. */
export function useSession() {
  const query = useQuery({ queryKey: ['me'], queryFn: getMe, staleTime: 60_000, retry: false })
  const me = query.data
  return {
    ...query,
    user: me?.user ?? null,
    mode: me?.auth,
    signupsOpen: me?.signups_open ?? true,
    isOperator: Boolean(me?.operator),
    // Pull requests use the operator's GitHub token, so only the operator sees the button
    canOpenPrs: Boolean(me?.can_open_prs),
    // Accounts are required and nobody is signed in
    needsLogin: me?.auth === 'accounts' && !me.user,
  }
}
