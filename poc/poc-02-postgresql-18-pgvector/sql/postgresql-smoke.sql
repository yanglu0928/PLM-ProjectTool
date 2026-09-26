\set ON_ERROR_STOP on

DROP TABLE IF EXISTS poc02_smoke;
CREATE TABLE poc02_smoke (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT current_timestamp
);

INSERT INTO poc02_smoke (label, payload)
VALUES
    ('windows-11', '{"platform":"windows","kind":"desktop"}'),
    ('windows-server-2025', '{"platform":"windows","kind":"server"}'),
    ('debian-13', '{"platform":"linux","kind":"server"}');

SELECT id, label, payload->>'platform' AS platform
FROM poc02_smoke
ORDER BY id;
