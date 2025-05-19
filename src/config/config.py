import os

class Config:
    """
    Configuration settings for the application. Loads settings from environment variables.
    """
    DATABASE_URL: str
    SECRET_KEY: str
    SESSION_TYPE: str
    MODEL_NAME: str
    DEVICE: str

    def __init__(self):
        """Loads configuration from environment variables."""
        self.DATABASE_URL = self._get_required_env_var("DATABASE_URL")
        self.SECRET_KEY = self._get_required_env_var("SECRET_KEY")
        self.SESSION_TYPE = self._get_required_env_var("SESSION_TYPE")
        self.MODEL_NAME = self._get_required_env_var("MODEL_ID")
        self.DEVICE = self._get_required_env_var("DEVICE")

    def _get_required_env_var(self, var_name: str) -> str:
        """Helper to get required environment variables."""
        value = os.environ.get(var_name)
        if not value:
            raise ValueError(f"Environment variable '{var_name}' not set")
        return value

config = Config()
