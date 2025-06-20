import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from config import KAITO_BASE_URL, KAITO_CONFIG

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CORE API FUNCTIONS
# ============================================================================

def make_request(url: str, params: Dict = None, headers: Dict = None, timeout: int = 15) -> Dict[str, Any]:
    """Standardized request function with error handling"""
    try:
        headers1 = {
            'authorization': f'Bearer {KAITO_CONFIG["bearer_token"]}',
            'user-agent': KAITO_CONFIG["user-agent"],
            'user-id': KAITO_CONFIG["user-id"]
        }
        response = requests.get(url, params=params, headers=headers1, timeout=timeout)
        response.raise_for_status()
        return {'success': True, 'data': response.json(), 'error': None}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        return {'success': False, 'data': None, 'error': str(e)}

def fetch_kaito_mindshare_data(ticker: str, duration: str = "12m") -> Dict[str, Any]:
    """Fetch mindshare data from Kaito API"""
    if not KAITO_CONFIG.get("bearer_token"):
        return {'success': False, 'data': None, 'error': 'Kaito bearer token not configured'}
    
    url = f"{KAITO_BASE_URL}/ticker_mindshare_line"
    params = {
        'ticker': ticker,
        'duration': duration,
        'ex_official': 'false',
        'weighted': 'false'
    }
    headers = {
        'authorization': f'Bearer {KAITO_CONFIG["bearer_token"]}',
        'user-agent': KAITO_CONFIG["user-agent"],
        'user-id': KAITO_CONFIG["user-id"]
    }
    
    result = make_request(url, params, headers)
    if not result['success']:
        return result
    
    data = result['data']
    if 'result' in data and 'result' in data['result']:
        mindshare_series = data['result']['result']
        ticker_info = data.get('tickerData', {})
        
        mindshare_values = [float(entry.get('mindshare', 0)) for entry in mindshare_series]
        current_mindshare = mindshare_values[-1] if mindshare_values else 0
        avg_mindshare = sum(mindshare_values) / len(mindshare_values) if mindshare_values else 0
        
        return {
            'success': True,
            'data': {
                'current_mindshare': current_mindshare,
                'avg_mindshare': avg_mindshare,
                'mindshare_trend': mindshare_values[-7:] if len(mindshare_values) >= 7 else mindshare_values,
                'ticker_fullname': ticker_info.get('fullname', ticker),
                'data_points': len(mindshare_series)
            },
            'error': None
        }
    
    return {'success': False, 'data': None, 'error': 'No mindshare data found in response'}

def fetch_kaito_engagement_data(ticker: str, days: int = 30) -> Dict[str, Any]:
    """Fetch engagement data from Kaito API"""
    if not KAITO_CONFIG.get("bearer_token"):
        return {'success': False, 'data': None, 'error': 'Kaito bearer token not configured'}
    
    url = f"{KAITO_BASE_URL}/ticker_engagement"
    start_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
    
    params = {
        'ticker': ticker,
        'startTimestamp': start_timestamp,
        'keyword': '',
        'createdAtValue': f'last_{days}d',
        'sentimentWeightAndAdjust': '{"adjusted":false,"average":false}'
    }
    headers = {
        'authorization': f'Bearer {KAITO_CONFIG["bearer_token"]}',
        'user-agent': KAITO_CONFIG["user-agent"],
        'user-id': KAITO_CONFIG["user-id"]
    }
    
    result = make_request(url, params, headers)
    if not result['success']:
        return result
    
    data = result['data']
    if 'summaryData' in data:
        summary = data['summaryData']
        engagement = summary.get('engagement', 1)
        smart_engagement = summary.get('smartEngagement', 0)
        
        return {
            'success': True,
            'data': {
                'total_documents': summary.get('document', 0),
                'total_engagement': engagement,
                'smart_engagement': smart_engagement,
                'engagement_rate': smart_engagement / max(engagement, 1)
            },
            'error': None
        }
    
    return {'success': False, 'data': None, 'error': 'No engagement data found in response'}

def fetch_coingecko_price_data(coin_id: str) -> Dict[str, Any]:
    """Fetch basic price and market data from CoinGecko"""
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': coin_id,
        'vs_currencies': 'usd',
        'include_market_cap': 'true',
        'include_24hr_vol': 'true',
        'include_24hr_change': 'true'
    }
    
    result = make_request(url, params)
    if not result['success']:
        return result
    
    data = result['data']
    if coin_id in data:
        coin_data = data[coin_id]
        return {
            'success': True,
            'data': {
                'price': coin_data.get('usd', 0),
                'market_cap': coin_data.get('usd_market_cap', 0),
                'volume_24h': coin_data.get('usd_24h_vol', 0),
                'price_change_24h': coin_data.get('usd_24h_change', 0)
            },
            'error': None
        }
    
    return {'success': False, 'data': None, 'error': f'No price data found for {coin_id}'}

def fetch_coingecko_comprehensive_data(coin_id: str) -> Dict[str, Any]:
    """Fetch comprehensive token data from CoinGecko"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    
    result = make_request(url)
    if not result['success']:
        return result
    
    data = result['data']
    market_data = data.get('market_data', {})
    community_data = data.get('community_data', {})
    
    return {
        'success': True,
        'data': {
            'holder_count': data.get('watchlist_portfolio_users', 0),
            'market_cap': market_data.get('market_cap', {}).get('usd', 0),
            'market_cap_rank': data.get('market_cap_rank', 0),
            'telegram_users': community_data.get('telegram_channel_user_count', 0),
            'reddit_subscribers': community_data.get('reddit_subscribers', 0),
            'sentiment_positive': data.get('sentiment_votes_up_percentage', 0),
            'sentiment_negative': data.get('sentiment_votes_down_percentage', 0),
            'platform': data.get('asset_platform_id', ''),
            'contract_address': data.get('contract_address', ''),
            'categories': data.get('categories', [])
        },
        'error': None
    }

def fetch_defillama_protocol_data(protocol_slug: str) -> Dict[str, Any]:
    """Fetch DeFi protocol data from DefiLlama"""
    url = f"https://api.llama.fi/protocol/{protocol_slug}"
    
    result = make_request(url)
    if not result['success']:
        return result
    
    data = result['data']
    tvl_data = data.get('tvl', [])
    latest_tvl = 0
    
    if tvl_data and len(tvl_data) > 0:
        latest_tvl = tvl_data[-1].get('totalLiquidityUSD', 0) or 0
    
    return {
        'success': True,
        'data': {
            'tvl': latest_tvl,
            'logo_url': data.get('logo', ''),
            'twitter_handle': data.get('twitter', ''),
            'protocol_name': data.get('name', 'Unknown'),
            'category': data.get('category', 'DeFi')
        },
        'error': None
    }

def fetch_defillama_yields_data(protocol_slug: str) -> Dict[str, Any]:
    """Fetch staking/yield data from DeFiLlama"""
    url = "https://yields.llama.fi/pools"
    
    result = make_request(url)
    if not result['success']:
        return result
    
    all_pools = result['data'].get('data', [])
    protocol_pools = []
    
    # Find matching pools
    for pool in all_pools:
        project_name = pool.get('project', '').lower()
        if (protocol_slug.lower() in project_name or 
            project_name in protocol_slug.lower() or
            protocol_slug.lower().replace('-', '') == project_name.replace('-', '')):
            protocol_pools.append(pool)
    
    # Fallback to partial matching
    if not protocol_pools:
        for pool in all_pools:
            project_name = pool.get('project', '').lower()
            if any(word in project_name for word in protocol_slug.lower().split('-')):
                protocol_pools.append(pool)
    
    if protocol_pools:
        total_tvl = sum(pool.get('tvlUsd', 0) for pool in protocol_pools)
        avg_apy = sum(pool.get('apy', 0) for pool in protocol_pools) / len(protocol_pools)
        
        return {
            'success': True,
            'data': {
                'total_staking_tvl': total_tvl,
                'average_apy': avg_apy,
                'pool_count': len(protocol_pools)
            },
            'error': None
        }
    
    return {'success': False, 'data': None, 'error': f'No yield pools found for {protocol_slug}'}

def fetch_reservoir_nft_stats(collection_address: str) -> Dict[str, Any]:
    """Fetch NFT collection stats from Reservoir"""
    if not collection_address:
        return {'success': False, 'data': None, 'error': 'No collection address provided'}
    
    url = "https://api.reservoir.tools/collections/v7"
    params = {
        'id': collection_address,
        'includeTopBid': 'true'
    }
    headers = {
        'accept': 'application/json'
    }
    
    result = make_request(url, params, headers)
    if not result['success']:
        return result
    
    data = result['data']
    if data.get('collections'):
        collection = data['collections'][0]
        floor_ask = collection.get('floorAsk', {})
        price_info = floor_ask.get('price', {})
        amount_info = price_info.get('amount', {})
        
        return {
            'success': True,
            'data': {
                'floor_price': amount_info.get('native', 0),
                'volume_24h': collection.get('volume', {}).get('1day', 0),
                'volume_7d': collection.get('volume', {}).get('7day', 0),
                'owner_count': collection.get('ownerCount', 0),
                'token_count': collection.get('tokenCount', 0),
                'name': collection.get('name', 'Unknown')
            },
            'error': None
        }
    
    return {'success': False, 'data': None, 'error': 'No collection data found'}

def fetch_coingecko_historical_data(coin_id: str, days: int = 30) -> Dict[str, Any]:
    """Fetch historical price data from CoinGecko"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': days,
        # 'interval': 'hourly' if days <= 90 else 'daily'
    }
    headers = {
        'accept': 'application/json',
        'x-cgecko-api-key': 'CG-XgL2xMNsiZrmPZTJbNPX75ut'	
    }
    
    result = make_request(url, params)
    if not result['success']:
        return result
    
    data = result['data']
    prices = data.get('prices', [])
    volumes = data.get('total_volumes', [])
    
    # Format data for storage
    historical_data = []
    for i, price_point in enumerate(prices):
        timestamp = price_point[0] // 1000  # Convert to Unix timestamp
        price = price_point[1]
        volume = volumes[i][1] if i < len(volumes) else 0
        
        historical_data.append({
            'timestamp': timestamp,
            'price': price,
            'volume_24h': volume
        })
    
    return {
        'success': True,
        'data': {
            'coin_id': coin_id,
            'historical_prices': historical_data,
            'days_range': days,
            'data_points': len(historical_data)
        },
        'error': None
    }

def fetch_defi_governance_data(protocol_slug: str) -> Dict[str, Any]:
    """Fetch governance and additional DeFi metrics from free sources"""
    # Using DeFiLlama's free governance endpoint
    governance_url = f"https://api.llama.fi/governance/{protocol_slug}"
    
    result = make_request(governance_url)
    governance_data = {}
    
    if result['success']:
        data = result['data']
        governance_data = {
            'total_proposals': len(data.get('proposals', [])),
            'active_proposals': len([p for p in data.get('proposals', []) if p.get('state') == 'active']),
            'voter_count': data.get('voterCount', 0),
            'treasury_value': data.get('treasuryValue', 0)
        }
    
    # Get additional yield farming data
    yield_url = "https://yields.llama.fi/pools"
    yield_result = make_request(yield_url)
    
    additional_metrics = {}
    if yield_result['success']:
        all_pools = yield_result['data'].get('data', [])
        protocol_pools = [p for p in all_pools if protocol_slug.lower() in p.get('project', '').lower()]
        
        if protocol_pools:
            total_tvl = sum(p.get('tvlUsd', 0) for p in protocol_pools)
            avg_apy = sum(p.get('apy', 0) for p in protocol_pools) / len(protocol_pools)
            max_apy = max(p.get('apy', 0) for p in protocol_pools)
            
            additional_metrics = {
                'farming_tvl': total_tvl,
                'avg_farm_apy': avg_apy,
                'max_farm_apy': max_apy,
                'farm_pools_count': len(protocol_pools),
                'stable_pools': len([p for p in protocol_pools if p.get('stablecoin', False)]),
                'il_risk_pools': len([p for p in protocol_pools if not p.get('stablecoin', False)])
            }
    
    return {
        'success': True,
        'data': {
            **governance_data,
            **additional_metrics
        },
        'error': None
    }

def fetch_protocol_social_metrics(protocol_name: str) -> Dict[str, Any]:
    """Fetch social metrics from multiple free sources"""
    # Using CoinGecko's free social data
    search_url = "https://api.coingecko.com/api/v3/search"
    search_params = {'query': protocol_name}
    
    search_result = make_request(search_url, search_params)
    if not search_result['success']:
        return {'success': False, 'data': None, 'error': 'Search failed'}
    
    # Try to find the protocol in search results
    coins = search_result['data'].get('coins', [])
    target_coin = None
    
    for coin in coins:
        if protocol_name.lower() in coin.get('name', '').lower():
            target_coin = coin
            break
    
    if not target_coin:
        return {'success': False, 'data': None, 'error': 'Protocol not found'}
    
    # Get detailed coin data
    coin_id = target_coin['id']
    coin_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    
    coin_result = make_request(coin_url)
    if not coin_result['success']:
        return coin_result
    
    coin_data = coin_result['data']
    community = coin_data.get('community_data', {})
    developer = coin_data.get('developer_data', {})
    
    return {
        'success': True,
        'data': {
            'twitter_followers': community.get('twitter_followers', 0),
            'reddit_subscribers': community.get('reddit_subscribers', 0),
            'reddit_active_users': community.get('reddit_accounts_active_48h', 0),
            'telegram_users': community.get('telegram_users', 0),
            'github_forks': developer.get('forks', 0),
            'github_stars': developer.get('stars', 0),
            'github_subscribers': developer.get('subscribers', 0),
            'github_commits_4w': developer.get('github_commits_4w', 0),
            'developer_score': coin_data.get('developer_score', 0),
            'community_score': coin_data.get('community_score', 0)
        },
        'error': None
    }

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def fetch_all_protocol_data(protocol_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch all available data for a protocol"""
    all_data = {}
    
    # Kaito data
    # if config.get('kaito_ticker'):
    #     mindshare = fetch_kaito_mindshare_data(config['kaito_ticker'])
    #     engagement = fetch_kaito_engagement_data(config['kaito_ticker'])
    #     all_data['mindshare'] = mindshare
    #     all_data['engagement'] = engagement
    
    # # CoinGecko data
    # if config.get('coingecko_id'):
    #     price = fetch_coingecko_price_data(config['coingecko_id'])
    #     comprehensive = fetch_coingecko_comprehensive_data(config['coingecko_id'])
    #     all_data['price'] = price
    #     all_data['comprehensive'] = comprehensive
    
    # # DefiLlama data
    # if config.get('defillama_slug'):
    #     protocol = fetch_defillama_protocol_data(config['defillama_slug'])
    #     yields = fetch_defillama_yields_data(config['defillama_slug'])
    #     all_data['protocol'] = protocol
    #     all_data['yields'] = yields
    
    # # NFT data
    # if config.get('nft_contract'):
    #     nft = fetch_reservoir_nft_stats(config['nft_contract'])
    #     all_data['nft'] = nft
    import time
    if config.get('coingecko_id'):
        historical_data = fetch_coingecko_historical_data(config['coingecko_id'], days=30)

        time.sleep(1)  # Rate limiting
    
    # NEW: Additional DeFi governance data
    if config.get('defillama_slug'):
        governance_data = fetch_defi_governance_data(config['defillama_slug'])   
        time.sleep(0.5)
    
        # NEW: Social metrics
        social_data = fetch_protocol_social_metrics(config['coingecko_id'])
    all_data['governance'] = governance_data
    all_data['social'] = social_data
    all_data['historical'] = historical_data
    
    return all_data

# ============================================================================
# TESTING FUNCTION
# ============================================================================

def test_api_functions(clients_config: Dict[str, Dict[str, Any]]):
    """Test all API functions with provided configuration"""
    results = {}
    
    for client_name, config in clients_config.items():
        logger.info(f"Testing {client_name}...")
        results[client_name] = fetch_all_protocol_data(client_name, config)
    
    return results

if __name__ == "__main__":
    from config import CLIENTS
    
    results = test_api_functions(CLIENTS)
    import json
    # Save to JSON file
    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=4)

    # Print in readable format
    print(json.dumps(results, indent=4))