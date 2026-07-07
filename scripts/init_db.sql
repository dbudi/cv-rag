-- Jalankan sekali setelah container Postgres pgvector aktif, sebelum
-- menjalankan migrasi Alembic / create_all.
CREATE EXTENSION IF NOT EXISTS vector;
