from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://renate:changeme@db:5432/renate_sales"

    openai_api_key: str = ""

    playwright_ws_endpoint: str = "ws://playwright-browser:3000"

    # Proxy (comma-separated, format: host:port:username:password)
    proxy_list: str = ""

    # CAPTCHA
    captcha_api_key: str = ""

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    report_recipients: str = ""

    # Scraper
    max_concurrent_scrapers: int = 3
    browser_pool_size: int = 5
    daily_report_hour: int = 9
    daily_report_minute: int = 0

    # Fallback APIs
    apify_api_key: str = ""
    firecrawl_api_key: str = ""

    # Enrichment (Hunter.io)
    hunter_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
