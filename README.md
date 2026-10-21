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
     password per person; names then show in the change log.
3. Deploy.

Files uploaded through the web app (workbook PDF, blank forms, a backup to restore) must be under about 4 MB, the
Vercel request limit.

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
