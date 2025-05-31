import os
from uuid import UUID

class Config:
    """
    Configuration settings for the application. Loads settings from environment variables.
    """
    DATABASE_URL: str
    SECRET_KEY: str
    SESSION_TYPE: str
    MODEL_NAME: str
    DEVICE: str
    CONVERSATION_ID: UUID
    ASSISTANT_USER_ID: UUID
    ASSISTANT_SESSION_ID: UUID
    WITH_MOCKED_ASSISTANT: bool
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    DEBUG: bool

    def __init__(
        self,
        *,
        database_url: str,
        secret_key: str,
        session_type: str,
        model_name: str,
        device: str,
        conversation_id: UUID,
        assistant_user_id: UUID,
        assistant_session_id: UUID,
        with_mocked_assistant: bool,
        admin_username: str,
        admin_password,
        debug: bool
    ):
        """Loads configuration from environment variables."""
        self.DATABASE_URL = database_url
        self.SECRET_KEY = secret_key
        self.SESSION_TYPE = session_type
        self.MODEL_NAME = model_name
        self.DEVICE = device
        self.CONVERSATION_ID = conversation_id
        self.ASSISTANT_SESSION_ID = assistant_session_id
        self.ASSISTANT_USER_ID = assistant_user_id
        self.WITH_MOCKED_ASSISTANT = with_mocked_assistant
        self.ADMIN_USERNAME = admin_username
        self.ADMIN_PASSWORD = admin_password
        self.DEBUG = debug

    @staticmethod
    def new_from_env():
        """Loads configuration from environment variables."""
        database_url = Config._get_required_env_var("DATABASE_URL")
        secret_key = Config._get_required_env_var("SECRET_KEY")
        session_type = Config._get_required_env_var("SESSION_TYPE")
        model_name = Config._get_required_env_var("MODEL_ID")
        device = Config._get_required_env_var("DEVICE")
        conversation_id = Config._get_required_env_var("CONVERSATION_ID")
        assistant_user_id = Config._get_required_env_var("ASSISTANT_USER_ID")
        assistant_session_id = Config._get_required_env_var("ASSISTANT_SESSION_ID")
        with_mocked_assistant = Config._get_required_env_var("WITH_MOCKED_ASSISTANT")
        admin_username = Config._get_required_env_var("ADMIN_USERNAME")
        admin_password = Config._get_required_env_var("ADMIN_PASSWORD")
        debug = Config._get_required_env_var("DEBUG")

        return Config(
            database_url=database_url,
            secret_key=secret_key,
            session_type=session_type,
            model_name=model_name,
            device=device,
            conversation_id=UUID(conversation_id),
            assistant_session_id=UUID(assistant_session_id),
            assistant_user_id=UUID(assistant_user_id),
            with_mocked_assistant=with_mocked_assistant.lower() == 'true',
            admin_username=admin_username,
            admin_password=admin_password,
            debug = debug.lower() == 'true'
        )

    @staticmethod
    def _get_required_env_var(var_name: str) -> str:
        """Helper to get required environment variables."""
        value = os.environ.get(var_name)
        if not value:
            raise ValueError(f"Environment variable '{var_name}' not set")
        return value
