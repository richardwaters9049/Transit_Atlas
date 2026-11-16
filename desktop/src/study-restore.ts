/** Commit restored application state only after the complete replay has verified. */
export function commitVerifiedRestore<T>(verify: () => T, commit: (verified: T) => void): T {
  const verified = verify();
  commit(verified);
  return verified;
}
