# NOTIFICATIONS — Triggers, Copy, Channels and Locale

**Status:** Canonical for REQ-10 and REQ-11 copy. `docs/background-jobs.md` owns when a
message is produced; this file owns what it says.
**Last updated:** 2026-11-22
**Visual template:** `docs/ui/emails/escalation-digest.html` and `.txt` (approved artifacts:
navy `#101820` header, gold `#E8AA23` brand line, white card on `#F8FAFC`, 12 px radius,
Tahoma/Arial, RTL).

---

## 1. Delivery rules

- Kinds and `dedupe_key` values are fixed by `NotificationLog` in `docs/domain-model.md` §2.12;
  reminder kinds by `ReminderLog` in §2.11. This document adds no new kinds.
- Channels: `email` (Hub mail API in production, MailHog in development) and `in_app`
  (rendered from `NotificationLog` rows, no separate table).
- **Recipient names and emails are never stored.** They are fetched from the Hub directory at
  send time (`docs/hub-contract.md` §4) and passed straight to the transport. If the directory
  is unavailable the message stays `pending` and the sweeper retries; it is never sent with a
  placeholder email.
- Locale: the recipient's language is the organization default (`ACADEMY_DEFAULT_LANGUAGE`),
  because no per-user preference is stored. `ar` uses `dir="rtl"`, `en` uses `dir="ltr"`; the
  same templates with the same variable set serve both.
- Every message carries a plain-text alternative. Subject ≤ 78 characters. No learner list,
  no grade or score, no video link — a link to the page, never to a media URL.
- Links are absolute: `{ACADEMY_HUB_ORIGIN}{ACADEMY_PROXY_PATH_PREFIX}` + the path below.
- Transactional only: no unsubscribe footer, no marketing copy, no tracking pixels.
- A `skipped` status is used when the recipient is inactive in the Hub or already completed the
  course at send time; the reason goes to `error_code` (`recipient_inactive`, `already_completed`).

## 2. Message catalogue

| Key | `NotificationLog.kind` | Recipient | Trigger | Channel(s) | `dedupe_key` |
|---|---|---|---|---|---|
| N-1 | `course_assigned` | learner | Assignment expansion creates an active enrollment | email + in_app | `assigned:<assignment_id>:<user_ref>` |
| N-2 | `course_completed` | learner | Enrollment reaches `completed` (lessons or override) | email + in_app | `completed:<enrollment_id>` |
| N-3 | `learner_completed` | manager | Same event as N-2, one per manager | in_app (+ email when the digest is due) | `learner_completed:<enrollment_id>:<manager_ref>` |
| N-4 | `due_minus_3` (`ReminderLog`) | learner | Active, incomplete, unacknowledged, `due_at − 3 days` | email | `reminder:due_minus_3:<enrollment_id>` |
| N-5 | `due` (`ReminderLog`) | learner | Same, on the due date | email | `reminder:due:<enrollment_id>` |
| N-6 | `due_plus_1` (`ReminderLog`) | learner | Same, one day after | email | `reminder:due_plus_1:<enrollment_id>` |
| N-7 | `manager_escalation` (`ReminderLog`) | manager | Enrollments at due+3, batched per manager | email + in_app | `escalation:<manager_ref>:<due_date>` |

Acknowledgement (`acknowledged_at`) suppresses N-4…N-6 only. Completion suppresses all
learner reminders for that enrollment.

## 3. Copy

Variables in `{}` are substituted from the database and the Hub directory. Arabic first;
English follows in the same row. `{org}` is the organization display name from settings.

| Key | العربية (subject / body) | English (subject / body) |
|---|---|---|
| N-1 | **تم إسناد دورة إليك: {course_title}** — «أُسندت إليك دورة {course_title} في أكاديمية {org}. موعد الاستحقاق: {due_date}.» + زر «ابدأ الدورة» (`/academy/my/`) | **A course has been assigned to you: {course_title}** — “{course_title} was assigned to you in {org} Academy. Due: {due_date}.” + button “Start course” (`/academy/my/`) |
| N-2 | **أكملت دورة {course_title}** — «أتممت دورة {course_title} بنجاح. يمكنك مراجعة محتواها في أي وقت.» + زر «الدورات التي أكملتها» (`/academy/my/?status=completed`) | **You completed {course_title}** — “You finished {course_title} successfully. You can revisit the content any time.” + button “Completed courses” |
| N-3 | **أكمل {learner_name} دورة {course_title}** — «أتمّ {learner_name} الدورة في {completed_date}.» + زر «تدريب فريقي» (`/academy/manage/team/`) | **{learner_name} completed {course_title}** — “{learner_name} finished the course on {completed_date}.” + button “Team training” |
| N-4 | **تبقّى 3 أيام لإكمال {course_title}** — «يستحق إكمال دورة {course_title} في {due_date}. تقدّمك الحالي {progress}%.» + زر «أكمل الآن» (`/academy/my/`) | **3 days left to finish {course_title}** — “{course_title} is due on {due_date}. Your progress is {progress}%.” + button “Continue” |
| N-5 | **دورة {course_title} مستحقة اليوم** — «موعد إكمال دورة {course_title} هو اليوم. تقدّمك الحالي {progress}%.» + زر «أكمل الآن» | **{course_title} is due today** — “{course_title} is due today. Your progress is {progress}%.” + button “Continue” |
| N-6 | **تأخّرت دورة {course_title} يوماً واحداً** — «كان موعد إكمال دورة {course_title} في {due_date}. أكملها لتجنّب التصعيد إلى مديرك.» + زر «أكمل الآن» | **{course_title} is one day overdue** — “{course_title} was due on {due_date}. Finish it to avoid escalation to your manager.” + button “Continue” |
| N-7 | as the approved artifact: **ملخّص تدريب الفريق المتأخر** — intro line with `{count}`, table of «الموظف / الدورة / الاستحقاق / أيام التأخر / التقدم», button «افتح صفحة تدريب فريقي» | **Your team's overdue training** — intro with `{count}`, table «Employee / Course / Due / Days overdue / Progress», button “Open team training” |

N-7 reuses `docs/ui/emails/escalation-digest.html` unchanged; only the rows and `{count}` are
dynamic. Its footer states the organization name and the current year, replacing the sample
“مثال تصميم يحتوي بيانات تجريبية”.

## 4. In-app rendering

`in_app` rows appear in the shell's notification list: unread first, newest first, 20 per page,
each with a relative time (`قبل 3 ساعات` / `3 hours ago`) and a link to the same target page.
Opening the target marks the row read (`read_at` is derived from `status` + a client-side
acknowledgement call — no new table, no new column). A failed send never appears as
delivered; it is retried by the sweeper.

## 5. Test obligations (T-021)

- For each key: rendered output contains no unreplaced `{variable}`, subject ≤ 78 chars, both
  languages present, direction attribute correct.
- Idempotency: calling the handler twice yields one row per `(dedupe_key, channel)`.
- Suppression: acknowledged enrollment sends no N-4…N-6; completed enrollment sends no
  reminders; inactive recipient sets `skipped` + `recipient_inactive`.
- Directory outage: message stays `pending` with `attempt_count` incremented, and no transport
  call is made without a real address.
- The digest renders the approved artifact byte-for-byte except for the injected rows, count
  and footer name.
