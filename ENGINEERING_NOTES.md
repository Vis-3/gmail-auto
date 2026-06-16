# Engineering Notes — Gmail Triage & Reply Assistant

This document covers the design decisions, difficulties encountered, bugs fixed, and improvements made over the course of building this project. Written for technical interviews and future reference.

---

## Design Decisions

### Two-Tier Classification

**Decision:** Run a rule-based filter before calling the LLM, not after.

**Reasoning:** The majority of emails I receive are clearly noise — job portal bulk sends, known newsletter domains, university announcements. Sending all of these to an LLM would be slow and wasteful. The rule-based tier handles these cases with zero latency and zero cost. The LLM only sees genuinely ambiguous emails where context and intent matter.

**Implementation:** `rule_based_filter()` returns a `Categories` enum value (or `None`). A `None` triggers the LLM. The LLM call returns a Pydantic `ClassificationOutput` with `category`, `confidence` (0–1), and `rationale`. Both paths return the same type, so the rest of the pipeline is agnostic to which tier made the decision.

**Trade-off:** Rule-based matching on domain strings is brittle — a new job portal won't be caught until I add it. This is acceptable for a personal tool; the LLM catches what the rules miss.

---

### Dynamic Sent-Mail Whitelist

**Decision:** Build the "conversation" category from Gmail's actual sent mail rather than maintaining a static contact list.

**Reasoning:** A static whitelist goes stale immediately. The people I'm expecting replies from are exactly the people I've emailed recently. A 30-day rolling window of sent-mail addresses is a living, accurate signal at near-zero cost.

**Implementation:** `get_sent_emails()` queries the Gmail API for sent messages in the last 30 days, extracts the `To` headers, and returns a set. This set is checked in the rule-based filter — if the incoming sender is in it, the email is classified as `conversation` with confidence 1.0.

**Trade-off:** The function makes one API call per sent email to fetch the `To` header. For someone with a high email volume this is slow. Left as a known limitation to address later (batch fetch or header-only query).

---

### Pydantic for Structured LLM Output

**Decision:** Use a Pydantic `BaseModel` with a `str(Enum)` category field and a `Field(ge=0, le=1)` constrained confidence float.

**Reasoning:** The LLM must return parseable, validated JSON. Pydantic gives free validation with clear error messages, and the Groq client's `response_model` parameter handles the JSON extraction automatically.

**Learning:** I learned that the field name in the Pydantic model must exactly match what the LLM returns. The initial schema had `categories` (plural) but the LLM returned `category` — this caused a `ValidationError` on every classification call until the field was renamed.

---

### SQLite State Machine

**Decision:** Track each email through its lifecycle using a `state` column in SQLite, with separate timestamp columns for each transition (`classified_at`, `notified_at`, `drafted_at`, etc.).

**Reasoning:** If the process crashes or is restarted, the state column tells us exactly where each email is. Timestamp columns give a full audit trail. The `message_id` primary key from Gmail prevents duplicate processing — if we try to insert an email we've already processed, the `PRIMARY KEY` constraint raises an exception and we `continue` to the next email silently.

**State machine:**
```
new → classified → notified → drafted → read_complete (terminal)
                             ↘ read_complete (no_reply)
```

---

### Concurrent Async Architecture

**Decision:** Run the Gmail poller and Telegram bot simultaneously using `asyncio.gather()` instead of threading or two separate processes.

**Reasoning:** Both the email poller and the Telegram bot are I/O-bound. `asyncio.gather` lets them run concurrently in one process with no synchronization complexity. The poller sleeps for an hour between runs; the bot stays alive listening for button taps indefinitely.

**Learning:** I initially called `asyncio.run(send_notification())` inside an `async def` function, which caused a "cannot run nested event loops" error. The fix was to `await send_notification()` directly — you only call `asyncio.run()` once, at the top level.

---

### Thread Context for Drafting

**Decision:** When drafting a reply, fetch the full email thread and include it in the LLM prompt.

**Reasoning:** Without thread context, the LLM has no idea what it's replying to. A "yes I'm available" reply makes no sense without the original scheduling request. Thread context allows the LLM to write a reply that actually addresses the conversation.

**Implementation:** `get_thread_messages()` fetches the full `threads.get` response, extracts each message's sender and body, and returns a list of dicts. The drafter joins these into a conversation history string and passes it to the LLM as the user message.

---

## Difficulties and Bugs

### OAuth 403 Access Denied

**Symptom:** The OAuth flow completed but Gmail API calls returned 403.

**Cause:** The Google Cloud project was set to "External" user type, and my Gmail address was not added to the list of test users.

**Fix:** Google Cloud Console → OAuth consent screen → Test users → added my Gmail address.

---

### Telegram `BadRequest: Can't parse entities`

**Symptom:** Telegram notifications failed with a parse error whenever the sender's email address appeared in the message.

**Cause:** Email addresses can contain `<` and `>` characters (e.g., `Name <email@domain.com>`). Telegram's HTML parse mode treats these as tag delimiters and rejects malformed HTML.

**Fix:** Switched from Markdown to HTML parse mode and wrapped all user-controlled strings (sender, subject, rationale) in `html.escape()`.

---

### Telegram `Chat not found`

**Symptom:** `send_message` raised "chat not found."

**Cause:** `TELEGRAM_CHAT_ID` was set to the bot's own ID, not my personal chat ID.

**Fix:** Sent a message to the bot, then fetched `https://api.telegram.org/bot{TOKEN}/getUpdates` to find the correct `chat.id` in the response.

---

### Telegram `Forbidden: bot can't send messages to bots`

**Symptom:** After fixing the above, still getting a Forbidden error.

**Cause:** I had copied the wrong `id` from the `getUpdates` response — the bot's `from.id` instead of the user's `message.chat.id`.

**Fix:** Used the `id` from the `chat` object in the message, not the `from` object.

---

### `StopIteration` on Sender Email

**Symptom:** `get_unread_emails()` crashed on some emails.

**Cause:** The code used `next(h['value'] for h in headers if h['name'] == 'Sender')`. Some emails don't have a `Sender` header — only a `From` header.

**Fix:** Changed to look for `'From'` header, which is present in all RFC 2822-compliant emails.

---

### `StopIteration` and `TypeError` on Email Body

**Symptom:** Crashes on emails with unusual MIME structure.

**Cause:** Multiple related issues:
1. Some emails have no `text/plain` part — only `text/html`
2. Some emails have no `parts` array at all (simple, non-multipart messages)
3. The base64 decode would crash if `body` was `None`

**Fix:** Added a chain of fallbacks:
- Try `text/plain` first
- Fall back to `text/html`
- Fall back to `None`
- Guard the base64 decode with `if body:`
- Guard the `parts` access with `if msg['payload'].get('parts'):`

---

### `get_thread_messages` Only Returning First Message

**Symptom:** Draft replies only had context from the first email in the thread.

**Cause:** The `return thread_list` statement was inside the `for` loop that iterated over thread messages. It returned after the first iteration.

**Fix:** Moved `return thread_list` to after the loop (fixed indentation by one level).

---

### SQL Schema Missing Comma

**Symptom:** `sqlite3.OperationalError: near "thread_id": syntax error` on first run.

**Cause:** The `CREATE TABLE` statement was missing a comma between `read_completed_at DATETIME` and `thread_id VARCHAR`.

**Fix:** Added the missing comma. Dropped and recreated the table.

---

### `emails[:0]` Bug

**Symptom:** The email poller ran without errors but never processed any emails.

**Cause:** During debugging, the list was sliced to `emails[:0]` (empty) to avoid processing real emails. The slice was left in production code.

**Fix:** Changed to `emails[:1]` for single-email testing, then removed the slice entirely for production.

---

### Telegram "Query is Too Old" / "Message is not Modified"

**Symptom:** Tapping an old notification or double-tapping a button caused unhandled exceptions that crashed the callback handler.

**Cause:** Telegram callback queries expire after ~60 minutes. Double-tapping the same button tries to edit the message to the same content, which Telegram rejects.

**Fix:** Wrapped `query.answer()` in a `try/except` that returns early. Both errors (`QueryTooOld` and `MessageNotModified`) are caught silently, which is the correct UX — if the callback is stale or already handled, do nothing.

---

### `dict` Variable Name Shadowing Built-in

**Symptom:** Subtle potential for confusion; linter warning.

**Cause:** A local variable was named `dict`, shadowing Python's built-in `dict` type within that scope.

**Fix:** Renamed to `email_dict`.

---

### Sent Email Set Initialized as Tuple

**Symptom:** `in` operator on `sent_email_set` checked tuple membership incorrectly (and performance was O(n) not O(1)).

**Cause:** `sent_email_set = ()` creates a tuple, not a set.

**Fix:** Changed to `sent_email_set = set()`.

---

## Improvements Made During Development

### Added `html.escape()` Everywhere

Initially applied only to the sender field. Extended to subject and rationale after realizing any of these could contain characters that break Telegram HTML parsing.

### Silent Duplicate Handling

Initially the email poller would log an error on duplicate `message_id` inserts and continue. Changed to a bare `except Exception: continue` after the `insert_email()` call — duplicates are expected and should be silent.

### Removed Debug Code

Several `print()` statements and `emails[:1]` slices left over from debugging were cleaned up before the first commit.

### Removed Unused Imports

`re`, `json`, and `google_auth_oauthlib` were imported but never used across multiple files. Removed to keep the code clean.

---

## Known Limitations

- **No auto-start:** The script must be started manually each morning. A Windows Task Scheduler entry or `systemd` unit would fix this.
- **Sent-mail whitelist is slow:** `get_sent_emails()` makes one API call per sent email to read the `To` header. A batch metadata fetch would be faster.
- **No reminder system:** Phase 5 (reminder scheduling via APScheduler) was intentionally skipped — checking Gmail drafts daily is sufficient for this use case.
- **No observability:** Sentry for error tracking and Langfuse for LLM call tracing would improve debuggability in a production setting, but add complexity not warranted for a personal tool.
- **Token expiry is silent:** If `token.json` is deleted or the refresh token is revoked, the script fails with an auth error and needs to be restarted to re-authorize via the browser flow.
