-- migrate:up
CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE user_sessions (
    id UUID NOT NULL,
    user_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event TEXT NOT NULL,
    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE VIEW latest_user_sessions AS
SELECT DISTINCT
    ON (id) *
FROM
    user_sessions
ORDER BY
    id,
    timestamp DESC;

CREATE INDEX idx_user_sessions_user_id ON user_sessions (user_id);

CREATE INDEX idx_user_sessions_id ON user_sessions (id);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE concepts (
    id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    concept TEXT NOT NULL,
    meaning TEXT NOT NULL,
    deleted BOOLEAN NOT NULL,
    PRIMARY KEY (id, timestamp)
);

CREATE VIEW latest_concepts AS
SELECT
    *
FROM
    (
        SELECT DISTINCT
            ON (id) *
        FROM
            concepts
        ORDER BY
            id,
            timestamp DESC
    )
WHERE
    deleted = FALSE;

CREATE TABLE replies (
    id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    message_id UUID NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (message_id) REFERENCES messages (id)
);

CREATE VIEW latest_replies AS
SELECT DISTINCT
    ON (id) *
FROM
    replies
ORDER BY
    id,
    timestamp DESC;

CREATE TABLE system_prompts (
    key TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    prompt TEXT NOT NULL,
    PRIMARY KEY (key, timestamp)
);

CREATE INDEX idx_system_prompts_key ON system_prompts (key);

CREATE VIEW latest_system_prompts AS
SELECT DISTINCT
    ON (key) *
FROM
    system_prompts
ORDER BY
    key,
    timestamp DESC;

-- System prompts are considered part of the code.
INSERT INTO
    system_prompts (key, timestamp, prompt)
VALUES
    ('base', NOW (), ''),
    ('related_concepts', NOW (), '');

-- migrate:down
-- Views
DROP VIEW latest_user_sessions;

DROP VIEW latest_replies;

DROP VIEW latest_system_prompts;

DROP VIEW latest_concepts;

--  Tables
DROP TABLE replies;

DROP TABLE user_sessions;

DROP TABLE messages;

DROP TABLE users;

DROP TABLE concepts;

DROP TABLE system_prompts;
