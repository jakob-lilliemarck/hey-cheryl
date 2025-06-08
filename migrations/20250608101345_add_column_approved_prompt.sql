-- migrate:up
ALTER TABLE system_prompts
ADD COLUMN approved BOOL NOT NULL DEFAULT FALSE;

-- migrate:down
ALTER TABLE system_prompts
DROP COLUMN IF EXISTS approved;
