/**
 * The signed-in user, shared with every page.
 *
 * Each page previously carried its own `const USER_ID = 1`. That was invisible
 * while one person used the tool, but it meant a second operator would read and
 * write account 1's reels, posts and analytics rather than their own. The id now
 * comes from /api/me, which App resolves once before rendering any page.
 *
 * useCurrentUser throws when the provider is missing rather than falling back to
 * a default id: a missing provider is a wiring mistake, and silently operating on
 * somebody else's account is exactly the failure this replaced.
 */
import { createContext, useContext } from 'react'
import type { User } from './api/auth'

const CurrentUserContext = createContext<User | null>(null)

export function CurrentUserProvider({
  user,
  children,
}: {
  user: User
  children: React.ReactNode
}) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>
}

export function useCurrentUser(): User {
  const user = useContext(CurrentUserContext)
  if (!user) {
    throw new Error('useCurrentUser must be used within a CurrentUserProvider')
  }
  return user
}

/** Convenience for the common case - pages that only need the id. */
export function useUserId(): number {
  return useCurrentUser().id
}
