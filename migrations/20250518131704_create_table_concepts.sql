-- migrate:up
CREATE TABLE concepts (
    id SERIAL PRIMARY KEY,
    concept TEXT NOT NULL,
    meaning TEXT NOT NULL
);

-- migrate:down
DROP TABLE concepts;
