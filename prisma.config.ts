import "dotenv/config";
import { defineConfig, env } from "prisma/config";

// Prisma only reads the tables here. The Python code (db.init_db, run by the Streamlit app) creates and upgrades
// them, so there are no Prisma migrations: never run `prisma migrate` or `prisma db push` against this database.
// After the Python side adds a column, refresh this schema with `npm run db:pull`.
export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: { url: env("DATABASE_URL") },
});
