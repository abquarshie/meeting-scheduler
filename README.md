# Meeting Scheduler

Schedules the midweek and weekend meetings: who takes which part, slips (S-89), schedule sheets, the S-140, public
talks and WhatsApp cards. Two front ends share one Neon PostgreSQL database:

- **Next.js app** (`src/`): the web app deployed on Vercel. Next.js App Router, Tailwind CSS, Prisma.
- **Streamlit app** (`app.py`): the original app. It keeps working against the same database.

The scheduling rules and every document (slips, sheets, S-140, cards, letters, backups) stay in Python. On Vercel they
run as one Python function, `api/py.py`, which the Next.js pages call at `/api/py?op=...`. `api/st_shim.py` lets the
existing modules (`db.py`, `picking.py`, `sheets_pdf.py`, ...) run there unchanged without Streamlit.

## Deploy on Vercel

1. Import the repository in Vercel. The framework is detected as Next.js; `vercel.json` adds the Python function.
2. Set these environment variables (see `.env.example`):
   - `DATABASE_URL`: the Neon connection string (the pooled one).
   - `SESSION_SECRET`: a long random string, for example from `openssl rand -base64 32`.
   - `APP_PASSWORD`: the shared sign-in password. Or `APP_USERS` as `Name=password;Name2=password2` for one
     password per person; names then show in the change log. End someone's password with `:weekend`
     (`Kofi=his-password:weekend`) to limit him to weekend meetings: he can create, edit, undo, delete and print
     weekend schedules and use Public talks, and nothing else. Don't give him `APP_PASSWORD`, since the shared
     password signs in anyone under any name with full access.
3. Deploy.

The function installs the packages in `api/requirements.txt` (not the root `requirements.txt`, which is the Streamlit
app's). Keep the two in step when adding a package, and keep Streamlit out of the function: it would push it past
Vercel's 500 MB limit.

Files uploaded through the web app (workbook PDF, blank forms, a backup to restore) must be under about 4 MB, the
Vercel request limit.

## Sign-in

Five wrong passwords lock sign-in for a minute. The count lives in the `settings` table (`signin_fails`,
`signin_locked`), so it holds across Vercel's instances. Someone who signs in with their own `APP_USERS` password stays
signed in for 30 days; with the shared `APP_PASSWORD`, for 7.

## Reminders and calendar links

**Reminders** (in the menu, and linked from Home when anyone has a part in the next 7 days) lists everyone with a part
in the next 7 or 14 days, with a ready WhatsApp message and a **Calendar link**. The app keeps no participant phone
numbers: the WhatsApp button opens WhatsApp with the message ready, and you pick the chat. (The only number it keeps is
the Talk Coordinator's, for the public talk letters.)

A calendar link is `/cal/<id>-<signature>.ics` (10 characters of signature; older 20-character links still work), signed with `SESSION_SECRET` (changing the secret retires every link).
It needs no sign-in, so a phone or Google Calendar ("From URL") can subscribe and pick up new and changed parts by
itself, with an alert the evening before. The meeting start times for it are set on the Reminders page
(`midweek_time`, `weekend_time`); without them the entries are all-day. The **iPhone link** button copies the same
address as `webcal://…`: tapped on an iPhone it offers "Subscribe", where the `https://` link only imports the parts
once. A weekend-only sign-in sees the reminders without the calendar buttons and can't change the times.

## Checks and backups

`.github/workflows/check.yml` runs on every pull request: the Next.js type check and build, and the Python tests
(`pytest`) against a throwaway Postgres. `.github/workflows/backup.yml` saves a full `pg_dump` every night, kept 30 days
on the run page; it needs a `BACKUP_DATABASE_URL` repository secret (Neon's direct connection string).

## The database

The tables are created and upgraded by the Python app (`db.init_db`). `prisma/schema.prisma` is read from the
database with `npm run db:pull` and is never pushed back: **do not run `prisma migrate` or `prisma db push`**.

## Run locally

```bash
cp .env.example .env          # fill in the values
npm install
pip install -r requirements.txt
npm run dev:py                # Python function on 127.0.0.1:8001
npm run dev                   # Next.js on localhost:3000 (forwards /api/py to the Python function)
```

The Streamlit app still runs with `streamlit run app.py`. Python tests: `MEETING_DSN=postgres://... pytest`.
