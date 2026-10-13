import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Keyword Intelligence", layout="wide", initial_sidebar_state="collapsed")

# --- Custom CSS for Apple Minimalist Dashboard Vibe ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
        
        /* Global Typography & Background */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: #F5F5F7; /* Apple subtle gray */
        }
        
        /* Hide default Streamlit UI elements for an 'App' feel */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Main Container Padding Optimization for Mobile & Web */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 1200px;
        }

        /* Metric Cards Styling (Apple Glassmorphism / Shadow) */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            border: 1px solid rgba(0,0,0,0.05);
            transition: transform 0.2s ease-in-out;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
        }
        div[data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 600 !important;
            color: #1D1D1F !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 13px !important;
            font-weight: 500 !important;
            color: #86868B !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Input Fields Styling */
        .stTextInput input, .stDateInput input {
            border-radius: 12px !important;
            border: 1px solid #E5E5EA !important;
            padding: 12px 16px !important;
            background-color: #FFFFFF !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
        }
        .stTextInput input:focus, .stDateInput input:focus {
            border-color: #007AFF !important;
            box-shadow: 0 0 0 3px rgba(0,122,255,0.2) !important;
        }

        /* Primary Button Styling */
        .stButton>button {
            width: 100%;
            background-color: #1D1D1F;
            color: white;
            border-radius: 12px;
            padding: 12px 24px;
            font-weight: 500;
            border: none;
            box-shadow: 0 4px 14px 0 rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            background-color: #434344;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            color: white;
        }

        /* Headings */
        h1, h2, h3 {
            color: #1D1D1F !important;
            font-weight: 600 !important;
            letter-spacing: -0.02em !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- API Setup ---
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    YOUTUBE_API_KEY = "" 

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# --- YouTube Logic ---
def resolve_channel_id(url):
    url = str(url).strip()
    try:
        if '@' in url:
            handle = "@" + url.split('@')[-1].split('/')[0]
            req = youtube.channels().list(part="id", forHandle=handle)
            res = req.execute()
            if res.get("items"):
                return res["items"][0]["id"]
        elif '/channel/' in url:
            return url.split('/channel/')[-1].split('/')[0]
    except Exception:
        pass
    return None

def get_video_metrics(video_ids):
    metrics = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        try:
            req = youtube.videos().list(part="statistics", id=",".join(chunk))
            res = req.execute()
            for item in res.get("items", []):
                vid = item["id"]
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))
                
                eng_rate = ((likes + comments) / views * 100) if views > 0 else 0
                metrics[vid] = {"views": views, "likes": likes, "comments": comments, "eng_rate": eng_rate}
        except Exception:
            pass
    return metrics

def get_videos_via_playlist(channel_id, keyword, after_date, before_date):
    matched_videos = []
    video_ids = []
    
    try:
        req = youtube.channels().list(part="contentDetails", id=channel_id)
        res = req.execute()
        if not res.get("items"): return pd.DataFrame()
        
        uploads_playlist = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        next_page = None
        
        while True:
            req = youtube.playlistItems().list(part="snippet", playlistId=uploads_playlist, maxResults=50, pageToken=next_page)
            res = req.execute()
            items = res.get("items", [])
            if not items: break
                
            oldest_in_page = None
            for item in items:
                pub_date_str = item["snippet"]["publishedAt"]
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
                oldest_in_page = pub_date
                
                if after_date <= pub_date <= before_date:
                    title = item["snippet"].get("title", "")
                    desc = item["snippet"].get("description", "")
                    if keyword.lower() in title.lower() or keyword.lower() in desc.lower():
                        vid_id = item["snippet"]["resourceId"]["videoId"]
                        video_ids.append(vid_id)
                        # Truncate title for cleaner charts
                        short_title = title if len(title) < 40 else title[:37] + "..."
                        matched_videos.append({
                            "Video ID": vid_id,
                            "Title": title,
                            "Short Title": short_title,
                            "Date": pub_date.strftime("%Y-%m-%d"),
                        })
            
            if oldest_in_page and oldest_in_page < after_date:
                break
            next_page = res.get("nextPageToken")
            if not next_page: break
            
        if not matched_videos:
            return pd.DataFrame()
            
        metrics = get_video_metrics(video_ids)
        
        for vid in matched_videos:
            vid_stats = metrics.get(vid["Video ID"], {"views": 0, "likes": 0, "comments": 0, "eng_rate": 0})
            vid["Views"] = vid_stats["views"]
            vid["Likes"] = vid_stats["likes"]
            vid["Comments"] = vid_stats["comments"]
            vid["Engagement Rate (%)"] = round(vid_stats["eng_rate"], 2)
            vid["URL"] = f"https://youtu.be/{vid['Video ID']}"
            
        return pd.DataFrame(matched_videos)

    except Exception:
        return pd.DataFrame()

# --- Common Plotly Config for Mobile Responsiveness ---
PLOT_CONFIG = {
    'displayModeBar': False, # Hides the clunky toolbar
    'responsive': True       # Ensures the chart resizes beautifully on rotation/mobile
}

# --- Web App UI ---
st.markdown("<h1>Keyword Intelligence</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #86868B; margin-top: -10px; margin-bottom: 30px;'>Track and visualize content performance across specific timelines.</p>", unsafe_allow_html=True)

platform = st.radio("Platform", ("YouTube", "Instagram"), horizontal=True, label_visibility="collapsed")

if platform == "Instagram":
    st.info("🚧 **Instagram Search is currently Under Development.** Please switch back to YouTube.")
else:
    # --- Input Section ---
    col1, col2 = st.columns([2, 1])
    with col1:
        account_input = st.text_input("YouTube Channel (URL or Handle)", placeholder="e.g., @TradeIQVaranasi")
    with col2:
        keyword_input = st.text_input("Keyword Target", placeholder="e.g., CoinDCX")

    col3, col4, col5 = st.columns([1, 1, 1])
    with col3:
        start_date = st.date_input("Start Date")
    with col4:
        end_date = st.date_input("End Date")
    with col5:
        st.write("") # Spacing
        st.write("")
        submit_btn = st.button("Generate Dashboard")

    if submit_btn:
        if account_input and keyword_input:
            with st.spinner("Processing channel data..."):
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                
                ch_id = resolve_channel_id(account_input)
                
                if not ch_id:
                    st.error("Could not resolve channel ID. Check the URL.")
                else:
                    df = get_videos_via_playlist(ch_id, keyword_input, start_dt, end_dt)
                    
                    if not df.empty:
                        df = df.sort_values(by="Date")
                        
                        # --- KPI Metric Cards ---
                        st.markdown("<br>", unsafe_allow_html=True)
                        kpi1, kpi2, kpi3 = st.columns(3)
                        kpi1.metric("Matched Videos", len(df))
                        kpi2.metric("Total Views", f"{int(df['Views'].sum()):,}")
                        kpi3.metric("Avg Engagement Rate", f"{df['Engagement Rate (%)'].mean():.2f}%")
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # --- Chart 1: Timeline Performance (Views vs Engagement) ---
                        st.markdown("### Performance Timeline")
                        fig_timeline = go.Figure()
                        
                        # Views Bar
                        fig_timeline.add_trace(go.Bar(
                            x=df['Date'], y=df['Views'], name='Views',
                            marker_color='#007AFF', opacity=0.85,
                            customdata=df['Short Title'],
                            hovertemplate="<b>%{customdata}</b><br>Views: %{y:,}<extra></extra>"
                        ))
                        # Engagement Line
                        fig_timeline.add_trace(go.Scatter(
                            x=df['Date'], y=df['Engagement Rate (%)'], name='Engagement Rate (%)',
                            yaxis='y2', mode='lines+markers',
                            line=dict(color='#1D1D1F', width=3), marker=dict(size=8, color='#1D1D1F'),
                            hovertemplate="Engagement: %{y}%<extra></extra>"
                        ))

                        fig_timeline.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
                            margin=dict(l=0, r=0, t=40, b=0),
                            yaxis=dict(title="Views", showgrid=True, gridcolor='#E5E5EA', zeroline=False),
                            yaxis2=dict(title="Eng. Rate (%)", overlaying='y', side='right', showgrid=False, zeroline=False),
                            xaxis=dict(showgrid=False, zeroline=False, tickangle=-45)
                        )
                        st.plotly_chart(fig_timeline, use_container_width=True, config=PLOT_CONFIG)
                        
                        st.markdown("<br><br>", unsafe_allow_html=True)

                        # --- Chart 2: Specific Video Breakdown (Likes & Comments) ---
                        st.markdown("### Video Engagement Breakdown")
                        fig_breakdown = go.Figure()
                        
                        fig_breakdown.add_trace(go.Bar(
                            x=df['Short Title'], y=df['Likes'], name='Likes',
                            marker_color='#FF2D55', # Apple Pink/Red
                            hovertemplate="Likes: %{y:,}<extra></extra>"
                        ))
                        fig_breakdown.add_trace(go.Bar(
                            x=df['Short Title'], y=df['Comments'], name='Comments',
                            marker_color='#FF9500', # Apple Orange
                            hovertemplate="Comments: %{y:,}<extra></extra>"
                        ))

                        fig_breakdown.update_layout(
                            barmode='group',
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
                            margin=dict(l=0, r=0, t=40, b=0),
                            yaxis=dict(showgrid=True, gridcolor='#E5E5EA', zeroline=False),
                            xaxis=dict(showgrid=False, zeroline=False, tickangle=-45)
                        )
                        st.plotly_chart(fig_breakdown, use_container_width=True, config=PLOT_CONFIG)
                        
                        st.markdown("<br>", unsafe_allow_html=True)

                        # --- Apple-Style Interactive Data Table ---
                        st.markdown("### Raw Data Audit")
                        
                        # Prepare clean dataframe for display
                        display_df = df[['Date', 'Title', 'Views', 'Likes', 'Comments', 'Engagement Rate (%)', 'URL']]
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "URL": st.column_config.LinkColumn("Watch Link", display_text="Open Video"),
                                "Views": st.column_config.NumberColumn(format="%d"),
                                "Likes": st.column_config.NumberColumn(format="%d"),
                                "Comments": st.column_config.NumberColumn(format="%d"),
                                "Engagement Rate (%)": st.column_config.ProgressColumn(
                                    "Eng. Rate (%)",
                                    help="Total interactions relative to views",
                                    format="%.2f%%",
                                    min_value=0,
                                    max_value=15, # Cap visual bar at 15% for cleaner scaling
                                )
                            }
                        )
                            
                    else:
                        st.warning("No videos found matching that keyword in this timeframe.")
