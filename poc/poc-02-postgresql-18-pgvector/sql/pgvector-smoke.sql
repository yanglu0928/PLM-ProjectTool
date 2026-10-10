\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS poc02_vectors;
CREATE TABLE poc02_vectors (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label text NOT NULL UNIQUE,
    embedding vector(3) NOT NULL
);

INSERT INTO poc02_vectors (label, embedding) VALUES
    ('origin', '[0,0,0]'),
    ('near', '[1,1,1]'),
    ('far', '[9,9,9]');

UPDATE poc02_vectors SET embedding = '[2,2,2]' WHERE label = 'near';
DELETE FROM poc02_vectors WHERE label = 'far';

CREATE INDEX poc02_vectors_hnsw_idx
    ON poc02_vectors USING hnsw (embedding vector_l2_ops);

SELECT extversion AS vector_version
FROM pg_extension
WHERE extname = 'vector';

SELECT label, embedding <-> '[0,0,0]'::vector AS distance
FROM poc02_vectors
ORDER BY embedding <-> '[0,0,0]'::vector
LIMIT 2;
