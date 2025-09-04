import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import time
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional
import logging

# Hardcoded password for dashboard access
PASSWORD = "apc@2025"

# Password protection
def password_protect():
    st.markdown("## 🔒 Enter Password to Access Dashboard")
    password = st.text_input("Password", type="password")
    if password != PASSWORD:
        st.warning("Incorrect password. Please try again.")
        st.stop()


# Import the API functions
from data_fetcher import (
    fetch_coingecko_historical_data,
    fetch_defi_governance_data,
    fetch_kaito_mindshare_data,
    fetch_kaito_engagement_data,
    fetch_coingecko_price_data,
    fetch_coingecko_comprehensive_data,
    fetch_defillama_protocol_data,
    fetch_defillama_yields_data,
    fetch_protocol_social_metrics,
    fetch_reservoir_nft_stats
)
from config import CLIENTS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Client Project Data Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Database setup
DB_NAME = "client_data.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Main data table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS client_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        data_type TEXT NOT NULL,
        data JSON NOT NULL,
        success BOOLEAN NOT NULL,
        error_message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Fetch history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fetch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fetch_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        clients_fetched INTEGER,
        total_apis_called INTEGER,
        errors_count INTEGER,
        duration_seconds REAL
    )
    """)
    
    conn.commit()
    conn.close()

def save_data_to_db(client_name: str, data_type: str, data: Dict[str, Any]):
    """Save fetched data to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO client_data (client_name, data_type, data, success, error_message)
    VALUES (?, ?, ?, ?, ?)
    """, (
        client_name,
        data_type,
        json.dumps(data.get('data', {})),
        data.get('success', False),
        data.get('error', None)
    ))
    
    conn.commit()
    conn.close()

def get_latest_data(client_name: str = None, data_type: str = None) -> pd.DataFrame:
    """Get latest data from database"""
    conn = sqlite3.connect(DB_NAME)
    
    query = """
    SELECT * FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY client_name, data_type ORDER BY timestamp DESC) as rn
        FROM client_data
        WHERE 1=1
    """
    
    params = []
    if client_name:
        query += " AND client_name = ?"
        params.append(client_name)
    if data_type:
        query += " AND data_type = ?"
        params.append(data_type)
    
    query += ") WHERE rn = 1"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Parse JSON data
    if not df.empty:
        df['data'] = df['data'].apply(json.loads)
    
    return df

def get_fetch_history() -> pd.DataFrame:
    """Get fetch history from database"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM fetch_history ORDER BY fetch_timestamp DESC LIMIT 10",
        conn
    )
    conn.close()
    return df

def init_historical_tables():
    """Initialize historical data tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Historical price data table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        coin_id TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        price_usd REAL NOT NULL,
        volume_24h REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(client_name, coin_id, timestamp)
    )
    """)
    
    # Optimized indexes for time series queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_client_time ON price_history(client_name, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_coin_time ON price_history(coin_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp)")
    
    conn.commit()
    conn.close()

def save_historical_data(client_name: str, coin_id: str, historical_data: List[Dict]):
    """Save historical price data to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Prepare data for batch insertion
    data_to_insert = [
        (client_name, coin_id, point['timestamp'], point['price'], point['volume_24h'])
        for point in historical_data
    ]
    
    cursor.execute("BEGIN TRANSACTION")
    cursor.executemany("""
        INSERT OR REPLACE INTO price_history 
        (client_name, coin_id, timestamp, price_usd, volume_24h)
        VALUES (?, ?, ?, ?, ?)
    """, data_to_insert)
    cursor.execute("COMMIT")
    conn.close()

def get_historical_data(client_names: List[str] = None, days: int = 30) -> pd.DataFrame:
    """Get historical price data from database"""
    conn = sqlite3.connect(DB_NAME)
    
    # Calculate timestamp cutoff
    cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
    
    query = """
    SELECT client_name, coin_id, timestamp, price_usd, volume_24h
    FROM price_history 
    WHERE timestamp >= ?
    """
    params = [cutoff_timestamp]
    
    if client_names:
        placeholders = ','.join('?' * len(client_names))
        query += f" AND client_name IN ({placeholders})"
        params.extend(client_names)
    
    query += " ORDER BY client_name, timestamp"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Convert timestamp to datetime
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    return df

def create_historical_price_chart(historical_df: pd.DataFrame, chart_type: str = "absolute") -> go.Figure:
    """Create interactive historical price comparison chart"""
    fig = go.Figure()
    
    if historical_df.empty:
        return fig
    
    clients = historical_df['client_name'].unique()
    
    for client in clients:
        client_data = historical_df[historical_df['client_name'] == client].copy()
        client_data = client_data.sort_values('datetime')
        
        if chart_type == "normalized":
            # Normalize to percentage returns from start
            if len(client_data) > 0:
                start_price = client_data['price_usd'].iloc[0]
                client_data['normalized_price'] = (client_data['price_usd'] / start_price - 1) * 100
                y_values = client_data['normalized_price']
                y_title = "Price Change (%)"
                hover_template = f"{client}: %{{y:+.2f}}%<br>%{{x}}<extra></extra>"
            else:
                continue
        else:
            y_values = client_data['price_usd']
            y_title = "Price (USD)"
            hover_template = f"{client}: $%{{y:,.4f}}<br>%{{x}}<extra></extra>"
        
        fig.add_trace(go.Scatter(
            x=client_data['datetime'],
            y=y_values,
            name=client,
            mode='lines',
            hovertemplate=hover_template,
            line=dict(width=2)
        ))
    
    fig.update_layout(
        title=f"{'Normalized ' if chart_type == 'normalized' else ''}Price Comparison",
        xaxis_title="Date",
        yaxis_title=y_title,
        hovermode='x unified',
        height=500,
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="7D", step="day", stepmode="backward"),
                    dict(count=30, label="30D", step="day", stepmode="backward"),
                    dict(count=90, label="90D", step="day", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.1),
            type="date"
        ),
        showlegend=True
    )
    
    return fig

def fetch_all_data_with_limits():
    """Fetch data for all clients with API limit handling"""
    fetch_start = time.time()
    total_apis_called = 0
    errors_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    clients_list = list(CLIENTS.items())
    total_steps = len(clients_list) * 6  # 6 API calls per client
    current_step = 0
    
    for idx, (client_name, config) in enumerate(clients_list):
        status_text.text(f"Fetching data for {client_name}...")
        
        # Mindshare data
        if config.get('kaito_ticker'):
            try:
                mindshare_data = fetch_kaito_mindshare_data(config['kaito_ticker'])
                save_data_to_db(client_name, 'mindshare', mindshare_data)
                total_apis_called += 1
                if not mindshare_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching mindshare for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(0.5)  # Rate limiting
            
            # Engagement data
            try:
                engagement_data = fetch_kaito_engagement_data(config['kaito_ticker'])
                save_data_to_db(client_name, 'engagement', engagement_data)
                total_apis_called += 1
                if not engagement_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching engagement for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(0.5)
        
        # CoinGecko data
        if config.get('coingecko_id'):
            try:
                price_data = fetch_coingecko_price_data(config['coingecko_id'])
                save_data_to_db(client_name, 'price', price_data)
                total_apis_called += 1
                if not price_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching price for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(30)  # CoinGecko rate limit
            
            try:
                comprehensive_data = fetch_coingecko_comprehensive_data(config['coingecko_id'])
                save_data_to_db(client_name, 'comprehensive', comprehensive_data)
                total_apis_called += 1
                if not comprehensive_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching comprehensive data for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(30)
        
        # DefiLlama data
        if config.get('defillama_slug'):
            try:
                protocol_data = fetch_defillama_protocol_data(config['defillama_slug'])
                save_data_to_db(client_name, 'protocol', protocol_data)
                total_apis_called += 1
                if not protocol_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching protocol data for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(0.5)
            
            try:
                yields_data = fetch_defillama_yields_data(config['defillama_slug'])
                save_data_to_db(client_name, 'yields', yields_data)
                total_apis_called += 1
                if not yields_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching yields data for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)

            time.sleep(10)
        
        # NFT data
        if config.get('nft_contract'):
            try:
                nft_data = fetch_reservoir_nft_stats(config['nft_contract'])
                save_data_to_db(client_name, 'nft', nft_data)
                total_apis_called += 1
                if not nft_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching NFT data for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_value = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress_value)
        
        time.sleep(30)  # Rate limiting

        # Historical price data
        if config.get('coingecko_id'):
            try:
                historical_data = fetch_coingecko_historical_data(config['coingecko_id'], days=30)
                save_data_to_db(client_name, 'historical', historical_data)
                
                # Save to historical table
                if historical_data.get('success') and historical_data['data'].get('historical_prices'):
                    save_historical_data(
                        client_name, 
                        config['coingecko_id'],
                        historical_data['data']['historical_prices']
                    )
                
                total_apis_called += 1
                if not historical_data.get('success'):
                    errors_count += 1
            except Exception as e:
                logger.error(f"Error fetching historical data for {client_name}: {e}")
                errors_count += 1
            
            current_step += 1
            progress_bar.progress(min(current_step / total_steps, 1.0))
            time.sleep(30)  # Rate limiting
        
        # Additional DeFi governance data
        # if config.get('defillama_slug'):
        #     try:
        #         governance_data = fetch_defi_governance_data(config['defillama_slug'])
        #         save_data_to_db(client_name, 'governance', governance_data)
        #         total_apis_called += 1
        #         if not governance_data.get('success'):
        #             errors_count += 1
        #     except Exception as e:
        #         logger.error(f"Error fetching governance data for {client_name}: {e}")
        #         errors_count += 1
            
        #     current_step += 1
        #     progress_bar.progress(min(current_step / total_steps, 1.0))
        #     time.sleep(1)
        
        # Social metrics
        # try:
        #     social_data = fetch_protocol_social_metrics(client_name)
        #     save_data_to_db(client_name, 'social', social_data)
        #     total_apis_called += 1
        #     if not social_data.get('success'):
        #         errors_count += 1
        # except Exception as e:
        #     logger.error(f"Error fetching social data for {client_name}: {e}")
        #     errors_count += 1
        
        # current_step += 1
        # progress_bar.progress(min(current_step / total_steps, 1.0))
        time.sleep(1)

    
    # Save fetch history
    fetch_duration = time.time() - fetch_start
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO fetch_history (clients_fetched, total_apis_called, errors_count, duration_seconds)
    VALUES (?, ?, ?, ?)
    """, (len(CLIENTS), total_apis_called, errors_count, fetch_duration))
    conn.commit()
    conn.close()
    
    progress_bar.empty()
    status_text.empty()
    
    return total_apis_called, errors_count, fetch_duration

def create_comparison_chart(metric_name: str, data_dict: Dict[str, float], title: str):
    """Create a comparison bar chart for a specific metric"""
    df = pd.DataFrame(list(data_dict.items()), columns=['Client', metric_name])
    df = df.sort_values(metric_name, ascending=True)
    
    fig = px.bar(df, x=metric_name, y='Client', orientation='h',
                 title=title,
                 color=metric_name,
                 color_continuous_scale='Blues')
    
    fig.update_layout(
        height=400,
        showlegend=False,
        xaxis_title=metric_name,
        yaxis_title="",
        title_x=0.5
    )
    
    return fig

def create_multi_metric_radar(client_data: Dict[str, Dict[str, float]], metrics: List[str]):
    """Create a radar chart comparing multiple metrics across clients"""
    fig = go.Figure()
    
    for client, data in client_data.items():
        values = [data.get(metric, 0) for metric in metrics]
        values.append(values[0])  # Close the radar
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=metrics + [metrics[0]],
            fill='toself',
            name=client
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=True,
        title="Multi-Metric Comparison",
        height=500
    )
    
    return fig

def format_number(num: float) -> str:
    """Format large numbers for display"""
    if num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    elif num >= 1e3:
        return f"${num/1e3:.2f}K"
    else:
        return f"${num:.2f}"

def get_logo_url(client_name: str, all_data: pd.DataFrame) -> Optional[str]:
    """Get logo URL for a client from protocol data"""
    protocol_data = all_data[(all_data['client_name'] == client_name) & 
                           (all_data['data_type'] == 'protocol')]
    if not protocol_data.empty and protocol_data.iloc[0]['success']:
        data = protocol_data.iloc[0]['data']
        return data.get('logo_url', None)
    return None

def main():
    # Password protection
    password_protect()
    # Initialize database
    init_database()
    # init_historical_tables()
    
    # Header
    st.title("🚀 Client Project Data Dashboard")
    st.markdown("Real-time comparative data for key crypto projects")
    
    # Sidebar
    with st.sidebar:
        st.header("Dashboard Controls")
        
        # Refresh button
        if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
            with st.spinner("Fetching data from APIs..."):
                apis_called, errors, duration = fetch_all_data_with_limits()
                st.success(f"Data refreshed! Called {apis_called} APIs in {duration:.1f}s ({errors} errors)")
        
        # Last fetch info
        st.subheader("Last Fetch Info")
        fetch_history = get_fetch_history()
        if not fetch_history.empty:
            last_fetch = fetch_history.iloc[0]
            st.info(f"**Last Updated:** {last_fetch['fetch_timestamp']}")
            st.metric("APIs Called", last_fetch['total_apis_called'])
            # st.metric("Errors", last_fetch['errors_count'])
            st.metric("Duration", f"{last_fetch['duration_seconds']:.1f}s")
        else:
            st.warning("No data fetched yet. Click refresh to start.")
        
        # Client filter
        st.subheader("Filters")
        selected_clients = st.multiselect(
            "Select Clients",
            options=list(CLIENTS.keys()),
            default=list(CLIENTS.keys())
        )
    
    # Main content
    tabs = st.tabs(["📊 Overview", "📈 Historical Prices", "💰 Price & Market", 
                    "🔗 DeFi Metrics", "📈 Social & Mindshare", "🎨 NFT Data", 
                    "📉 Comparisons"])
    
    # Get latest data
    all_data = get_latest_data()
    
    with tabs[0]:  # Overview
        st.header("Overview Dashboard")
        
        if all_data.empty:
            st.warning("No data available. Please click the refresh button to fetch data.")
        else:
            # Create overview metrics for each client
            for client in selected_clients:
                client_data = all_data[all_data['client_name'] == client]
                
                if not client_data.empty:
                    with st.container():
                        # Get logo URL
                        logo_url = get_logo_url(client, all_data)
                        
                        # Create header with logo
                        header_col1, header_col2 = st.columns([1, 11])
                        with header_col1:
                            if logo_url:
                                st.image(logo_url, width=50)
                            else:
                                st.write("📌")
                        
                        with header_col2:
                            st.subheader(client)
                    
                        col1, col2, col3, col4 = st.columns(4)
                        
                        # Extract metrics
                        price_row = client_data[client_data['data_type'] == 'price']
                        protocol_row = client_data[client_data['data_type'] == 'protocol']
                        comprehensive_row = client_data[client_data['data_type'] == 'comprehensive']
                        
                        with col1:
                            if not price_row.empty and price_row.iloc[0]['success']:
                                price_data = price_row.iloc[0]['data']
                                st.metric(
                                    "Price (24h)",
                                    f"${price_data.get('price', 0):.4f}",
                                    f"{(price_data.get('price_change_24h') or 0):.2f}%"
                                )
                        
                        with col2:
                            if not price_row.empty and price_row.iloc[0]['success']:
                                price_data = price_row.iloc[0]['data']
                                st.metric(
                                    "Market Cap",
                                    format_number(price_data.get('market_cap', 0))
                                )
                        
                        with col3:
                            if not protocol_row.empty and protocol_row.iloc[0]['success']:
                                protocol_data = protocol_row.iloc[0]['data']
                                st.metric(
                                    "TVL",
                                    format_number(protocol_data.get('tvl', 0))
                                )
                        
                        with col4:
                            if not comprehensive_row.empty and comprehensive_row.iloc[0]['success']:
                                comp_data = comprehensive_row.iloc[0]['data']
                                st.metric(
                                    "Holders",
                                    f"{comp_data.get('holder_count', 0):,}"
                                )
                        
                        st.divider()
    
    with tabs[1]:  # Historical Prices
        st.header("Historical Price Analysis")
        
        # Time range selection
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            days_range = st.selectbox(
                "Time Range",
                options=[7, 30, 90, 365],
                index=1,  # Default to 30 days
                format_func=lambda x: f"{x} days"
            )
        
        with col2:
            chart_type = st.selectbox(
                "Chart Type",
                options=["absolute", "normalized"],
                format_func=lambda x: "Absolute Prices" if x == "absolute" else "Normalized (%)"
            )
        
        with col3:
            if st.button("📊 Update Historical Data", type="secondary"):
                with st.spinner("Fetching historical data..."):
                    for client_name, config in CLIENTS.items():
                        if config.get('coingecko_id'):
                            historical_data = fetch_coingecko_historical_data(config['coingecko_id'], days=days_range)
                            if historical_data.get('success'):
                                save_historical_data(
                                    client_name,
                                    config['coingecko_id'],
                                    historical_data['data']['historical_prices']
                                )
                st.success("Historical data updated!")
        
        # Get historical data
        historical_df = get_historical_data(selected_clients, days=days_range)
        
        if not historical_df.empty:
            # Create and display historical chart
            hist_chart = create_historical_price_chart(historical_df, chart_type)
            st.plotly_chart(hist_chart, use_container_width=True)
            
            # Historical data summary
            st.subheader("Price Performance Summary")
            
            summary_data = []
            for client in selected_clients:
                client_data = historical_df[historical_df['client_name'] == client]
                if not client_data.empty:
                    client_data = client_data.sort_values('datetime')
                    start_price = client_data['price_usd'].iloc[0]
                    end_price = client_data['price_usd'].iloc[-1]
                    change_pct = ((end_price - start_price) / start_price) * 100
                    max_price = client_data['price_usd'].max()
                    min_price = client_data['price_usd'].min()
                    avg_volume = client_data['volume_24h'].mean()
                    
                    summary_data.append({
                        'Token': client,
                        'Start Price': f"${start_price:.4f}",
                        'End Price': f"${end_price:.4f}",
                        'Change %': f"{change_pct:+.2f}%",
                        'High': f"${max_price:.4f}",
                        'Low': f"${min_price:.4f}",
                        'Avg Volume': f"${avg_volume:,.0f}"
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)
        else:
            st.info("No historical data available. Click 'Update Historical Data' to fetch data.")

    
    with tabs[2]:  # Price & Market
        st.header("Price & Market Data")
        
        price_data_dict = {}
        market_cap_dict = {}
        volume_dict = {}
        logo_dict = {}
        
        for client in selected_clients:
            # Get logo
            logo_url = get_logo_url(client, all_data)
            if logo_url:
                logo_dict[client] = logo_url

            client_data = all_data[(all_data['client_name'] == client) & 
                                 (all_data['data_type'] == 'price')]
            if not client_data.empty and client_data.iloc[0]['success']:
                data = client_data.iloc[0]['data']
                price_data_dict[client] = data.get('price', 0)
                market_cap_dict[client] = data.get('market_cap', 0)
                volume_dict[client] = data.get('volume_24h', 0)
        
        # Display client logos in a row
        if logo_dict:
            st.subheader("Projects")
            logo_cols = st.columns(len(logo_dict))
            for idx, (client, logo_url) in enumerate(logo_dict.items()):
                with logo_cols[idx]:
                    st.image(logo_url, width=60, caption=client)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if price_data_dict:
                fig = create_comparison_chart("Price ($)", price_data_dict, "Token Prices Comparison")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if market_cap_dict:
                fig = create_comparison_chart("Market Cap ($)", market_cap_dict, "Market Cap Comparison")
                st.plotly_chart(fig, use_container_width=True)
        
        if volume_dict:
            fig = create_comparison_chart("24h Volume ($)", volume_dict, "24h Trading Volume Comparison")
            st.plotly_chart(fig, use_container_width=True)
    
    with tabs[3]:  # DeFi Metrics
        st.header("DeFi Protocol Metrics")
        
        tvl_dict = {}
        apy_dict = {}
        staking_tvl_dict = {}
        
        for client in selected_clients:
            # Protocol TVL
            protocol_data = all_data[(all_data['client_name'] == client) & 
                                   (all_data['data_type'] == 'protocol')]
            if not protocol_data.empty and protocol_data.iloc[0]['success']:
                data = protocol_data.iloc[0]['data']
                tvl_dict[client] = data.get('tvl', 0)
            
            # Yields data
            yields_data = all_data[(all_data['client_name'] == client) & 
                                 (all_data['data_type'] == 'yields')]
            if not yields_data.empty and yields_data.iloc[0]['success']:
                data = yields_data.iloc[0]['data']
                apy_dict[client] = data.get('average_apy', 0)
                staking_tvl_dict[client] = data.get('total_staking_tvl', 0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if tvl_dict:
                fig = create_comparison_chart("TVL ($)", tvl_dict, "Total Value Locked Comparison")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if apy_dict:
                fig = create_comparison_chart("APY (%)", apy_dict, "Average APY Comparison")
                st.plotly_chart(fig, use_container_width=True)
        
        # Detailed table
        if tvl_dict or apy_dict:
            st.subheader("Detailed DeFi Metrics")
            defi_df = pd.DataFrame({
                'Client': selected_clients,
                'TVL': [format_number(tvl_dict.get(c, 0)) for c in selected_clients],
                'Staking TVL': [format_number(staking_tvl_dict.get(c, 0)) for c in selected_clients],
                'Average APY': [f"{apy_dict.get(c, 0):.2f}%" for c in selected_clients]
            })
            st.dataframe(defi_df, use_container_width=True)
    
    with tabs[4]:  # Social & Mindshare
        st.header("Social & Mindshare Metrics")
        
        mindshare_dict = {}
        telegram_dict = {}
        sentiment_dict = {}
        
        for client in selected_clients:
            # Mindshare
            mindshare_data = all_data[(all_data['client_name'] == client) & 
                                    (all_data['data_type'] == 'mindshare')]
            if not mindshare_data.empty and mindshare_data.iloc[0]['success']:
                data = mindshare_data.iloc[0]['data']
                mindshare_dict[client] = data.get('current_mindshare', 0)
            
            # Social data
            comp_data = all_data[(all_data['client_name'] == client) & 
                               (all_data['data_type'] == 'comprehensive')]
            if not comp_data.empty and comp_data.iloc[0]['success']:
                data = comp_data.iloc[0]['data']
                telegram_dict[client] = data.get('telegram_users', 0)
                sentiment_dict[client] = data.get('sentiment_positive', 50)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if mindshare_dict:
                fig = create_comparison_chart("Mindshare", mindshare_dict, "Current Mindshare Comparison")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Mindshare data not available (authentication required)")
        
        with col2:
            if telegram_dict:
                fig = create_comparison_chart("Telegram Users", telegram_dict, "Telegram Community Size")
                st.plotly_chart(fig, use_container_width=True)
        
        # Sentiment gauge
        if sentiment_dict:
            st.subheader("Sentiment Analysis")
            cols = st.columns(len(selected_clients))
            for idx, client in enumerate(selected_clients):
                with cols[idx]:
                    sentiment = sentiment_dict.get(client, 50)
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=sentiment,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': client},
                        gauge={
                            'axis': {'range': [None, 100]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 80], 'color': "gray"}],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 90}}))
                    fig.update_layout(height=200)
                    st.plotly_chart(fig, use_container_width=True)
    
    with tabs[5]:  # NFT Data
        st.header("NFT Collection Data")
        
        nft_clients = [c for c in selected_clients if CLIENTS[c].get('nft_contract')]
        
        if not nft_clients:
            st.info("No NFT data available for selected clients")
        else:
            for client in nft_clients:
                nft_data = all_data[(all_data['client_name'] == client) & 
                                  (all_data['data_type'] == 'nft')]
                
                if not nft_data.empty and nft_data.iloc[0]['success']:
                    data = nft_data.iloc[0]['data']
                    
                    st.subheader(f"🎨 {client} - {data.get('name', 'NFT Collection')}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Floor Price", f"{data.get('floor_price', 0):.4f} ETH")
                    with col2:
                        st.metric("24h Volume", f"{data.get('volume_24h', 0):.2f} ETH")
                    with col3:
                        st.metric("Owners", f"{data.get('owner_count', 0):,}")
                    with col4:
                        st.metric("Total Supply", f"{float(data.get('token_count', 0)):,}")
    
    with tabs[6]:  # Comparisons
        st.header("Multi-Client Comparisons")
        
        # Prepare normalized data for radar chart
        radar_data = {}
        metrics_for_radar = ['Market Cap', 'TVL', 'Holders', 'Telegram Users']
        
        for client in selected_clients:
            client_metrics = {}
            
            # Get various metrics
            price_data = all_data[(all_data['client_name'] == client) & 
                                (all_data['data_type'] == 'price')]
            if not price_data.empty and price_data.iloc[0]['success']:
                client_metrics['Market Cap'] = price_data.iloc[0]['data'].get('market_cap', 0)
            
            protocol_data = all_data[(all_data['client_name'] == client) & 
                                   (all_data['data_type'] == 'protocol')]
            if not protocol_data.empty and protocol_data.iloc[0]['success']:
                client_metrics['TVL'] = protocol_data.iloc[0]['data'].get('tvl', 0)
            
            comp_data = all_data[(all_data['client_name'] == client) & 
                               (all_data['data_type'] == 'comprehensive')]
            if not comp_data.empty and comp_data.iloc[0]['success']:
                data = comp_data.iloc[0]['data']
                client_metrics['Holders'] = data.get('holder_count', 0)
                client_metrics['Telegram Users'] = data.get('telegram_users', 0)
            
            # Normalize metrics (0-100 scale)
            radar_data[client] = client_metrics
        
        # Create comparison visualizations
        if radar_data:
            # Normalize the data
            max_values = {}
            for metric in metrics_for_radar:
                max_val = max([data.get(metric) or 0 for data in radar_data.values()])
                max_values[metric] = max_val if max_val > 0 else 1
            
            normalized_data = {}
            for client, metrics in radar_data.items():
                normalized_data[client] = {
                    metric: ((metrics.get(metric) or 0) / max_values[metric] if max_values[metric] else 0) * 100
                    for metric in metrics_for_radar
                }
            
            # Create radar chart
            fig = create_multi_metric_radar(normalized_data, metrics_for_radar)
            st.plotly_chart(fig, use_container_width=True)
            
            # Create comparison table
            # from detailed_table_component import create_detailed_comparison_table
            # comparison_df = create_detailed_comparison_table(selected_clients, all_data)

            st.header("Multi-Client Comparisons")
            # Collect all unique data fields across all clients
            comparison_data = []
            for client in selected_clients:
                row = {'Client': client}
                
                # Get all data for this client
                client_all_data = all_data[all_data['client_name'] == client]
                
                # Get logo URL
                logo_url = get_logo_url(client, all_data)
                if logo_url:
                    row['Logo'] = logo_url
                
                # Process each data type for this client
                for _, data_row in client_all_data.iterrows():
                    if data_row['success']:
                        data_type = data_row['data_type']
                        data = data_row['data']
                        
                        if data_type == 'price':
                            # Price data
                            price = data.get('price', 0)
                            if price > 1000:
                                row['Price'] = format_number(price)
                            else:
                                row['Price'] = f"${price:.4f}" if price < 1 else f"${price:.2f}"
                            
                            row['Market Cap'] = format_number(data.get('market_cap', 0))
                            row['24h Volume'] = format_number(data.get('volume_24h', 0))
                            row['24h Change'] = f"{data.get('price_change_24h') or 0:.2f}%"
                            
                            # Any other price fields
                            for key, value in data.items():
                                if key not in ['price', 'market_cap', 'volume_24h', 'price_change_24h']:
                                    if isinstance(value, (int, float)):
                                        row[key.replace('_', ' ').title()] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    else:
                                        row[key.replace('_', ' ').title()] = str(value)
                        
                        elif data_type == 'protocol':
                            # Protocol data
                            row['TVL'] = format_number(data.get('tvl', 0))
                            if data.get('twitter_handle'):
                                row['Twitter'] = f"@{data['twitter_handle']}"
                            if data.get('protocol_name'):
                                row['Protocol Name'] = data['protocol_name']
                            
                            # Any other protocol fields
                            for key, value in data.items():
                                if key not in ['tvl', 'twitter_handle', 'protocol_name', 'logo_url', 'contract_address', 'platform']:
                                    field_name = key.replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if key in ['tvl']:
                                            row[field_name] = format_number(value)
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    else:
                                        row[field_name] = str(value)
                        
                        elif data_type == 'comprehensive':
                            # Comprehensive data
                            if data.get('holder_count'):
                                row['Holders'] = f"{int(data['holder_count']):,}"
                            if data.get('market_cap_rank'):
                                row['Market Rank'] = f"#{int(data['market_cap_rank'])}"
                            if data.get('telegram_users'):
                                row['Telegram Users'] = f"{int(data['telegram_users']):,}"
                            if data.get('reddit_subscribers'):
                                row['Reddit Subscribers'] = f"{int(data['reddit_subscribers']):,}"
                            if data.get('sentiment_positive'):
                                row['Positive Sentiment'] = f"{data['sentiment_positive']:.2f}%"
                            if data.get('sentiment_negative'):
                                row['Negative Sentiment'] = f"{data['sentiment_negative']:.2f}%"
                            if data.get('categories'):
                                categories = data['categories']
                                row['Categories'] = ', '.join(categories[:3]) + ('...' if len(categories) > 3 else '')
                            
                            # Any other comprehensive fields
                            for key, value in data.items():
                                if key not in ['holder_count', 'market_cap_rank', 'telegram_users', 'reddit_subscribers', 
                                            'sentiment_positive', 'sentiment_negative', 'categories']:
                                    field_name = key.replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if key.endswith('_count'):
                                            row[field_name] = f"{int(value):,}"
                                        elif 'sentiment' in key or 'rate' in key:
                                            row[field_name] = f"{value:.2f}%"
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    elif isinstance(value, list):
                                        row[field_name] = f"[{len(value)} items]"
                                    else:
                                        row[field_name] = str(value)
                        
                        elif data_type == 'yields':
                            # Yields data
                            if data.get('total_staking_tvl'):
                                row['Staking TVL'] = format_number(data['total_staking_tvl'])
                            if data.get('average_apy'):
                                row['Average APY'] = f"{data['average_apy']:.2f}%"
                            if data.get('pool_count'):
                                row['Pool Count'] = f"{int(data['pool_count']):,}"
                            
                            # Any other yields fields
                            for key, value in data.items():
                                if key not in ['total_staking_tvl', 'average_apy', 'pool_count']:
                                    field_name = key.replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if 'tvl' in key:
                                            row[field_name] = format_number(value)
                                        elif 'apy' in key or 'rate' in key:
                                            row[field_name] = f"{value:.2f}%"
                                        elif 'count' in key:
                                            row[field_name] = f"{int(value):,}"
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    else:
                                        row[field_name] = str(value)
                        
                        elif data_type == 'mindshare':
                            # Mindshare data
                            if data.get('current_mindshare'):
                                row['Current Mindshare'] = f"{data['current_mindshare']:.6f}"
                            if data.get('avg_mindshare'):
                                row['Avg Mindshare'] = f"{data['avg_mindshare']:.6f}"
                            if data.get('data_points'):
                                row['Data Points'] = f"{int(data['data_points']):,}"
                            if data.get('mindshare_trend'):
                                trend = data['mindshare_trend']
                                if trend:
                                    trend_indicator = "📈" if len(trend) > 1 and trend[-1] > trend[0] else "📉"
                                    row['Mindshare Trend'] = f"{trend[-1]:.6f} {trend_indicator}"
                                else:
                                    row['Mindshare Trend'] = "N/A"
                            
                            # Any other mindshare fields
                            for key, value in data.items():
                                if key not in ['current_mindshare', 'avg_mindshare', 'data_points', 'mindshare_trend']:
                                    field_name = key.replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if 'mindshare' in key:
                                            row[field_name] = f"{value:.6f}"
                                        elif 'count' in key or 'points' in key:
                                            row[field_name] = f"{int(value):,}"
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    elif isinstance(value, list):
                                        if 'trend' in key:
                                            if value:
                                                trend_indicator = "📈" if len(value) > 1 and value[-1] > value[0] else "📉"
                                                row[field_name] = f"{value[-1]:.6f} {trend_indicator}"
                                            else:
                                                row[field_name] = "N/A"
                                        else:
                                            row[field_name] = f"[{len(value)} items]"
                                    else:
                                        row[field_name] = str(value)
                        
                        elif data_type == 'engagement':
                            # Engagement data
                            if data.get('total_documents'):
                                row['Total Documents'] = f"{int(data['total_documents']):,}"
                            if data.get('total_engagement'):
                                row['Total Engagement'] = f"{int(data['total_engagement']):,}"
                            if data.get('smart_engagement'):
                                row['Smart Engagement'] = f"{int(data['smart_engagement']):,}"
                            if data.get('engagement_rate'):
                                row['Engagement Rate'] = f"{data['engagement_rate']:.2f}%"
                            
                            # Any other engagement fields
                            for key, value in data.items():
                                if key not in ['total_documents', 'total_engagement', 'smart_engagement', 'engagement_rate']:
                                    field_name = key.replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if 'rate' in key:
                                            row[field_name] = f"{value:.2f}%"
                                        elif 'count' in key or 'total' in key or 'documents' in key or 'engagement' in key:
                                            row[field_name] = f"{int(value):,}"
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    else:
                                        row[field_name] = str(value)
                        
                        else:
                            # Handle other data types
                            for key, value in data.items():
                                if key not in ['logo_url', 'contract_address', 'platform']:
                                    field_name = f"{data_type}_{key}".replace('_', ' ').title()
                                    if isinstance(value, (int, float)):
                                        if key in ['price', 'tvl', 'volume_24h', 'market_cap', 'total_staking_tvl']:
                                            if value > 1000:
                                                row[field_name] = format_number(value)
                                            else:
                                                row[field_name] = f"${value:.4f}" if value < 1 else f"${value:.2f}"
                                        elif key in ['price_change_24h', 'average_apy', 'sentiment_positive', 'sentiment_negative', 'engagement_rate']:
                                            row[field_name] = f"{value:.2f}%"
                                        elif key in ['holder_count', 'telegram_users', 'reddit_subscribers', 'pool_count', 'data_points', 'total_documents']:
                                            row[field_name] = f"{int(value):,}"
                                        elif key in ['current_mindshare', 'avg_mindshare']:
                                            row[field_name] = f"{value:.6f}"
                                        elif key in ['total_engagement', 'smart_engagement']:
                                            row[field_name] = f"{int(value):,}"
                                        elif key == 'market_cap_rank':
                                            row[field_name] = f"#{int(value)}"
                                        else:
                                            row[field_name] = f"{value:,.2f}" if value > 100 else f"{value:.4f}"
                                    elif isinstance(value, list):
                                        if key == 'categories':
                                            row[field_name] = ', '.join(value[:3]) + ('...' if len(value) > 3 else '')
                                        elif key == 'mindshare_trend':
                                            if value:
                                                trend_indicator = "📈" if len(value) > 1 and value[-1] > value[0] else "📉"
                                                row[field_name] = f"{value[-1]:.6f} {trend_indicator}"
                                            else:
                                                row[field_name] = "N/A"
                                        else:
                                            row[field_name] = f"[{len(value)} items]"
                                    elif isinstance(value, str):
                                        if key == 'twitter_handle':
                                            row[field_name] = f"@{value}"
                                        else:
                                            row[field_name] = value
                                    else:
                                        row[field_name] = str(value)
                
                comparison_data.append(row)

            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True)

if __name__ == "__main__":
    main()