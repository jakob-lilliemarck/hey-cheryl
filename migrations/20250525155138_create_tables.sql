-- migrate:up
CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX idx_user_sessions_user_id ON user_sessions (user_id);

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

-- migrate:down
DROP TABLE user_sessions;

DROP TABLE messages;

DROP TABLE users;

DROP TABLE concepts;
