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
    id UUID PRIMARY KEY,
    concept TEXT NOT NULL,
    meaning TEXT NOT NULL
);

CREATE TABLE replies (
    id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    message_id UUID NOT NULL,
    acknowledged BOOL NOT NULL,
    published BOOL NOT NULL,
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

-- migrate:down
DROP VIEW latest_user_sessions;

DROP VIEW latest_replies;

DROP TABLE replies;

DROP TABLE user_sessions;

DROP TABLE messages;

DROP TABLE users;

DROP TABLE concepts;
