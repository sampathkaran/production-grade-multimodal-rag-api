from scrapingbee import  ScrapingBeeClient
from src.config.index import app_config

scrapingbee_client = ScrapingBeeClient(api_key=app_config["scrapingbee_api_key"])