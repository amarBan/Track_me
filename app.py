import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Keyword Tracker", layout="wide")

# --- Custom CSS for Apple Minimalist Vibe ---
st.markdown("""
    <style>
        /* Apple-style typography and spacing */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        h1 {
            font-weight: 600;
            color: #1D1D1F;
            letter-spacing: -0.02em;
        }
        /* Mute the standard Streamlit top padding */
        .block-container {
            padding-top: 2rem;
            max-width: 1000px;
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
                    title = item["snippet"].get("title", "").lower()
                    desc = item["snippet"].get("description", "").lower()
                    if keyword.lower() in title or keyword.lower() in desc:
                        vid_id = item["snippet"]["resourceId"]["videoId"]
                        video_ids.append(vid_id)
                        matched_videos.append({
                            "Video ID": vid_id,
                            "Title": item["snippet"].get("title", ""),
                            "Date": pub_date.strftime("%Y-%m-%d"),
                        })
            
            if oldest_in_page and oldest_in_page < after_date:
                break
            next_page = res.get("nextPageToken")
            if not next_page: break
            
        if not matched_videos:
            return pd.DataFrame()
            
        # Fetch metrics for all matched videos
        metrics = get_video_metrics(video_ids)
        
        # Merge metrics into the final dataset
        for vid in matched_videos:
            vid_stats = metrics.get(vid["Video ID"], {"views": 0, "likes": 0, "comments": 0, "eng_rate": 0})
            vid["Views"] = vid_stats["views"]
            vid["Likes"] = vid_stats["likes"]
            vid["Comments"] = vid_stats["comments"]
            vid["Engagement Rate (%)"] = round(vid_stats["eng_rate"], 2)
            
        return pd.DataFrame(matched_videos)

    except Exception as e:
        return pd.DataFrame()

# --- Web App UI ---
st.title("Keyword Intelligence")
st.markdown("Track and visualize content performance across specific timelines.", unsafe_allow_html=True)
st.write("---")

platform = st.radio("Select Platform:", ("YouTube", "Instagram"), horizontal=True)

if platform == "Instagram":
    st.info("🚧 **Instagram Search is currently Under Development.** Please switch back to YouTube to continue your analysis.")
else:
    # YouTube UI
    col1, col2 = st.columns([2, 1])
    with col1:
        account_input = st.text_input("YouTube Channel (URL or Handle):", placeholder="e.g., @Apple")
    with col2:
        keyword_input = st.text_input("Keyword Target:", placeholder="e.g., CoinDCX")

    col3, col4 = st.columns(2)
    with col3:
        start_date = st.date_input("Start Date")
    with col4:
        end_date = st.date_input("End Date")

    if st.button("Generate Visualization"):
        if account_input and keyword_input:
            with st.spinner("Compiling channel data..."):
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                
                ch_id = resolve_channel_id(account_input)
                
                if not ch_id:
                    st.error("Could not resolve channel ID. Check the URL.")
                else:
                    df = get_videos_via_playlist(ch_id, keyword_input, start_dt, end_dt)
                    
                    if not df.empty:
                        # Sort by date for proper charting
                        df = df.sort_values(by="Date")
                        
                        # --- KPI Cards ---
                        st.write("---")
                        kpi1, kpi2, kpi3 = st.columns(3)
                        kpi1.metric("Total Matched Videos", len(df))
                        kpi2.metric("Average Views", f"{int(df['Views'].mean()):,}")
                        kpi3.metric("Avg Engagement Rate", f"{df['Engagement Rate (%)'].mean():.2f}%")
                        st.write("---")
                        
                        # --- Apple Minimalist Chart Design ---
                        # Create a dual-axis chart (Views on left, Engagement on right)
                        fig = go.Figure()

                        # Bar chart for Views (Subtle Blue)
                        fig.add_trace(go.Bar(
                            x=df['Date'],
                            y=df['Views'],
                            name='Views',
                            marker_color='#007AFF', # Apple Blue
                            opacity=0.8,
                            customdata=df['Title'],
                            hovertemplate="<b>%{customdata}</b><br>Date: %{x}<br>Views: %{y:,}<extra></extra>"
                        ))

                        # Line chart for Engagement Rate (Minimal Gray/Black)
                        fig.add_trace(go.Scatter(
                            x=df['Date'],
                            y=df['Engagement Rate (%)'],
                            name='Engagement Rate (%)',
                            yaxis='y2',
                            mode='lines+markers',
                            line=dict(color='#1D1D1F', width=3),
                            marker=dict(size=8, color='#1D1D1F'),
                            hovertemplate="Engagement: %{y}%<extra></extra>"
                        ))

                        # Layout styling (Clean, white background, no grid lines)
                        fig.update_layout(
                            title=dict(text=f"Performance Timeline: '{keyword_input}'", font=dict(size=20, color='#1D1D1F')),
                            plot_bgcolor='white',
                            paper_bgcolor='white',
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            margin=dict(l=0, r=0, t=60, b=0),
                            yaxis=dict(
                                title="Total Views",
                                showgrid=True,
                                gridcolor='#F5F5F7',
                                zeroline=False
                            ),
                            yaxis2=dict(
                                title="Engagement Rate (%)",
                                overlaying='y',
                                side='right',
                                showgrid=False,
                                zeroline=False
                            ),
                            xaxis=dict(
                                showgrid=False,
                                zeroline=False,
                                tickangle=-45
                            )
                        )

                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Data table below chart
                        with st.expander("View Raw Data"):
                            st.dataframe(df.drop(columns=['Video ID']), use_container_width=True)
                            
                    else:
                        st.warning("No videos found matching that keyword in this timeframe.")
