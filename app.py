# app.py
import streamlit as st
import yt_dlp
import os
import zipfile
import tempfile
from pathlib import Path
import json
from datetime import datetime
import re

# Page configuration
st.set_page_config(
    page_title="YouTube Music Stream & Download",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if 'playlist' not in st.session_state:
    st.session_state.playlist = []
if 'downloading' not in st.session_state:
    st.session_state.downloading = False
if 'downloaded_files' not in st.session_state:
    st.session_state.downloaded_files = []

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #FF0000;
        text-align: center;
        margin-bottom: 2rem;
    }
    .song-card {
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 1rem;
        background-color: #f9f9f9;
    }
    .playlist-item {
        padding: 0.5rem;
        border-bottom: 1px solid #eee;
    }
    .download-btn {
        background-color: #4CAF50;
        color: white;
    }
    .remove-btn {
        background-color: #ff4444;
        color: white;
    }
    .stProgress > div > div > div > div {
        background-color: #FF0000;
    }
</style>
""", unsafe_allow_html=True)

# Utility functions
def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def extract_video_info(url):
    """Extract video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'id': info['id'],
                'title': info['title'],
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'url': url
            }
    except Exception as e:
        st.error(f"Error extracting video info: {str(e)}")
        return None

def download_audio(url, output_path, progress_callback=None):
    """Download audio from YouTube and convert to MP3"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'progress_hooks': [progress_callback] if progress_callback else [],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Get the actual downloaded file path
            downloaded_file = output_path.parent / f"{output_path.stem}.mp3"
            return downloaded_file, info
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")

def download_progress_hook(d):
    """Progress hook for downloads"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        if total and downloaded:
            percentage = (downloaded / total) * 100
            st.session_state.download_progress = percentage

# Main app
def main():
    st.markdown('<h1 class="main-header">🎵 YouTube Music Stream & Download</h1>', unsafe_allow_html=True)
    
    # Sidebar for playlist management
    with st.sidebar:
        st.header("🎼 Your Playlist")
        
        if st.session_state.playlist:
            for i, item in enumerate(st.session_state.playlist):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{i+1}. {item['title'][:30]}...")
                with col2:
                    if st.button("❌", key=f"remove_{i}"):
                        st.session_state.playlist.pop(i)
                        st.rerun()
            
            st.markdown("---")
            
            # Playlist actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Playlist"):
                    save_playlist()
            with col2:
                if st.button("🗑️ Clear All"):
                    st.session_state.playlist = []
                    st.rerun()
            
            # Batch download options
            st.markdown("### 📦 Batch Download")
            download_format = st.selectbox(
                "Download as:",
                ["ZIP File", "Individual MP3s"]
            )
            
            if st.button("⬇️ Download All", type="primary"):
                with st.spinner("Preparing download..."):
                    download_playlist(download_format == "ZIP File")
        else:
            st.info("Your playlist is empty. Add songs from the main panel!")
        
        st.markdown("---")
        st.markdown("### 📥 Load Playlist")
        uploaded_file = st.file_uploader("Upload saved playlist", type=['json'])
        if uploaded_file:
            load_playlist(uploaded_file)
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["🎵 Stream & Download", "📋 Manage Playlist", "⚙️ Settings"])
    
    with tab1:
        st.header("Search and Download Music")
        
        # URL input
        col1, col2 = st.columns([3, 1])
        with col1:
            url = st.text_input(
                "Enter YouTube URL:",
                placeholder="https://www.youtube.com/watch?v=... or https://music.youtube.com/watch?v=..."
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Extract Info", use_container_width=True):
                if url:
                    with st.spinner("Extracting video information..."):
                        video_info = extract_video_info(url)
                        if video_info:
                            st.session_state.current_video = video_info
        
        # Display video info if available
        if 'current_video' in st.session_state and st.session_state.current_video:
            video = st.session_state.current_video
            
            col1, col2 = st.columns([1, 2])
            with col1:
                if video['thumbnail']:
                    st.image(video['thumbnail'], use_column_width=True)
            with col2:
                st.subheader(video['title'])
                st.write(f"👤 **Uploader:** {video['uploader']}")
                if video['duration'] > 0:
                    minutes = video['duration'] // 60
                    seconds = video['duration'] % 60
                    st.write(f"⏱️ **Duration:** {minutes}:{seconds:02d}")
                
                # Action buttons
                col_actions = st.columns(3)
                with col_actions[0]:
                    if st.button("➕ Add to Playlist", use_container_width=True):
                        if video not in st.session_state.playlist:
                            st.session_state.playlist.append(video)
                            st.success("Added to playlist!")
                            st.rerun()
                
                with col_actions[1]:
                    if st.button("▶️ Stream", use_container_width=True):
                        stream_audio(video['url'])
                
                with col_actions[2]:
                    if st.button("⬇️ Download MP3", type="primary", use_container_width=True):
                        download_single(video)
        
        # Batch URL input
        st.markdown("---")
        st.subheader("Batch Download from URLs")
        urls_text = st.text_area(
            "Enter multiple URLs (one per line):",
            height=100,
            placeholder="https://www.youtube.com/watch?v=...\nhttps://music.youtube.com/watch?v=...\n..."
        )
        
        if st.button("📥 Add All to Playlist", use_container_width=True):
            if urls_text:
                urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
                added_count = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, url in enumerate(urls):
                    status_text.text(f"Processing URL {i+1} of {len(urls)}...")
                    video_info = extract_video_info(url)
                    if video_info and video_info not in st.session_state.playlist:
                        st.session_state.playlist.append(video_info)
                        added_count += 1
                    progress_bar.progress((i + 1) / len(urls))
                
                status_text.text(f"✅ Added {added_count} new songs to playlist!")
                progress_bar.empty()
                st.rerun()
    
    with tab2:
        st.header("Playlist Management")
        
        if st.session_state.playlist:
            # Display playlist in detail
            for i, item in enumerate(st.session_state.playlist):
                with st.expander(f"{i+1}. {item['title']}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Uploader:** {item['uploader']}")
                        st.write(f"**URL:** {item['url']}")
                    with col2:
                        if st.button("Remove", key=f"remove_detail_{i}"):
                            st.session_state.playlist.pop(i)
                            st.rerun()
            
            # Playlist statistics
            st.markdown("---")
            col_stats = st.columns(3)
            with col_stats[0]:
                st.metric("Total Songs", len(st.session_state.playlist))
            with col_stats[1]:
                total_duration = sum(item.get('duration', 0) for item in st.session_state.playlist)
                hours = total_duration // 3600
                minutes = (total_duration % 3600) // 60
                st.metric("Total Duration", f"{hours}h {minutes}m")
        else:
            st.info("No songs in playlist. Add some songs from the Stream & Download tab!")
    
    with tab3:
        st.header("Settings")
        
        # Download quality settings
        st.subheader("Download Settings")
        quality = st.select_slider(
            "Audio Quality:",
            options=["128k", "192k", "256k", "320k"],
            value="192k"
        )
        
        # Storage location
        st.subheader("Storage")
        if st.button("Clear Temporary Files"):
            clear_temp_files()
        
        # About section
        st.markdown("---")
        st.subheader("About")
        st.markdown("""
        This app allows you to:
        - Stream audio from YouTube and YouTube Music
        - Download audio as MP3 files
        - Create and manage playlists
        - Batch download as ZIP files
        
        **Note:** Please respect copyright laws and only download content
        you have permission to download.
        """)

def stream_audio(url):
    """Stream audio directly"""
    try:
        # Create temporary file for streaming
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
            output_path = Path(tmp.name)
        
        # Download audio
        with st.spinner("Preparing stream..."):
            downloaded_file, info = download_audio(url, output_path)
            
            # Read file for streaming
            with open(downloaded_file, 'rb') as f:
                audio_bytes = f.read()
            
            # Display audio player
            st.audio(audio_bytes, format='audio/mp3')
            
            # Cleanup
            os.unlink(downloaded_file)
    
    except Exception as e:
        st.error(f"Streaming failed: {str(e)}")

def download_single(video_info):
    """Download single song"""
    try:
        filename = sanitize_filename(f"{video_info['title']}.mp3")
        output_path = Path(tempfile.gettempdir()) / filename
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total and downloaded:
                    percentage = (downloaded / total) * 100
                    progress_bar.progress(min(percentage, 100) / 100)
        
        status_text.text("Downloading audio...")
        downloaded_file, info = download_audio(
            video_info['url'], 
            output_path,
            progress_callback=update_progress
        )
        
        progress_bar.progress(1.0)
        status_text.text("Converting to MP3...")
        
        # Read file for download
        with open(downloaded_file, 'rb') as f:
            file_bytes = f.read()
        
        # Offer download
        st.download_button(
            label="📥 Click to Download MP3",
            data=file_bytes,
            file_name=filename,
            mime="audio/mpeg"
        )
        
        progress_bar.empty()
        status_text.text("✅ Ready to download!")
        
        # Cleanup
        os.unlink(downloaded_file)
        
    except Exception as e:
        st.error(f"Download failed: {str(e)}")

def download_playlist(as_zip=True):
    """Download entire playlist"""
    if not st.session_state.playlist:
        st.warning("Playlist is empty!")
        return
    
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            downloaded_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, item in enumerate(st.session_state.playlist):
                status_text.text(f"Downloading: {item['title'][:30]}...")
                filename = sanitize_filename(f"{i+1:02d}_{item['title']}.mp3")
                output_path = tmp_path / filename
                
                try:
                    downloaded_file, _ = download_audio(item['url'], output_path)
                    downloaded_files.append(downloaded_file)
                except Exception as e:
                    st.warning(f"Failed to download {item['title']}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(st.session_state.playlist))
            
            if downloaded_files:
                if as_zip:
                    # Create ZIP file
                    zip_path = tmp_path / "playlist.zip"
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for file in downloaded_files:
                            zipf.write(file, file.name)
                    
                    # Read ZIP file
                    with open(zip_path, 'rb') as f:
                        zip_bytes = f.read()
                    
                    # Offer download
                    st.download_button(
                        label="📦 Download Playlist as ZIP",
                        data=zip_bytes,
                        file_name=f"youtube_playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip"
                    )
                else:
                    # Create a download button for each file
                    for file in downloaded_files:
                        with open(file, 'rb') as f:
                            file_bytes = f.read()
                        
                        st.download_button(
                            label=f"⬇️ Download {file.name}",
                            data=file_bytes,
                            file_name=file.name,
                            mime="audio/mpeg",
                            key=f"download_{file.name}"
                        )
                
                status_text.text(f"✅ Downloaded {len(downloaded_files)} songs!")
            
            progress_bar.empty()
    
    except Exception as e:
        st.error(f"Batch download failed: {str(e)}")

def save_playlist():
    """Save playlist to JSON file"""
    if not st.session_state.playlist:
        st.warning("Playlist is empty!")
        return
    
    playlist_data = {
        'name': 'YouTube Playlist',
        'created': datetime.now().isoformat(),
        'songs': st.session_state.playlist
    }
    
    json_str = json.dumps(playlist_data, indent=2, ensure_ascii=False)
    
    st.download_button(
        label="💾 Download Playlist File",
        data=json_str,
        file_name=f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

def load_playlist(uploaded_file):
    """Load playlist from uploaded JSON file"""
    try:
        playlist_data = json.load(uploaded_file)
        
        if 'songs' in playlist_data:
            loaded_songs = playlist_data['songs']
            current_urls = {song['url'] for song in st.session_state.playlist}
            
            new_songs = []
            for song in loaded_songs:
                if song['url'] not in current_urls:
                    new_songs.append(song)
            
            if new_songs:
                st.session_state.playlist.extend(new_songs)
                st.success(f"Added {len(new_songs)} songs from playlist file!")
                st.rerun()
            else:
                st.info("No new songs to add from this file.")
    except Exception as e:
        st.error(f"Failed to load playlist: {str(e)}")

def clear_temp_files():
    """Clear temporary files"""
    temp_dir = tempfile.gettempdir()
    deleted = 0
    
    for file in Path(temp_dir).glob("*.mp3"):
        try:
            file.unlink()
            deleted += 1
        except:
            pass
    
    for file in Path(temp_dir).glob("*.part"):
        try:
            file.unlink()
            deleted += 1
        except:
            pass
    
    st.success(f"Cleaned up {deleted} temporary files!")

if __name__ == "__main__":
    main()
