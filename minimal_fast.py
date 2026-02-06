# minimal_fast.py - Super simple version
import streamlit as st
import yt_dlp
import tempfile
from pathlib import Path

st.set_page_config(page_title="Fast YT Downloader", layout="centered")

def extract_info_simple(url):
    """Super simple extraction"""
    with yt_dlp.YoutubeDL({
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'socket_timeout': 10,
    }) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
            }
        except:
            return None

def download_simple(url):
    """Simple download with minimal options"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
        output_path = Path(tmp.name)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path),
        'quiet': False,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'socket_timeout': 30,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            mp3_file = output_path.with_suffix('.mp3')
            
            with open(mp3_file, 'rb') as f:
                return f.read(), info.get('title', 'audio.mp3')
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None, None

# UI
st.title("⚡ Fast YouTube Downloader")

url = st.text_input("YouTube URL:")

if st.button("Quick Download") and url:
    with st.spinner("Processing..."):
        # Extract info
        info = extract_info_simple(url)
        if info:
            st.success(f"Found: {info['title']}")
            
            # Download
            audio_data, filename = download_simple(url)
            if audio_data:
                st.download_button(
                    "Download MP3",
                    data=audio_data,
                    file_name=f"{filename}.mp3",
                    mime="audio/mpeg"
                )
        else:
            st.error("Could not process URL")
