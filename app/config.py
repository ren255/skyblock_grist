from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config= SettingsConfigDict(env_file=".env", extra="ignore")
    grist_url: str = "http://localhost:3000"
    grist_api_key: str
    
    grist_doc_id: str
    grist_gem_table_name: str = "Gem"

settings = Settings()
