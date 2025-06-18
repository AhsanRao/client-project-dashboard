import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
KAITO_BASE_URL = "https://portal.kaito.ai/api/ai/analytics"

# Get credentials from environment
KAITO_CONFIG = {
    'bearer_token': os.getenv('KAITO_BEARER_TOKEN', ''),
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'user-id': os.getenv('KAITO_USER_ID', '')
}

# Client configurations
CLIENTS = {
    "Raydium": {
        "coingecko_id": "raydium",
        "defillama_slug": "raydium",
        "kaito_ticker": "RAY",
        "blockchain": "solana",
        "display_name": "RAY",
        "contract_address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "nft_contract": None,
        "opensea_slug": None
    },
    "Abstract": {
        "coingecko_id": "stargate-bridged-usdc-abstract", #stargate-bridged-usdc-abstract
        "defillama_slug": "abstract",
        "kaito_ticker": "ABSTRACT",
        "blockchain": "ethereum",
        "display_name": "ABS",
        "contract_address": None,
        "nft_contract": None,
        "opensea_slug": None
    },
    "Kaito": {
        "coingecko_id": "kaito",
        "defillama_slug": "kaito",
        "kaito_ticker": "KAITO",
        "blockchain": "ethereum",
        "display_name": "KAITO",
        "contract_address": "0x98d0baa52b2d063e780de12f615f963fe8537553",
        "nft_contract": None,
        "opensea_slug": None
    },
    "Pengu": {
        "coingecko_id": "pudgy-penguins",
        "defillama_slug": "pudgy-penguins",
        "kaito_ticker": "PENGU",
        "blockchain": "ethereum",
        "display_name": "PENGU",
        "contract_address": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
        "nft_contract": "0xbd3531da5cf5857e7cfaa92426877b022e612cf8",  # Pudgy Penguins NFT
        "opensea_slug": "pudgypenguins"
    },
    "Sophon": {
        "coingecko_id": "sophon",
        "defillama_slug": "sophon-bridge",
        "kaito_ticker": "SOPHON",
        "blockchain": "ethereum",
        "display_name": "SOPH",
        "contract_address": None,
        "nft_contract": None,
        "opensea_slug": None
    },
    "OpenLedger": {
        "coingecko_id": "openledger",
        "defillama_slug": "openledger",
        "kaito_ticker": "OPENLEDGER",
        "blockchain": "ethereum",
        "display_name": "OL",
        "contract_address": "0x92cfbec26c206c90aee3b7c66a9ae673754fab7e",
        "nft_contract": None,
        "opensea_slug": None
    }
}

# Cache settings
CACHE_TTL = {
    'price_data': 300,  # 5 minutes
    'defi_data': 300,   # 5 minutes
    'social_data': 600  # 10 minutes
}