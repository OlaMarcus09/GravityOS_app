-- Migration 0029 is already applied. Resolve pgcrypto from this project's
-- extensions schema without changing the applied migration file.
alter function private.zz_claim_founder_trial()
  set search_path = public, private, auth, extensions;
alter function private.claim_founder_trial_on_confirmation()
  set search_path = public, private, auth, extensions;
