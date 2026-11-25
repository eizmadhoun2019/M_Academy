# NOTIFICATIONS — Triggers, Copy, Channels and Locale

**Status:** Canonical for REQ-10, REQ-11 and REQ-26 copy. `docs/background-jobs.md` owns when a
message is produced; this file owns what it says.
**Last updated:** 2026-11-25
**Visual template:** `docs/ui/emails/escalation-digest.html` and `.txt` (approved artifacts:
navy `#101820` header, gold `#E8AA23` brand line, white card on `#F8FAFC`, 12 px radius,
Tahoma/Arial, RTL).

---

## 1. Delivery rules
- Kinds and `dedupe_key` values are fixed by `NotificationLog` in `docs/domain-model.md` §2.12;
  reminder kinds by `ReminderLog` in §2.11. This document adds no new kinds.
- Channels: `email` (SMTP transport by default; `console`/`locmem` in development/test; optional
  Hub adapter only when the integration is enabled) and `in_app` (rendered from
  `NotificationLog` rows, no separate table).
- **Recipients are local:** `recipient_user_id` provides the address, and
  `recipient_membership_id` provides the company context. Names/emails are not copied into
  business tables or logs. A missing/inactive account or membership sets `skipped` with
  `recipient_inactive`; it is never sent to a placeholder address.
- **Locale:** the recipient's `preferred_language`, falling back to the company's
  `default_language`, then `ACADEMY_DEFAULT_LANGUAGE`. `ar` uses `dir="rtl"`, `en` uses
  `dir="ltr"`; the same template and variable set serve both.
- **Company context:** `{org}` is the Organization display name; the sender name is the company
  `sender_name` (falling back to `ACADEMY_COMPANY_NAME`), and the From address is
  `ACADEMY_DEFAULT_FROM_EMAIL` in H1.5.
- **Dates/times** render in the company's time zone (D-038); the stored values remain UTC.
- Every message carries a plain-text alternative. Subject ≤ 78 characters. No learner list, no
  grade or score, no video link — a link to a page, never to a media URL.
- Links are absolute and built from `ACADEMY_PUBLIC_BASE_URL` (never the request `Host`) + the
  path below; the app prefix is `/academy`.
- Transactional only: no unsubscribe footer, no marketing copy, no tracking pixels.
- A `skipped` status is used when the message must not leave: inactive/removed recipient
  (`recipient_inactive`), already completed (`already_completed`), cancelled enrollment
  (`enrollment_cancelled`), or ids no longer resolving (`context_missing`). The reason goes to
  `error_code`.
- Copy is rendered when the send runs, from the ids in the row, not when queued: a message that
  waited still names the current course, and a reminder that became unnecessary is skipped
  rather than sent with stale facts.

## 2. Message catalogue

| Key | `NotificationLog.kind` | Recipient | Trigger | Channel(s) | `dedupe_key` |
|---|---|---|---|---|---|
| N-0a | `account_verify` | account | Registration/invitation requires email verification | email | `verify:<user_id>:<token_id>` |
| N-0b | `account_reset` | account | Password reset requested | email | `reset:<user_id>:<token_id>` |
| N-0c | `membership_invited` | invited email | Company invitation created | email | `invite:<invitation_id>` |
| N-1 | `course_assigned` | learner membership | Assignment expansion creates an active enrollment | email + in_app | `assigned:<assignment_id>:<membership_id>` |
| N-2 | `course_completed` | learner membership | Enrollment reaches `completed` (lessons or override) | email + in_app | `completed:<enrollment_id>` |
| N-3 | `learner_completed` | manager membership | Same event as N-2, one per manager | in_app (+ email when the digest is due) | `learner_completed:<enrollment_id>:<manager_membership_id>` |
| N-4 | `due_minus_3` (`ReminderLog`) | learner membership | Active, incomplete, unacknowledged, `due_at − 3 days` | email | `reminder:due_minus_3:<enrollment_id>` |
| N-5 | `due` (`ReminderLog`) | learner membership | Same, on the due date | email | `reminder:due:<enrollment_id>` |
| N-6 | `due_plus_1` (`ReminderLog`) | learner membership | Same, one day after | email | `reminder:due_plus_1:<enrollment_id>` |
| N-7 | `manager_escalation` (`ReminderLog`) | manager membership | Enrollments at due+3, batched per manager | email + in_app | `escalation:<manager_membership_id>:<local_due_date>` |

N-0a/N-0b are account-level (`recipient_membership_id` null); N-0c is sent to the invited
address before an account exists and is recorded against the company. They are not subject to
company reminder preferences.

Acknowledgement (`acknowledged_at`) suppresses N-4…N-6 only. Completion suppresses all learner
reminders for that enrollment. N-0a/N-0b are throttled at the API layer, not deduped by kind, so
a legitimate resend works while token replay does not.

## 3. Copy

Variables in `{}` are substituted from the database. Arabic first; English follows in the same
row. `{org}` is the company display name.

| Key | العربية (subject / body) | English (subject / body) |
|---|---|---|
| N-0a | **تحقق من بريدك في أكاديمية {org}** — «اضغط الرابط لتفعيل حسابك. ينتهي الرابط خلال 24 ساعة.» | **Verify your email for {org} Academy** — “Use the link to activate your account. It expires in 24 hours.” |
| N-0b | **إعادة تعيين كلمة المرور** — «طلبت إعادة تعيين كلمة المرور. ينتهي الرابط خلال ساعة. إن لم تطلب ذلك فتجاهل الرسالة.» | **Reset your password** — “You requested a password reset. The link expires in one hour. Ignore this message if it wasn't you.” |
| N-0c | **دعوة إلى أكاديمية {org}** — «دعاك {inviter_name} للانضمام. تنتهي الدعوة خلال 7 أيام.» | **Invitation to {org} Academy** — “{inviter_name} invited you to join. The invitation expires in 7 days.” |
| N-1 | **تم إسناد دورة إليك: {course_title}** — «أُسندت إليك دورة {course_title} في أكاديمية {org}. موعد الاستحقاق: {due_date}.» + زر «ابدأ الدورة» (`/academy/my/courses/`) | **A course has been assigned to you: {course_title}** — “{course_title} was assigned to you in {org} Academy. Due: {due_date}.” + button “Start course” (`/academy/my/courses/`) |
| N-2 | **أكملت دورة {course_title}** — «أتممت دورة {course_title} بنجاح. يمكنك مراجعة محتواها في أي وقت.» + زر «الدورات التي أكملتها» (`/academy/my/courses/?status=completed`) | **You completed {course_title}** — “You finished {course_title} successfully. You can revisit the content any time.” + button “Completed courses” |
| N-3 | **أكمل {learner_name} دورة {course_title}** — «أتمّ {learner_name} الدورة في {completed_date}.» + زر «تدريب فريقي» (`/academy/manage/reports/`) | **{learner_name} completed {course_title}** — “{learner_name} finished the course on {completed_date}.” + button “Team training” |
| N-4 | **تبقّى 3 أيام لإكمال {course_title}** — «يستحق إكمال دورة {course_title} في {due_date}. تقدّمك الحالي {progress}%.» + زر «أكمل الآن» (`/academy/my/courses/`) | **3 days left to finish {course_title}** — “{course_title} is due on {due_date}. Your progress is {progress}%.” + button “Continue” (`/academy/my/courses/`) |
| N-5 | **دورة {course_title} مستحقة اليوم** — «موعد إكمال دورة {course_title} هو اليوم. تقدّمك الحالي {progress}%.» + زر «أكمل الآن» | **{course_title} is due today** — “{course_title} is due today. Your progress is {progress}%.” + button “Continue” |
| N-6 | **تأخّرت دورة {course_title} يوماً واحداً** — «كان موعد إكمال دورة {course_title} في {due_date}. أكملها لتجنّب التصعيد إلى مديرك.» + زر «أكمل الآن» | **{course_title} is one day overdue** — “{course_title} was due on {due_date}. Finish it to avoid escalation to your manager.” + button “Continue” |
| N-7 | as the approved artifact: **ملخّص تدريب الفريق المتأخر** — intro line with `{count}`, table «الموظف / الدورة / الاستحقاق / أيام التأخر / التقدم», button «افتح صفحة تدريب فريقي» | **Your team's overdue training** — intro with `{count}`, table «Employee / Course / Due / Days overdue / Progress», button “Open team training” |

N-7 reuses `docs/ui/emails/escalation-digest.html` unchanged; only rows, `{count}`, language
direction and the footer company/year are dynamic. Sample demo text is never sent.

## 4. In-app rendering
`in_app` rows appear in the shell's notification list: unread first, newest first, 20 per page,
each with a relative time (`قبل 3 ساعات` / `3 hours ago`) and a link to the same target page.
Opening the target marks the row read (derived from `status` plus a client acknowledgement call —
no new table or column). A failed send never appears as delivered; the sweeper retries it.

## 5. Transport and failures
- `ACADEMY_MAIL_TRANSPORT` selects `smtp` (default), `console`, `locmem` (test) or `hub`
  (only when Hub is enabled). One `MailTransport` interface: `send(message) -> None`, raising
  `MailTransportError` on failure.
- SMTP uses the configured host/port/TLS/credentials and a bounded timeout; a permanent failure
  (5xx, invalid address) sets `failed` with `smtp_permanent` and is not retried forever; transient
  failures retry with backoff up to the configured attempts.
- Bounce/complaint handling is manual in H1.5: `ACADEMY_SUPPORT_EMAIL` receives reports, and a
  platform admin can mark an address unusable (documented operational runbook, T-034).
- Account mail is queued like other mail but is never blocked by company reminder settings.

## 6. Test obligations (T-032; auth mail in T-027)
- For each key: no unreplaced `{variable}`, subject ≤ 78 characters, both languages present,
  correct `dir`, correct company time zone, no media URL.
- Idempotency: calling the handler twice yields one row per `(dedupe_key, channel)`.
- Suppression: acknowledged enrollment sends no N-4…N-6; completed sends none; inactive/removed
  recipient sets `skipped` + `recipient_inactive`.
- Transport failure: transient → `pending` + attempts; permanent → `failed` + `smtp_permanent`;
  no transport call without a real address.
- Two companies with different languages and time zones render different subjects/dates from the
  same event; a duplicate beat tick writes nothing.
- The digest renders the approved artifact byte-for-byte except for injected rows, count,
  language direction and footer name.
