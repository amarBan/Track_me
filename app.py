import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Keyword Intelligence Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Apple Pro Dark Aesthetic ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        /* Global Reset & Pro Dark Theme */
        html, body, [class*="css"], .stApp {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif !important;
            background-color: #0A0A0C !important;
            color: #F5F5F7 !important;
        }
        
        #MainMenu, header, footer {visibility: hidden;}
        
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
            max-width: 1200px;
        }

        /* Dark Card Elevation */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #16161A 0%, #111114 100%) !important;
            border-radius: 18px !important;
            padding: 22px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6) !important;
            backdrop-filter: blur(20px);
            transition: all 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            border-color: rgba(10, 132, 255, 0.4) !important;
            transform: translateY(-2px);
        }
        div[data-testid="stMetricValue"] {
            font-size: 32px !important;
            font-weight: 700 !important;
            color: #FFFFFF !important;
            letter-spacing: -0.02em !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 12px !important;
            font-weight: 600 !important;
            color: #8E8E93 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.8px !important;
        }

        /* Inputs & Date Pickers in Dark Mode */
        .stTextInput input, .stDateInput input {
            background-color: #16161A !important;
            color: #FFFFFF !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            padding: 12px 16px !important;
            transition: all 0.2s ease;
        }
        .stTextInput input:focus, .stDateInput input:focus {
            border-color: #0A84FF !important;
            box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.25) !important;
        }

        /* Action Buttons */
        .stButton>button {
            width: 100%;
            background: linear-gradient(180deg, #0A84FF 0%, #0066CC 100%) !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            border-radius: 12px !important;
            padding: 12px 20px !important;
            border: none !important;
            box-shadow: 0 4px 18px rgba(10, 132, 255, 0.35) !important;
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            transform: scale(1.01);
            box-shadow: 0 6px 24px rgba(10, 132, 255, 0.5) !important;
        }

        /* Section Subheaders */
        .section-header {
            font-size: 19px;
            font-weight: 600;
            color: #F5F5F7;
            margin-top: 1.8rem;
            margin-bottom: 0.8rem;
            letter-spacing: -0.01em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Radio Toggle */
        div[role="radiogroup"] {
            background-color: #16161A;
            padding: 4px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            display: inline-flex;
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
                metrics[vid] = {
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "eng_rate": eng_rate
                }
        except Exception:
            pass
    return metrics

def get_videos_via_playlist(channel_id, keyword, after_date, before_date):
    matched_videos = []
    video_ids = []
    
    try:
        req = youtube.channels().list(part="contentDetails", id=channel_id)
        res = req.execute()
        if not res.get("items"): 
            return pd.DataFrame()
        
        uploads_playlist = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        next_page = None
        
        while True:
            req = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist,
                maxResults=50,
                pageToken=next_page
            )
            res = req.execute()
            items = res.get("items", [])
            if not items:
                break
                
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
                        short_title = title if len(title) < 36 else title[:33] + "..."
                        matched_videos.append({
                            "Video ID": vid_id,
                            "Title": title,
                            "Short Title": short_title,
                            "PublishedAt": pub_date,
                            "Date": pub_date.strftime("%b %d, %Y"),
                            "Timestamp": pub_date.strftime("%Y-%m-%d %H:%M")
                        })
            
            if oldest_in_page and oldest_in_page < after_date:
                break
            next_page = res.get("nextPageToken")
            if not next_page: 
                break
            
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

# Common Plotly dark config
DARK_PLOT_CONFIG = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    'displaylogo': False,
    'responsive': True
}

# --- Header UI ---
st.markdown("<h1 style='font-size: 2.2rem; margin-bottom: 0px;'>Keyword Intelligence <span style='color: #0A84FF;'>Pro</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #8E8E93; font-size: 15px; margin-bottom: 24px;'>Dark-mode analytics & video-level performance telemetry.</p>", unsafe_allow_html=True)

platform = st.radio("Platform", ("YouTube", "Instagram"), horizontal=True, label_visibility="collapsed")

if platform == "Instagram":
    st.info("⚡ **Instagram Scraper:** Under security overhaul. Use YouTube for real-time telemetry.")
else:
    col1, col2 = st.columns([2.2, 1.2])
    with col1:
        account_input = st.text_input("Channel URL / Handle", placeholder="e.g. @ManojDey or https://youtube.com/channel/...")
    with col2:
        keyword_input = st.text_input("Keyword", placeholder="e.g. CoinDCX")

    col3, col4, col5 = st.columns([1, 1, 1])
    with col3:
        start_date = st.date_input("Start Date")
    with col4:
        end_date = st.date_input("End Date")
    with col5:
        st.write("")
        st.write("")
        submit_btn = st.button("Run Audit")

    if submit_btn:
        if account_input and keyword_input:
            with st.spinner("Extracting uploads and computing telemetry..."):
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                
                ch_id = resolve_channel_id(account_input)
                
                if not ch_id:
                    st.error("Failed to resolve Channel ID. Verify URL or handle syntax.")
                else:
                    df = get_videos_via_playlist(ch_id, keyword_input, start_dt, end_dt)
                    
                    if not df.empty:
                        # Chronological sorting by exact publishing timestamp
                        df = df.sort_values(by="PublishedAt").reset_index(drop=True)
                        
                        # --- KPI Cards ---
                        st.markdown("<br>", unsafe_allow_html=True)
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Matched Videos", f"{len(df):,}")
                        k2.metric("Total Views", f"{int(df['Views'].sum()):,}")
                        k3.metric("Total Engagements", f"{int(df['Likes'].sum() + df['Comments'].sum()):,}")
                        k4.metric("Avg Engagement", f"{df['Engagement Rate (%)'].mean():.2f}%")
                        
                        # --- Chart 1: Performance Timeline (Dual Axis Dark) ---
                        st.markdown("<div class='section-header'>📈 Timeline Telemetry (Views vs Engagement Rate)</div>", unsafe_allow_html=True)
                        
                        fig1 = go.Figure()
                        
                        # Views - Vibrant Neon Blue Bars
                        fig1.add_trace(go.Bar(
                            x=df['Timestamp'],
                            y=df['Views'],
                            name='Views',
                            marker=dict(
                                color='#0A84FF',
                                line=dict(color='rgba(255,255,255,0.1)', width=1)
                            ),
                            opacity=0.88,
                            customdata=df[['Title', 'Views', 'Engagement Rate (%)']],
                            hovertemplate=(
                                "<b>%{customdata[0]}</b><br><br>"
                                "🗓 Uploaded: %{x}<br>"
                                "👁 Views: <b>%{customdata[1]:,}</b><br>"
                                "⚡ Engagement: <b>%{customdata[2]}%</b>"
                                "<extra></extra>"
                            )
                        ))
                        
                        # Engagement Rate - Neon Amber Smooth Line
                        fig1.add_trace(go.Scatter(
                            x=df['Timestamp'],
                            y=df['Engagement Rate (%)'],
                            name='Eng. Rate (%)',
                            yaxis='y2',
                            mode='lines+markers',
                            line=dict(color='#FF9F0A', width=3, shape='spline'),
                            marker=dict(size=7, color='#FF9F0A', symbol='circle', line=dict(color='#0A0A0C', width=1.5)),
                            customdata=df[['Title', 'Engagement Rate (%)']],
                            hovertemplate="⚡ <b>%{customdata[0]}</b><br>Rate: <b>%{customdata[1]}%</b><extra></extra>"
                        ))

                        fig1.update_layout(
                            template='plotly_dark',
                            plot_bgcolor='#111114',
                            paper_bgcolor='#111114',
                            hovermode="x unified",
                            margin=dict(l=20, r=20, t=30, b=40),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1,
                                font=dict(color='#8E8E93', size=12)
                            ),
                            xaxis=dict(
                                showgrid=True,
                                gridcolor='rgba(255,255,255,0.06)',
                                tickangle=-30,
                                rangeslider=dict(visible=True, thickness=0.06, bgcolor='#16161A')
                            ),
                            yaxis=dict(
                                title=dict(text="Views", font=dict(color='#0A84FF')),
                                tickfont=dict(color='#0A84FF'),
                                showgrid=True,
                                gridcolor='rgba(255,255,255,0.06)'
                            ),
                            yaxis2=dict(
                                title=dict(text="Eng. Rate (%)", font=dict(color='#FF9F0A')),
                                tickfont=dict(color='#FF9F0A'),
                                overlaying='y',
                                side='right',
                                showgrid=False
                            )
                        )
                        st.plotly_chart(fig1, use_container_width=True, config=DARK_PLOT_CONFIG)
                        
                        # --- Chart 2: Per-Video Engagement Breakdown (Likes vs Comments) ---
                        st.markdown("<div class='section-header'>📊 Video-Level Breakdown (Likes vs Comments)</div>", unsafe_allow_html=True)
                        
                        fig2 = go.Figure()
                        
                        fig2.add_trace(go.Bar(
                            x=df['Short Title'],
                            y=df['Likes'],
                            name='Likes',
                            marker_color='#FF375F',
                            customdata=df['Title'],
                            hovertemplate="<b>%{customdata}</b><br>❤️ Likes: <b>%{y:,}</b><extra></extra>"
                        ))
                        
                        fig2.add_trace(go.Bar(
                            x=df['Short Title'],
                            y=df['Comments'],
                            name='Comments',
                            marker_color='#30D158',
                            customdata=df['Title'],
                            hovertemplate="<b>%{customdata}</b><br>💬 Comments: <b>%{y:,}</b><extra></extra>"
                        ))

                        fig2.update_layout(
                            template='plotly_dark',
                            barmode='group',
                            plot_bgcolor='#111114',
                            paper_bgcolor='#111114',
                            hovermode="closest",
                            margin=dict(l=20, r=20, t=30, b=50),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1,
                                font=dict(color='#8E8E93', size=12)
                            ),
                            xaxis=dict(
                                showgrid=False,
                                tickangle=-30
                            ),
                            yaxis=dict(
                                title=dict(text="Interactions"),
                                showgrid=True,
                                gridcolor='rgba(255,255,255,0.06)'
                            )
                        )
                        st.plotly_chart(fig2, use_container_width=True, config=DARK_PLOT_CONFIG)
                        
                        # --- Apple Dark Interactive Data Table ---
                        st.markdown("<div class='section-header'>📋 Video Audit Index</div>", unsafe_allow_html=True)
                        
                        display_df = df[['Date', 'Title', 'Views', 'Likes', 'Comments', 'Engagement Rate (%)', 'URL']]
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "URL": st.column_config.LinkColumn("Link", display_text="Open ↗"),
                                "Views": st.column_config.NumberColumn("Views", format="%d"),
                                "Likes": st.column_config.NumberColumn("Likes", format="%d"),
                                "Comments": st.column_config.NumberColumn("Comments", format="%d"),
                                "Engagement Rate (%)": st.column_config.ProgressColumn(
                                    "Eng. Rate (%)",
                                    format="%.2f%%",
                                    min_value=0,
                                    max_value=max(float(df["Engagement Rate (%)"].max()), 5.0)
                                )
                            }
                        )
                    else:
                        st.warning("No videos matched the keyword criteria within this timeframe.")
