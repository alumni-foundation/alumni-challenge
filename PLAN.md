# ALUMNI CHALLENGE: MASTER BUILD PLAN

Scope: everything in the architecture document EXCEPT Kubernetes and M-Pesa.
Builder: solo. Status key: `[ ]` not done, `[x]` done.

## Rules

1. A phase is finished only when every box is ticked AND its **Gate** passes.
2. Nothing new is added to a phase mid-build. New ideas go to the "Later" list at the bottom.
3. If something is found missing, it gets written into this file the same day, in the right phase.
4. Every feature ships with tests. Auth, permissions, privacy, payments and capacity get the strictest tests.
5. Web and mobile never hold business rules. The API decides.
6. Database changes only through Alembic migrations.
7. "Build if justified" items: the tick means measured, decision written down (ADR), and built if the numbers demanded it.

---

## PHASE 0: Decisions and data model

- [ ] One-page product scope: who the users are, what each role does, what "launch" means
- [ ] Full ERD covering: users, sessions, organizations, memberships (user + org + role), alumni profiles, skills/professions/companies/interests reference data, schools, partners, connections, events, registrations, homecomings, sports, teams, golf entities, opportunities, mentorship, projects, contributions, impact records, conversations, messages, notifications, preferences, reports/moderation, audit log, files/media, membership, consent records
- [ ] Standard columns: id (UUID for external), created_at and updated_at on every table. created_by and updated_by (via a mixin) on tables people edit, and status only where a record has a real lifecycle. Applies to new tables from Oct 2026; existing tables are not retrofitted (owner decision, 23 Oct 2026)
- [ ] Permission matrix: role x action x resource, including ownership and organization boundaries
- [ ] Privacy rules: PUBLIC, MEMBERS_ONLY, CONNECTIONS_ONLY, PRIVATE, field by field
- [ ] Rules for time: store UTC, display Africa/Nairobi, event time handling
- [ ] Rules for deletion: soft delete vs hard delete, account deletion, data retention
- [ ] Endpoint classification for every planned endpoint (PUBLIC, AUTHENTICATED, ROLE_PROTECTED, OWNER_PROTECTED, ADMIN_ONLY)
- [ ] Tool choices written down: job queue, email provider, SMS provider, push (FCM/APNs), object storage, error tracking, container registry
- [ ] Naming conventions, API conventions (pagination, errors, filtering, sorting)
- [ ] Repo structure, branching, commit and review rules
- [ ] Data protection checklist (Kenya DPA): what data, why, legal basis, retention, ODPC registration
- [ ] Decide how existing alumni get in: self-signup, invite, bulk import by school admins, profile claiming
- [ ] Decide first-launch audience and the first schools/partners

**Gate:** ERD, permission matrix and privacy rules reviewed by you (and an independent reviewer). No table is built that is not on the ERD.

---

## PHASE 1: Foundation and deployment

- [ ] Backend repo: FastAPI, Pydantic settings, SQLAlchemy 2.0, Alembic, modular folder layout from the doc
- [ ] Docker images for: api, worker, realtime, scheduler, migrations
- [ ] Docker Compose for local development (api, worker, Postgres, Redis, mail catcher, object storage emulator)
- [ ] Health endpoints /health/live and /health/ready, designed so a non-critical outage does not pull the API out of service
- [ ] Three environments: development, staging, production, each with own database, storage, secrets, credentials
- [ ] Rule and tooling so production data is never copied to development; seed and fixture data for dev
- [ ] CI (GitHub Actions): lint, type check, unit tests, integration tests, dependency and secret scanning, Docker build
- [ ] Container registry, versioned images
- [ ] Coolify staging with deploy from main; production deploy path with one-step rollback
- [ ] Cloudflare: DNS, TLS, CDN, WAF basics, DDoS protection in front of staging
- [ ] Secrets handling: nothing in Git, secret scanning in CI, rotation procedure written
- [ ] Postgres automated backups to off-server storage
- [ ] Object storage versioning/protection turned on
- [ ] One full backup restore test, written up as a runbook
- [ ] Infrastructure configuration stored in Git

**Gate:** push to main deploys to staging with tests green; rollback tested; backup restore proven.

---

## PHASE 2: Platform baseline (observability, API standards, protection)

- [ ] Structured logging with request IDs, no secrets or personal data in logs
- [ ] Sentry for backend errors
- [ ] Prometheus metrics: request rate, errors, latency, DB connections, queue depth, cache hit rate
- [ ] Grafana dashboards and alerts
- [ ] OpenTelemetry tracing: client, API, database, Redis, worker, external provider
- [ ] API versioning under /api/v1, OpenAPI published as the shared contract
- [ ] Standard error format, pagination, filtering, validation
- [ ] Idempotency-Key support built once, reusable everywhere
- [ ] Rate limiting framework by IP, user and endpoint (auth, messaging, search, uploads, connection requests)
- [ ] Security headers, CORS rules, request size limits
- [ ] Database connection pooling settings sized as replicas x workers x connections
- [ ] Redis setup with clear rules for what may and may not be cached
- [ ] Job queue running with retries, dead-letter handling, scheduled jobs
- [ ] Domain event mechanism (UserRegistered, AlumniProfileCompleted, ConnectionCreated, EventRegistered, OpportunityPublished, MessageSent, PaymentCompleted, ProjectUpdated, ImpactRecorded)
- [ ] Audit log mechanism

**Gate:** you can watch a request travel through logs, metrics and a trace; a failing job retries and lands in dead-letter; limits block abuse in tests.

---

## PHASE 3: Identity and access

- [ ] Register, login, logout, argon2 hashing
- [ ] Email verification and password recovery
- [ ] Short-lived access tokens, rotating refresh tokens stored hashed, reuse detection
- [ ] Session and device list, revoke sessions
- [ ] Account status (active, suspended, deleted)
- [ ] Organizations and memberships; roles stored on the membership row (SUPER_ADMIN, ADMIN, MODERATOR, SCHOOL_ADMIN, PARTNER_ADMIN, EVENT_MANAGER, SPORTS_MANAGER, ALUMNI)
- [ ] One permission layer used by every endpoint
- [ ] First super-admin creation process (secure bootstrap)
- [ ] Email sending set up properly: SPF, DKIM, DMARC, templates
- [ ] Login abuse protection: lockouts, rate limits, credential stuffing defences
- [ ] Hooks ready for Google and Apple sign-in later
- [ ] Tests, including "School A admin cannot touch School B"

**Gate:** independent security review of the full auth flow; tests that actively try to break it.

---

## PHASE 4: Alumni, schools, partners, connections, files

- [ ] Alumni profile: professional info, skills, expertise, interests, bio, graduation year, country/location, school links, mentorship and participation preferences
- [ ] Reference data (skills, professions, companies) with cleanup rules
- [ ] Privacy levels enforced on the server, field by field
- [ ] Connections: request, accept, decline, remove, block; CONNECTIONS_ONLY privacy uses it
- [ ] Schools as communities: profile, admins, announcements, members, alumni engagement
- [ ] Partners: profile, admins, announcements, alumni benefits, sponsorship relationships
- [ ] Alumni directory with Postgres full-text search, filters, pagination
- [ ] File uploads: signed URLs, MIME and type checks, size limits, filename cleaning, private vs public storage, expiring links
- [ ] Malware scanning for uploads that need it
- [ ] Image variants (thumbnail, small, medium, large) through workers
- [ ] Moderation: report user/content/message, block, admin review queue, status history, suspension
- [ ] Bulk alumni import and profile claiming (per Phase 0 decision)
- [ ] Database indexes designed from the real queries here

**Gate:** privacy tests prove a hidden field never leaks through any endpoint, including search and lists.

---

## PHASE 5: Events, homecoming and registration

- [ ] Events: categories (homecoming, sports, CEO forums, executive, networking, mentorship, leadership, philanthropy), date/time, location, capacity
- [ ] School homecomings tied to schools
- [ ] RSVP and registration in a locked transaction (capacity check, lock, create, update, commit)
- [ ] Idempotent registration
- [ ] Waitlist and cancellation rules
- [ ] Attendee lists with privacy respected
- [ ] Reminders and notifications through the queue
- [ ] Load test: thousands registering for one event at once, zero overbooking

**Gate:** the concurrency test passes repeatedly. Sports and golf reuse this exact pattern.

---

## PHASE 6: Payments (provider-agnostic, no M-Pesa yet)

- [ ] Order, payment intent, payment record model
- [ ] Payment provider interface and a fake provider for testing
- [ ] Callback/webhook handler that is idempotent and verifies transactions
- [ ] Client-side confirmation never treated as final
- [ ] Payment state left pending when the provider is unavailable
- [ ] Paid event registration end to end on the fake provider
- [ ] Use cases wired: event and sports registration, donations, membership, merchandise
- [ ] Reconciliation report and audit trail

**Gate:** duplicate callbacks, replays and fake client confirmations cannot create false or duplicate payments.

---

## PHASE 7: Sports and golf

- [ ] Sports categories (golf, football, athletics, future sports)
- [ ] Registration, participants, teams, school representation
- [ ] Results and notifications
- [ ] Golf: events, players, schools, four-balls, handicaps, rounds, scores, leaderboards
- [ ] Four-ball allocation under concurrency
- [ ] Leaderboard updates

**Gate:** a full mock tournament runs from registration to final leaderboard.

---

## PHASE 8: Opportunities and mentorship

- [ ] Opportunities: jobs, internships, scholarships, business, leadership, training, networking
- [ ] Publishing, expiry and moderation of opportunities, kept separate from mentorship
- [ ] Mentor profiles, expertise, areas of support
- [ ] Mentorship requests, relationships, status
- [ ] Matching (simple rules first, hooks for smarter matching)

---

## PHASE 9: Projects, philanthropy, impact

- [ ] School and community projects, owners, participants, status
- [ ] Fundraising and contribution records (School -> Project -> Fundraising -> Contribution -> Impact)
- [ ] Impact metrics: schools engaged, students reached, projects supported, funds raised, mentors, volunteers, alumni participation
- [ ] Impact aggregation jobs

---

## PHASE 10: Notifications

- [ ] In-app, email and mobile push through workers
- [ ] User notification preferences
- [ ] Push content that avoids sensitive details
- [ ] Notifications stay queued if a worker or provider is down

---

## PHASE 11: Messaging and realtime

- [ ] Conversations and access checks
- [ ] Messages persisted before counted as sent
- [ ] WebSockets with identity checks, Redis coordination across nodes
- [ ] Read state, unread counts, blocking, message reporting
- [ ] Message rate limits and spam controls
- [ ] Realtime service deployable and scalable on its own
- [ ] WebSocket load test

**Gate:** no lost messages; nobody can read a conversation they are not in.

---

## PHASE 12: Membership and digital identity

- [ ] Membership status, numbers, benefits
- [ ] Digital alumni identity and verification
- [ ] QR membership card and event check-in
- [ ] Membership operations are idempotent

---

## PHASE 13: Executive network

- [ ] CEO/executive/founder groups and verification
- [ ] Forums, referrals, business opportunities
- [ ] Executive events

---

## PHASE 14: Admin and analytics

- [ ] Admin dashboard: users, organizations, roles, content, moderation, reports, suspensions
- [ ] Operational analytics (API, database, queue, WebSockets)
- [ ] Product analytics (members, active users, connections, messages, events, registrations, opportunities, sports)
- [ ] Impact analytics
- [ ] Data exports for admins
- [ ] Analytics failure never affects the core platform

---

## PHASE 15: Search and scale infrastructure

Each item: measure, write the decision, build if justified.

- [ ] Tune Postgres full-text search for alumni, schools, partners, events, opportunities, projects
- [ ] Dedicated search engine (OpenSearch/Elasticsearch) with index as a derived copy
- [ ] Search fallback if the engine is down
- [ ] Caching for public profiles, events, opportunities, metadata, with deliberate invalidation
- [ ] PgBouncer
- [ ] Read replicas and read routing
- [ ] Table partitioning review (messages, notifications, audit logs, analytics, payment events)
- [ ] Dedicated event platform (NATS JetStream or Kafka) decision
- [ ] Data warehouse decision
- [ ] Service extraction review: realtime, notifications, payments, search, media, analytics
- [ ] Failure isolation tests: email down, analytics down, search down, workers down, payment provider down
- [ ] Capacity plan from measured load (requests/sec, concurrent users, DB transactions/sec, WebSockets, queue throughput, storage, bandwidth, peak registrations)

**Gate:** every item has a recorded decision backed by numbers.

---

## PHASE 16: Web app (Next.js), built alongside phases 3 to 14

- [ ] Design system, layout, components
- [ ] Public site: home, institutions, partners, events, opportunities, impact
- [ ] SEO: server rendering, metadata, canonical URLs, structured data, sitemap, robots, Open Graph
- [ ] Authenticated app: dashboard, profile, directory, connections, schools, events, sports, opportunities, partners, projects, impact, messaging, notifications, membership, settings
- [ ] Admin screens
- [ ] Web deployed through Coolify with CDN
- [ ] Accessibility and performance pass
- [ ] End-to-end tests (Playwright) for the main journeys

---

## PHASE 17: Mobile app (Flutter), starts when API contracts stop changing

- [ ] Apple Developer and Google Play accounts set up
- [ ] API client generated from OpenAPI
- [ ] Auth and secure token storage
- [ ] Local caching, retry logic, network detection, image caching, drafts
- [ ] Screens for every module
- [ ] Push notifications (FCM/APNs)
- [ ] QR features
- [ ] Financial and sensitive actions stay server-authoritative
- [ ] Store listings, privacy labels, review submission
- [ ] Release pipeline and crash reporting

---

## PHASE 18: Legal, compliance, content

- [ ] Terms of service and privacy policy
- [ ] Consent records and cookie consent
- [ ] User data export and account deletion
- [ ] ODPC registration if required
- [ ] Moderation policy and community rules
- [ ] Support email and contact process

---

## PHASE 19: Hardening, testing, launch

- [ ] Full security audit: auth, permissions, uploads, rate limits, dependencies, secrets
- [ ] Penetration test of the main flows
- [ ] Load tests on real spike scenarios (homecoming launch, golf registration, large events)
- [ ] Backup restore drill on production-like data
- [ ] Incident runbook and on-call plan
- [ ] Monitoring and alerts live
- [ ] Documentation: README, API docs, runbooks, architecture decisions
- [ ] Seed real content: schools, partners, first events
- [ ] Staged production rollout, rollback tested
- [ ] Launch

---

## PHASE 20: After launch

- [ ] First-week monitoring and fixes
- [ ] User feedback collection
- [ ] Review the "Later" list

---

## ADDED DURING THE BUILD (rule 3: written down the day it was found)

Decisions of 23 Oct 2026 (owner):

- Build order changed from phase order, because bookings need these first: (1) platform
  fixes and role/seed tools, (2) files and uploads, (3) minimum notifications (email and SMS
  through the queue, behind a provider-agnostic interface with a logging fake until real
  keys exist), (4) events (Phase 5), (5) payments (Phase 6, fake provider first, then M-Pesa
  STK Push, then cards), (6) sports and golf (Phase 7), then the rest in phase order.
- M-Pesa moves from deferred to required for launch of paid events (still needs Daraja
  credentials and Safaricom approval; the whole flow must work on the fake provider first).
- Postgres 17 in development, CI and production.
- Guest booking and group payment: stop and ask the owner before building either.

Done, with the evidence that proves it:

- [x] Tests run on their own database and their own Redis index and refuse to run otherwise
  (`tests/_env.py`, `tests/test_test_environment.py`)
- [x] JWT leeway fixed at 10 seconds, as a constant, tested to reject tokens issued 2 minutes
  ahead (`tests/test_token_clock_tolerance.py`)
- [x] CI runs `alembic check` and an upgrade/downgrade/upgrade cycle (`.github/workflows/ci.yml`)
- [x] Staging and production refuse to start with a placeholder or short `SECRET_KEY`
  (`tests/test_settings_secret_key.py`)
- [x] Worker container has its own healthcheck (`arq --check`)
- [x] `seed-demo` replaces `create-dev-account`: one account per role, development only,
  password printed once and never stored (`tests/test_seed_demo.py`)
- [x] Organization user lookup by email: scoped, rate limited, audited, no existence leak
  (`tests/test_user_lookup.py`)
- [x] Grant and revoke roles with the rank rule; the last super admin cannot be revoked, also
  under concurrency (`tests/test_role_changes.py`)
- [x] Organization member list and school roster with a waiting-for-verification filter
  (`tests/test_org_members_roster.py`)
- [x] Storage interface with a local-disk backend (`tests/test_storage.py`)
- [x] Image uploads: type decided from content, picture rebuilt from pixels (EXIF/GPS, comments,
  appended bytes stripped), 25 megapixel cap, per-purpose policy, server-generated keys, per-user
  file cap, upload rate limit, a larger body limit on the upload route only
  (`tests/test_images.py`, `tests/test_file_upload.py`)
- [x] Permanent public URLs for logos and posters; five-minute signed URLs for private files;
  profile `avatar_url` only for viewers who may see the profile (`tests/test_file_serving.py`,
  `tests/test_file_attach.py`)
- [x] S3-compatible storage adapter for Cloudflare R2 behind `STORAGE_BACKEND`, tested against an
  emulator (`tests/test_storage.py`). Still to do with the real bucket: create it and its keys.
- [x] Real email: Resend and SMTP adapters (logging fake is the default), Mailpit in development,
  sent from the queue with backoff and a dead letter; no token or body logged outside development
  (`tests/test_mail.py`, `tests/test_domain_events.py`)
- [x] Change password (signs out other devices), data export, account deletion by anonymization
  (`tests/test_change_password.py`, `tests/test_data_export.py`, `tests/test_account_deletion.py`)
- [x] Rate limit on every write route, with a test that fails if a public one lacks its own;
  real visitor address behind Cloudflare (`tests/test_write_rate_limits.py`)
- [x] Sentry from environment variables with sensitive data scrubbed (`tests/test_sentry.py`)
- [x] Production image target, separate migration command, health checks incl. Redis status,
  backup and restore scripts rehearsed on the dev database, `docs/DEPLOYMENT.md` kept honest by
  `tests/test_deployment_doc.py`
- [ ] Deploy pipeline, registry, staging environment, Cloudflare rules, scheduled off-server
  backups: need the client's servers and accounts (see `docs/DEPLOYMENT.md`, section 10)
- [ ] Cleanup job for uploads that were never attached (they count against the per-user cap
  until the owner deletes them)
- [ ] Malware scanning and image variants (thumbnails): still the open Phase 4 items
- [ ] Events seeded by `seed-demo` (waits for Phase 5)
- [ ] Platform-wide user lookup by email for admins (not built; it cannot hide whether an
  address exists, so it needs an owner decision)

---

## DEFERRED BY DECISION (tracked, not forgotten)

- [ ] M-Pesa (Daraja) provider (now REQUIRED for launch of paid events, 23 Oct 2026; build after the fake provider): paybill/till, Safaricom go-live approval, real money flows. Until this is done, paid flows run on the fake provider only and cannot collect real money.
- [ ] Kubernetes, autoscaling, node autoscaling: only when measured load requires it

## LATER LIST

- Advanced recommendations, social feed algorithms, advanced fundraising accounting, multiple payment providers

---

## TRACEABILITY: every section of the architecture document and where it is built

| Doc section | Built in |
|---|---|
| 1 Executive summary, 2 Principles | Phases 0-2 |
| 3 High-level architecture | Phases 1, 15 |
| 4 Client architecture (web) | Phase 16 |
| 5 Mobile architecture | Phase 17 |
| 6 Backend architecture, 7 Structure | Phases 1, 2 |
| 8.1 Identity | Phase 3 |
| 8.2 Alumni | Phase 4 |
| 8.3 Schools | Phase 4 |
| 8.4 Partners | Phase 4 |
| 8.5 Events | Phase 5 |
| 8.6 Sports, 8.7 Golf | Phase 7 |
| 8.8 Opportunities, 8.9 Mentorship | Phase 8 |
| 8.10 Projects, 8.11 Impact | Phase 9 |
| 8.12 Membership | Phase 12 |
| 8.13 Executive network | Phase 13 |
| 9 Core data model, 10 Multi-organization | Phase 0, 3 |
| 11 PostgreSQL, 41 Indexing | Phases 0, 4, 15 |
| 12 DB scaling, 13 Pooling | Phases 2, 15 |
| 14 Redis, 15 Caching | Phases 2, 15 |
| 16 Object storage, 47 Media | Phase 4 |
| 17 CDN and edge | Phase 1 |
| 18 Search | Phases 4, 15 |
| 19 Async, 20 Events | Phase 2 |
| 21 Messaging | Phase 11 |
| 22 Notifications | Phase 10 |
| 23 Authentication, 24 Authorization | Phase 3 |
| 25 API security, 26 Rate limiting | Phases 2, 3, 19 |
| 27 File security | Phase 4 |
| 28 Payments and M-Pesa | Phase 6 (provider-agnostic); M-Pesa deferred |
| 29 Concurrency, 45 Idempotency | Phases 2, 5, 6, 7 |
| 30 QR identity | Phase 12 |
| 31 Analytics | Phase 14 |
| 32 Observability, 33 Health checks | Phases 1, 2 |
| 34 Docker, 35 Coolify | Phase 1 |
| 36 Kubernetes, 37 relationship | Deferred by decision |
| 38 CI/CD, 39 Environments, 40 Secrets | Phase 1 |
| 42 Partitioning | Phase 15 |
| 43 Disaster recovery | Phases 1, 19 |
| 44 Failure isolation | Phase 15 |
| 46 Mobile reliability | Phase 17 |
| 48 SEO | Phase 16 |
| 49 Privacy | Phases 0, 4, 18 |
| 50 Moderation, 51 Anti-abuse | Phases 3, 4 |
| 52 Capacity planning, 53 Scaling strategy | Phases 15, 19 |
| 54 Service extraction | Phase 15 |
| 55 API structure, 56 API docs | Phase 2 |
| 57 Tech stack | Phase 0 (tool choices) |
| 58 MVP vs future | Whole plan (MVP order = phase order) |
| 59-64 Position and outcome | Rules and Phase 21 |

---

## PHASE 21: Final completeness audit (last thing done)

- [ ] Reread the full architecture document line by line against this plan
- [ ] Every unchecked box either done or moved to Deferred with a reason
- [ ] Every doc section in the traceability table confirmed working in production
- [ ] All gates re-run once on production
- [ ] Sign off: platform complete


added features
USERS
  id (uuid, pk)
  email (unique)
  password_hash
  status (active | suspended | deleted)
  email_verified_at (nullable)
  created_at, updated_at

SESSIONS (refresh tokens)
  id (uuid, pk)
  user_id (fk -> users)
  refresh_token_hash
  device_label
  ip_address
  created_at, last_used_at, revoked_at (nullable)

ORGANIZATIONS
  id (uuid, pk)
  type (school | partner)
  name
  slug (unique)
  description
  logo_file_id (fk -> files, nullable)
  status (active | inactive)
  created_at, updated_at

MEMBERSHIPS  <- this is the role table, not a global role on users
  id (uuid, pk)
  user_id (fk -> users)
  organization_id (fk -> organizations, nullable)  -- null for platform-wide roles
  role (super_admin | admin | moderator | school_admin | partner_admin
        | event_manager | sports_manager | alumni)
  status (active | revoked)
  created_at
  UNIQUE(user_id, organization_id, role)

ALUMNI_PROFILES
  id (uuid, pk)
  user_id (fk -> users, unique)
  full_name
  bio
  graduation_year
  school_id (fk -> organizations, nullable)   -- self-declared
  country
  profession
  company
  verification_status (unverified | verified)
  verification_method (admin | peer | email_domain, nullable)
  verified_at (nullable)
  profile_visibility (public | members_only | connections_only | private)
  avatar_file_id (fk -> files, nullable)
  created_at, updated_at

SKILLS / INTERESTS (reference + join tables)
  skills (id, name unique)
  alumni_skills (alumni_profile_id, skill_id)
  interests (id, name unique)
  alumni_interests (alumni_profile_id, interest_id)

PEER_VOUCHES
  id (uuid, pk)
  vouched_user_id (fk -> alumni_profiles)
  voucher_user_id (fk -> alumni_profiles)
  created_at
  UNIQUE(vouched_user_id, voucher_user_id)

SCHOOL_EMAIL_DOMAINS   -- for auto-verify by institutional email
  id, organization_id (fk -> schools), domain (unique)

CONNECTIONS
  id (uuid, pk)
  requester_id (fk -> users)
  addressee_id (fk -> users)
  status (pending | accepted | declined | removed | blocked)
  created_at, updated_at
  UNIQUE(requester_id, addressee_id)

FILES
  id (uuid, pk)
  owner_user_id (fk -> users, nullable)
  storage_key
  mime_type
  size_bytes
  visibility (public | private)
  created_at

AUDIT_LOG
  id (uuid, pk)
  actor_user_id (fk -> users, nullable)
  action
  target_type, target_id
  metadata (jsonb)
  created_at


USER 1---1 ALUMNI_PROFILE
USER 1---N MEMBERSHIPS
USER 1---N SESSIONS
USER 1---N FILES (as owner)
USER 1---N CONNECTIONS (as requester or addressee)

ORGANIZATION 1---N MEMBERSHIPS
ORGANIZATION 1---N ALUMNI_PROFILES (via school_id, schools only)
ORGANIZATION 1---N SCHOOL_EMAIL_DOMAINS (schools only)

ALUMNI_PROFILE N---N SKILLS (via alumni_skills)
ALUMNI_PROFILE N---N INTERESTS (via alumni_interests)
ALUMNI_PROFILE N---N ALUMNI_PROFILE (via peer_vouches, self-referencing)





# Phase 0 — ERD and Permission Matrix

## Decisions locked

- Alumni onboarding: open self-signup, no invite/import
- Verification: passive, non-blocking (admin bulk-verify, peer vouch, or institutional email match)
- Peer-vouch threshold: 3 verified alumni from the same school
- Default `profile_visibility`: `members_only`
- Moderators see a profile only once it has an active report against it, not by default

---

## Core ERD

```
USERS
  id (uuid, pk)
  email (unique)
  password_hash
  status (active | suspended | deleted)
  email_verified_at (nullable)
  created_at, updated_at

SESSIONS (refresh tokens)
  id (uuid, pk)
  user_id (fk -> users)
  refresh_token_hash
  device_label
  ip_address
  created_at, last_used_at, revoked_at (nullable)

ORGANIZATIONS
  id (uuid, pk)
  type (school | partner)
  name
  slug (unique)
  description
  logo_file_id (fk -> files, nullable)
  status (active | inactive)
  created_at, updated_at

MEMBERSHIPS
  id (uuid, pk)
  user_id (fk -> users)
  organization_id (fk -> organizations, nullable)  -- null for platform-wide roles
  role (super_admin | admin | moderator | school_admin | partner_admin
        | event_manager | sports_manager | alumni)
  status (active | revoked)
  created_at
  UNIQUE(user_id, organization_id, role)

ALUMNI_PROFILES
  id (uuid, pk)
  user_id (fk -> users, unique)
  full_name
  bio
  graduation_year
  school_id (fk -> organizations, nullable)   -- self-declared
  country
  profession
  company
  verification_status (unverified | verified)
  verification_method (admin | peer | email_domain, nullable)
  verified_at (nullable)
  profile_visibility (public | members_only | connections_only | private)
  avatar_file_id (fk -> files, nullable)
  created_at, updated_at

SKILLS
  id (uuid, pk), name (unique)

ALUMNI_SKILLS
  alumni_profile_id (fk), skill_id (fk)

INTERESTS
  id (uuid, pk), name (unique)

ALUMNI_INTERESTS
  alumni_profile_id (fk), interest_id (fk)

PEER_VOUCHES
  id (uuid, pk)
  vouched_user_id (fk -> alumni_profiles)
  voucher_user_id (fk -> alumni_profiles)
  created_at
  UNIQUE(vouched_user_id, voucher_user_id)

SCHOOL_EMAIL_DOMAINS
  id (uuid, pk)
  organization_id (fk -> organizations, schools only)
  domain (unique)

CONNECTIONS
  id (uuid, pk)
  requester_id (fk -> users)
  addressee_id (fk -> users)
  status (pending | accepted | declined | removed | blocked)
  created_at, updated_at
  UNIQUE(requester_id, addressee_id)

FILES
  id (uuid, pk)
  owner_user_id (fk -> users, nullable)
  storage_key
  mime_type
  size_bytes
  visibility (public | private)
  created_at

REPORTS
  id (uuid, pk)
  reporter_user_id (fk -> users)
  target_type (profile | message | content)
  target_id (uuid)
  reason
  status (open | reviewing | resolved | dismissed)
  reviewed_by (fk -> users, nullable)
  created_at, resolved_at (nullable)

AUDIT_LOG
  id (uuid, pk)
  actor_user_id (fk -> users, nullable)
  action
  target_type, target_id
  metadata (jsonb)
  created_at
```

### Relationships

```
USER 1---1 ALUMNI_PROFILE
USER 1---N MEMBERSHIPS
USER 1---N SESSIONS
USER 1---N FILES (as owner)
USER 1---N CONNECTIONS (as requester or addressee)
USER 1---N REPORTS (as reporter)

ORGANIZATION 1---N MEMBERSHIPS
ORGANIZATION 1---N ALUMNI_PROFILES (via school_id, schools only)
ORGANIZATION 1---N SCHOOL_EMAIL_DOMAINS (schools only)

ALUMNI_PROFILE N---N SKILLS (via alumni_skills)
ALUMNI_PROFILE N---N INTERESTS (via alumni_interests)
ALUMNI_PROFILE N---N ALUMNI_PROFILE (via peer_vouches, self-referencing)
```

### Notes

- `ORGANIZATIONS` merges schools and partners with a `type` column — matches the doc's multi-org model, and lets a future org type slot in without a schema change.
- Verification lives on `ALUMNI_PROFILES`, not `USERS` — identity (can log in) is separate from trust in the claimed school affiliation.
- `MEMBERSHIPS.organization_id` nullable is how `super_admin`/`admin` work platform-wide while other roles stay scoped. Every permission check reads off this table.

---

## Permission matrix

Roles: `super_admin` and `admin` are platform-wide. `moderator` is platform-wide but report-scoped for profile visibility. `school_admin`, `partner_admin`, `event_manager`, `sports_manager` are scoped to one organization via their membership row. `alumni` is the base role every signed-up user has for their own account.

| Resource | Action | anonymous | alumni (self) | alumni (other) | school_admin (own org) | partner_admin (own org) | moderator | admin / super_admin |
|---|---|---|---|---|---|---|---|---|
| User account | register | allow | n/a | n/a | n/a | n/a | n/a | n/a |
| User account | login / logout | allow | allow | n/a | n/a | n/a | n/a | n/a |
| User account | view own sessions / revoke | deny | allow | deny | deny | deny | deny | allow (any, audited) |
| User account | suspend / delete | deny | deny | deny | deny | deny | allow (reason required, audited) | allow |
| Alumni profile | create / edit own | deny | allow | deny | deny | deny | deny | allow (any, audited) |
| Alumni profile | view | public fields only | allow (own); others per visibility | per `profile_visibility` | per visibility, plus own school roster always visible | deny (not their org) | only if profile has an open report | allow |
| Alumni profile | set `verification_status` | deny | deny | deny | allow (own school's alumni only) | deny | deny | allow |
| Peer vouch | create | deny | allow (must be verified self) | n/a | n/a | n/a | deny | deny |
| Organization | create | deny | deny | n/a | deny | deny | deny | allow |
| Organization | edit own org profile | deny | deny | n/a | allow (own org only) | allow (own org only) | deny | allow |
| Organization | assign school_admin / partner_admin | deny | deny | n/a | deny | deny | deny | allow |
| Membership | grant event_manager / sports_manager for own org | deny | deny | n/a | allow (own org) | allow (own org) | deny | allow |
| Connections | send / accept / remove own | deny | allow | deny | deny | deny | deny | allow (support only, audited) |
| Report | file | deny | allow | n/a | n/a | n/a | n/a | n/a |
| Report | review / action | deny | deny | deny | deny | deny | allow | allow |
| Audit log | view | deny | deny | deny | allow (own org actions only, filtered) | allow (own org actions only, filtered) | allow (moderation-scoped) | allow (full) |

### Rules that apply across every row

1. Ownership always wins over role, except where explicitly blocked (e.g. a user cannot self-verify).
2. Organization scope is enforced by `organization_id` matching at the query level, not by role name alone. `school_admin` for School A querying School B's data must be rejected server-side. This is the Phase 3 gate test case.
3. `super_admin` is reserved for irreversible or platform-critical actions: deleting organizations, changing another admin's role, platform-wide settings. Routine operations go through `admin`.
4. Anonymous access is limited to registration, login, and whatever public pages Phase 16 decides are SEO-facing — not covered by this table.
5. Every `deny` here must be a 403 at the API layer, tested explicitly. Frontend checks are UX only, never the enforcement.

---

## Still open for Phase 0

- [ ] Field-by-field privacy rules sheet: for each of `public` / `members_only` / `connections_only` / `private`, which exact fields on `ALUMNI_PROFILES` are shown
- [ ] Rules for time (UTC storage, Africa/Nairobi display)
- [ ] Deletion rules (soft vs hard delete, retention)
- [ ] Endpoint classification list for every planned v1 endpoint
- [ ] Tool choices: job queue, email provider, SMS provider, push, object storage, error tracking, container registry
- [ ] Kenya Data Protection Act checklist
