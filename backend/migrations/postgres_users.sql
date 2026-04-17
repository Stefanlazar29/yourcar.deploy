-- Schema PostgreSQL pentru fluxul dublu (Parola 1 + Parola 2)
-- Rulează în consola PostgreSQL când migrezi de la SQLite.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pentru contul tău de fondator (rulează manual în consola PostgreSQL):
-- UPDATE users SET role = 'founder' WHERE email = 'sefanlazar7@gmail.com';

-- Index pentru căutare rapidă după email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
