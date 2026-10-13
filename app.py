import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime
import instaloader

# --- API Setup ---
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    YOUTUBE_API_KEY = "" # Fallback if secrets are not configured yet

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

def get_videos_via_playlist(channel_id, keyword, after_date, before_date):
    matched = []
    try:
        req = youtube.channels().list(part="contentDetails", id=channel_id)
        res = req.execute()
        if not res.get("items"): return matched
        
        uploads_playlist = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        next_page = None
        
        while True:
            req = youtube.playlistItems().list(part="snippet", playlistId=uploads_playlist, maxResults=50, pageToken=next_page)
            res = req.execute()
            items = res.get("items", [])
            if not items: break
                
            oldest_in_page = None
            for item in items:
                pub_date = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
                oldest_in_page = pub_date
                
                if after_date <= pub_date <= before_date:
                    title = item["snippet"].get("title", "").lower()
                    desc = item["snippet"].get("description", "").lower()
                    if keyword.lower() in title or keyword.lower() in desc:
                        # Return video title and a clickable YouTube link
                        video_id = item["snippet"]["resourceId"]["videoId"]
                        matched.append(f"{title} (Link: https://youtu.be/{video_id})")
            
            if oldest_in_page and oldest_in_page < after_date:
                break
            next_page = res.get("nextPageToken")
            if not next_page: break
    except Exception:
        pass
    return matched

# --- Instagram Logic ---
def get_instagram_posts(username, keyword, after_date, before_date):
    matched = []
    L = instaloader.Instaloader(quiet=True)
    try:
        # Clean up input in case they paste a URL or add an @ symbol
        username = username.strip().replace('@', '').split('/')[-1]
        profile = instaloader.Profile.from_username(L.context, username)
        
        # Instaloader fetches from newest to oldest
        for post in profile.get_posts():
            if post.date_utc > before_date:
                continue
            if post.date_utc < after_date:
                break # We have passed the target date range, stop fetching
                
            caption = post.caption.lower() if post.caption else ""
            if keyword.lower() in caption:
                # Format a clean snippet of the caption
                display_caption = post.caption.replace('\n', ' ')[:80] + "..." if post.caption else "No caption"
                matched.append(f"{post.date_utc.strftime('%Y-%m-%d')} - {display_caption} (Link: https://instagram.com/p/{post.shortcode}/)")
                
    except Exception as e:
        st.error(f"Instagram restriction encountered: {e}. Note: Instagram aggressively rate-limits public scrapers.")
    return matched

# --- Web App UI ---
st.title("Social Media Keyword & Timeline Tracker")
st.write("Search a YouTube channel or Instagram profile for a keyword within a specific date range.")

# Platform selection toggle
platform = st.radio("Select Platform:", ("YouTube", "Instagram"))

if platform == "YouTube":
    account_input = st.text_input("Enter YouTube Channel URL or Handle (e.g., @ManojDey):")
else:
    account_input = st.text_input("Enter Instagram Username (e.g., cristiano):")

keyword_input = st.text_input("Enter Keyword (e.g., CoinDCX):")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

if st.button(f"Search {platform}"):
    if account_input and keyword_input:
        with st.spinner(f"Scanning {platform} history..."):
            
            # Convert UI dates to datetime objects for accurate comparison
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            
            # Route to correct platform logic
            if platform == "YouTube":
                ch_id = resolve_channel_id(account_input)
                if not ch_id:
                    st.error("Could not resolve channel ID. Check the URL.")
                else:
                    results = get_videos_via_playlist(ch_id, keyword_input, start_dt, end_dt)
                    if results:
                        st.success(f"Found {len(results)} video(s) matching '{keyword_input}'!")
                        for r in results:
                            st.write(f"- {r}")
                    else:
                        st.warning("No videos found matching that keyword in this timeframe.")
                        
            elif platform == "Instagram":
                results = get_instagram_posts(account_input, keyword_input, start_dt, end_dt)
                if results:
                    st.success(f"Found {len(results)} post(s) matching '{keyword_input}'!")
                    for r in results:
                        st.write(f"- {r}")
                else:
                    st.warning("No posts found matching that keyword in this timeframe.")