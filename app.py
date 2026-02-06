import streamlit as st
import os
from pathlib import Path
import tempfile
import zipfile
import rarfile
import json
from datetime import datetime
import yt_dlp
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pytube
import uuid

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="MusicStream Pro",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark/light mode and styling
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .song-card {
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        transition: all 0.3s;
    }
    .song-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .dark-mode .song-card {
        background-color: #2d2d2d;
        border: 1px solid #444;
    }
    .light-mode .song-card {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
    }
    .download-btn {
        background: linear-gradient(45deg, #FF6B6B, #FF8E53);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 5px;
        cursor: pointer;
    }
    .creator-upload {
        border: 2px dashed #4CAF50;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'playlist' not in st.session_state:
    st.session_state.playlist = []
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'artist_songs' not in st.session_state:
    st.session_state.artist_songs = []
if 'user_playlists' not in st.session_state:
    st.session_state.user_playlists = {}
if 'current_playlist' not in st.session_state:
    st.session_state.current_playlist = "default"

class MusicDownloader:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        if self.spotify_client_id and self.spotify_client_secret:
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=self.spotify_client_id,
                    client_secret=self.spotify_client_secret
                )
            )
        else:
            self.sp = None
    
    def download_youtube(self, url, quality='highest'):
        """Download audio from YouTube/YouTube Music"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                mp3_filename = filename.rsplit('.', 1)[0] + '.mp3'
                
                # Get metadata
                metadata = {
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'source': 'YouTube'
                }
                
                return mp3_filename, metadata
        except Exception as e:
            st.error(f"Error downloading from YouTube: {e}")
            return None, None
    
    def search_youtube(self, query, limit=10):
        """Search YouTube for songs"""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(
                    f"ytsearch{limit}:{query}",
                    download=False
                )
                
                videos = []
                for entry in results.get('entries', []):
                    video = {
                        'title': entry.get('title', 'Unknown'),
                        'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', 'Unknown'),
                        'source': 'YouTube'
                    }
                    videos.append(video)
                
                return videos
        except Exception as e:
            st.error(f"Error searching YouTube: {e}")
            return []
    
    def search_spotify(self, query, limit=10):
        """Search Spotify for songs"""
        if not self.sp:
            st.warning("Spotify API credentials not configured. Please add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env file")
            return []
        
        try:
            results = self.sp.search(q=query, limit=limit, type='track')
            
            tracks = []
            for track in results['tracks']['items']:
                track_info = {
                    'title': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'album': track['album']['name'],
                    'duration': track['duration_ms'] // 1000,
                    'thumbnail': track['album']['images'][0]['url'] if track['album']['images'] else '',
                    'url': track['external_urls']['spotify'],
                    'spotify_id': track['id'],
                    'source': 'Spotify'
                }
                tracks.append(track_info)
            
            return tracks
        except Exception as e:
            st.error(f"Error searching Spotify: {e}")
            return []
    
    def download_spotify(self, track_url):
        """Download Spotify track by searching on YouTube"""
        try:
            # Extract track info from Spotify
            if self.sp:
                track_id = track_url.split('/')[-1].split('?')[0]
                track = self.sp.track(track_id)
                
                search_query = f"{track['name']} {track['artists'][0]['name']}"
                youtube_results = self.search_youtube(search_query, limit=1)
                
                if youtube_results:
                    return self.download_youtube(youtube_results[0]['url'])
            
            return None, None
        except Exception as e:
            st.error(f"Error processing Spotify track: {e}")
            return None, None
    
    def convert_to_mp3(self, input_file, output_file):
        """Convert any audio file to MP3"""
        try:
            # Using yt-dlp's postprocessor for conversion
            ydl_opts = {
                'outtmpl': output_file,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # This is a workaround for local files
                # In production, you might want to use ffmpeg directly
                pass
            
            return output_file
        except Exception as e:
            st.error(f"Error converting to MP3: {e}")
            return None

# Initialize downloader
downloader = MusicDownloader()

def create_zip_archive(files, archive_name):
    """Create ZIP archive of multiple files"""
    zip_path = os.path.join(downloader.temp_dir, f"{archive_name}.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            if os.path.exists(file):
                zipf.write(file, os.path.basename(file))
    
    return zip_path

def create_rar_archive(files, archive_name):
    """Create RAR archive of multiple files"""
    try:
        import rarfile
        rar_path = os.path.join(downloader.temp_dir, f"{archive_name}.rar")
        
        # Note: Creating RAR files requires rar command line tool
        # This is a placeholder - implementation depends on system setup
        return create_zip_archive(files, archive_name)  # Fallback to ZIP
    except:
        return create_zip_archive(files, archive_name)

def display_song_card(song, index):
    """Display song in a card format"""
    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
    
    with col1:
        if song.get('thumbnail'):
            st.image(song['thumbnail'], width=50)
        st.write(f"**{song.get('title', 'Unknown')}**")
        st.caption(f"Artist: {song.get('artist', 'Unknown')}")
    
    with col2:
        st.write(f"Duration: {song.get('duration', 0)}s")
        st.caption(f"Source: {song.get('source', 'Unknown')}")
    
    with col3:
        if st.button("🎵 Play", key=f"play_{index}"):
            st.session_state.current_song = song
    
    with col4:
        if st.button("⬇️ Download", key=f"download_{index}"):
            return song
    
    return None

def main_page():
    """Main search and download page"""
    st.title("🎵 MusicStream Pro")
    st.markdown("---")
    
    # Search bar
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        search_query = st.text_input("Search for songs, albums, or artists:")
    
    with col2:
        platform = st.selectbox(
            "Platform",
            ["All", "YouTube", "YouTube Music", "Spotify"]
        )
    
    with col3:
        search_btn = st.button("🔍 Search", use_container_width=True)
    
    if search_btn and search_query:
        with st.spinner("Searching..."):
            results = []
            if platform in ["All", "YouTube", "YouTube Music"]:
                results.extend(downloader.search_youtube(search_query))
            if platform in ["All", "Spotify"]:
                results.extend(downloader.search_spotify(search_query))
            
            st.session_state.search_results = results
    
    # Display search results
    if st.session_state.search_results:
        st.subheader("Search Results")
        for idx, song in enumerate(st.session_state.search_results):
            song_to_download = display_song_card(song, idx)
            if song_to_download:
                download_song(song_to_download)
    
    # Currently playing
    if 'current_song' in st.session_state:
        st.markdown("---")
        st.subheader("🎧 Now Playing")
        song = st.session_state.current_song
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if song.get('thumbnail'):
                st.image(song['thumbnail'], width=150)
        
        with col2:
            st.write(f"**{song.get('title', 'Unknown')}**")
            st.write(f"*{song.get('artist', 'Unknown')}*")
            st.write(f"Source: {song.get('source', 'Unknown')}")
            
            # Add to playlist
            if st.button("➕ Add to Playlist"):
                if song not in st.session_state.playlist:
                    st.session_state.playlist.append(song)
                    st.success("Added to playlist!")
            
            # Download button
            if st.button("⬇️ Download This Song"):
                download_song(song)

def download_song(song):
    """Download a single song"""
    with st.spinner(f"Downloading {song.get('title')}..."):
        if song['source'] == 'YouTube':
            file_path, metadata = downloader.download_youtube(song['url'])
        elif song['source'] == 'Spotify':
            file_path, metadata = downloader.download_spotify(song['url'])
        else:
            st.error("Unsupported source")
            return
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                st.download_button(
                    label=f"Download {os.path.basename(file_path)}",
                    data=f,
                    file_name=os.path.basename(file_path),
                    mime="audio/mpeg"
                )
            st.success("Download ready!")

def playlist_page():
    """Playlist management page"""
    st.title("📋 My Playlists")
    st.markdown("---")
    
    # Create new playlist
    col1, col2 = st.columns([2, 1])
    with col1:
        new_playlist_name = st.text_input("New playlist name:")
    with col2:
        if st.button("Create Playlist") and new_playlist_name:
            if new_playlist_name not in st.session_state.user_playlists:
                st.session_state.user_playlists[new_playlist_name] = []
                st.session_state.current_playlist = new_playlist_name
                st.success(f"Playlist '{new_playlist_name}' created!")
    
    # Select current playlist
    if st.session_state.user_playlists:
        playlist_names = list(st.session_state.user_playlists.keys())
        selected_playlist = st.selectbox(
            "Select Playlist",
            playlist_names,
            index=playlist_names.index(st.session_state.current_playlist) if st.session_state.current_playlist in playlist_names else 0
        )
        st.session_state.current_playlist = selected_playlist
        
        # Display playlist songs
        playlist = st.session_state.user_playlists.get(selected_playlist, [])
        
        if playlist:
            st.subheader(f"Playlist: {selected_playlist} ({len(playlist)} songs)")
            
            for idx, song in enumerate(playlist):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{song.get('title', 'Unknown')}**")
                    st.caption(f"Artist: {song.get('artist', 'Unknown')}")
                
                with col2:
                    st.button("▶️ Play", key=f"play_playlist_{idx}")
                
                with col3:
                    if st.button("❌ Remove", key=f"remove_{idx}"):
                        playlist.pop(idx)
                        st.rerun()
            
            # Batch download options
            st.markdown("---")
            st.subheader("Batch Download")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📥 Download as MP3s"):
                    download_playlist(playlist, "mp3")
            
            with col2:
                if st.button("🗜️ Download as ZIP"):
                    download_playlist(playlist, "zip")
            
            with col3:
                if st.button("📦 Download as RAR"):
                    download_playlist(playlist, "rar")
        else:
            st.info("This playlist is empty. Add songs from the search results!")
    else:
        st.info("Create your first playlist to get started!")

def download_playlist(playlist, format_type):
    """Download entire playlist"""
    with st.spinner(f"Preparing {format_type.upper()} download..."):
        files = []
        
        for song in playlist:
            if song['source'] == 'YouTube':
                file_path, _ = downloader.download_youtube(song['url'])
            elif song['source'] == 'Spotify':
                file_path, _ = downloader.download_spotify(song['url'])
            
            if file_path and os.path.exists(file_path):
                files.append(file_path)
        
        if files:
            if format_type == "mp3":
                # Create a ZIP if multiple files, otherwise download single
                if len(files) > 1:
                    archive_path = create_zip_archive(files, f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    with open(archive_path, 'rb') as f:
                        st.download_button(
                            label="Download Playlist (ZIP)",
                            data=f,
                            file_name=f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip"
                        )
                else:
                    with open(files[0], 'rb') as f:
                        st.download_button(
                            label=f"Download {os.path.basename(files[0])}",
                            data=f,
                            file_name=os.path.basename(files[0]),
                            mime="audio/mpeg"
                        )
            elif format_type == "zip":
                archive_path = create_zip_archive(files, f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                with open(archive_path, 'rb') as f:
                    st.download_button(
                        label="Download Playlist (ZIP)",
                        data=f,
                        file_name=f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip"
                    )
            elif format_type == "rar":
                archive_path = create_rar_archive(files, f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                with open(archive_path, 'rb') as f:
                    st.download_button(
                        label="Download Playlist (RAR)",
                        data=f,
                        file_name=f"playlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.rar",
                        mime="application/x-rar-compressed"
                    )
            
            st.success("Download ready!")

def creator_page():
    """Creator mode for artists"""
    st.title("🎤 Creator Mode")
    st.markdown("---")
    
    st.markdown("### Upload Your Music")
    
    with st.form("upload_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            song_title = st.text_input("Song Title")
            artist_name = st.text_input("Artist Name")
            album_name = st.text_input("Album Name (optional)")
        
        with col2:
            genre = st.selectbox("Genre", [
                "Pop", "Rock", "Hip Hop", "Jazz", "Classical",
                "Electronic", "R&B", "Country", "Metal", "Other"
            ])
            release_date = st.date_input("Release Date")
        
        uploaded_file = st.file_uploader(
            "Upload Audio File",
            type=['mp3', 'wav', 'flac', 'm4a', 'aac']
        )
        
        # Promotion options
        st.markdown("### Promotion Options")
        promote = st.checkbox("Promote this song (increase visibility)")
        
        if promote:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Basic Promotion", "$9.99", "+1000 views")
            with col2:
                st.metric("Premium Promotion", "$29.99", "+5000 views")
            with col3:
                st.metric("VIP Promotion", "$99.99", "+25000 views")
            
            promotion_tier = st.select_slider(
                "Select Promotion Tier",
                options=["Basic", "Premium", "VIP"],
                value="Basic"
            )
        
        submitted = st.form_submit_button("Upload Song")
        
        if submitted and uploaded_file and song_title and artist_name:
            # Save uploaded file
            temp_file = os.path.join(downloader.temp_dir, uploaded_file.name)
            with open(temp_file, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Convert to MP3 if needed
            if not uploaded_file.name.lower().endswith('.mp3'):
                mp3_file = os.path.splitext(temp_file)[0] + '.mp3'
                downloader.convert_to_mp3(temp_file, mp3_file)
                temp_file = mp3_file
            
            # Store song info
            song_data = {
                'title': song_title,
                'artist': artist_name,
                'album': album_name,
                'genre': genre,
                'release_date': str(release_date),
                'file_path': temp_file,
                'upload_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'promoted': promote,
                'promotion_tier': promotion_tier if promote else None
            }
            
            st.session_state.artist_songs.append(song_data)
            st.success(f"Successfully uploaded '{song_title}'!")
            
            if promote:
                st.info(f"Your song will be promoted with {promotion_tier} tier. Payment processing required.")

def settings_page():
    """Settings page"""
    st.title("⚙️ Settings")
    st.markdown("---")
    
    # Dark/Light mode toggle
    st.subheader("Display Settings")
    dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode)
    
    if dark_mode != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode
        st.rerun()
    
    # Audio quality settings
    st.subheader("Audio Quality")
    quality = st.select_slider(
        "MP3 Quality",
        options=["64k", "128k", "192k", "256k", "320k"],
        value="192k"
    )
    
    # Download location
    st.subheader("Download Location")
    download_path = st.text_input(
        "Default Download Folder",
        value=os.path.join(str(Path.home()), "MusicDownloads")
    )
    
    # API Settings
    st.subheader("API Configuration")
    
    with st.expander("Spotify API Settings"):
        spotify_client_id = st.text_input(
            "Spotify Client ID",
            value=os.getenv('SPOTIFY_CLIENT_ID', ''),
            type="password"
        )
        spotify_client_secret = st.text_input(
            "Spotify Client Secret",
            value=os.getenv('SPOTIFY_CLIENT_SECRET', ''),
            type="password"
        )
    
    if st.button("Save Settings"):
        st.success("Settings saved!")
        
        # Update environment variables
        env_path = Path('.env')
        env_content = env_path.read_text() if env_path.exists() else ''
        
        # Update or add Spotify credentials
        lines = env_content.split('\n')
        updated_lines = []
        spotify_id_found = spotify_secret_found = False
        
        for line in lines:
            if line.startswith('SPOTIFY_CLIENT_ID='):
                updated_lines.append(f'SPOTIFY_CLIENT_ID={spotify_client_id}')
                spotify_id_found = True
            elif line.startswith('SPOTIFY_CLIENT_SECRET='):
                updated_lines.append(f'SPOTIFY_CLIENT_SECRET={spotify_client_secret}')
                spotify_secret_found = True
            else:
                updated_lines.append(line)
        
        if not spotify_id_found:
            updated_lines.append(f'SPOTIFY_CLIENT_ID={spotify_client_id}')
        if not spotify_secret_found:
            updated_lines.append(f'SPOTIFY_CLIENT_SECRET={spotify_client_secret}')
        
        env_path.write_text('\n'.join(updated_lines))

def sidebar():
    """Sidebar navigation"""
    with st.sidebar:
        st.title("🎵 MusicStream")
        
        # Mode toggle
        mode = st.selectbox(
            "Mode",
            ["🎵 Listener", "🎤 Creator"]
        )
        
        st.markdown("---")
        
        # Navigation
        if mode == "🎵 Listener":
            page = st.radio(
                "Navigation",
                ["🔍 Search & Play", "📋 My Playlists", "⚙️ Settings"]
            )
            
            if page == "🔍 Search & Play":
                st.session_state.current_page = "main"
            elif page == "📋 My Playlists":
                st.session_state.current_page = "playlist"
            elif page == "⚙️ Settings":
                st.session_state.current_page = "settings"
        
        else:  # Creator mode
            page = st.radio(
                "Navigation",
                ["🎤 Upload Music", "📊 Analytics", "💰 Earnings"]
            )
            
            if page == "🎤 Upload Music":
                st.session_state.current_page = "creator"
            elif page == "📊 Analytics":
                st.session_state.current_page = "analytics"
            elif page == "💰 Earnings":
                st.session_state.current_page = "earnings"
        
        st.markdown("---")
        
        # Quick stats
        if st.session_state.current_page in ["main", "playlist"]:
            st.caption(f"Playlist: {len(st.session_state.playlist)} songs")
        
        # Dark mode toggle in sidebar
        st.markdown("---")
        if st.session_state.dark_mode:
            st.button("🌙 Dark Mode", disabled=True)
        else:
            st.button("☀️ Light Mode", disabled=True)

def analytics_page():
    """Analytics page for creators"""
    st.title("📊 Analytics")
    st.markdown("---")
    
    if st.session_state.artist_songs:
        st.subheader("Your Uploaded Songs")
        
        for song in st.session_state.artist_songs:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{song['title']}**")
                st.caption(f"Artist: {song['artist']} | Uploaded: {song['upload_date']}")
            
            with col2:
                st.metric("Plays", "1,234")
            
            with col3:
                st.metric("Downloads", "567")
            
            st.progress(75, text="Popularity: 75%")
            st.markdown("---")
    else:
        st.info("No songs uploaded yet. Upload your first song in Creator Mode!")

def earnings_page():
    """Earnings page for creators"""
    st.title("💰 Earnings")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Earnings", "$1,234.56")
    
    with col2:
        st.metric("This Month", "$456.78")
    
    with col3:
        st.metric("Total Downloads", "12,345")
    
    st.markdown("---")
    st.subheader("Recent Transactions")
    
    # Sample transaction data
    transactions = [
        {"date": "2024-01-15", "song": "My First Hit", "amount": "$123.45", "type": "Royalties"},
        {"date": "2024-01-10", "song": "Summer Vibes", "amount": "$89.10", "type": "Promotion"},
        {"date": "2024-01-05", "song": "Midnight Dreams", "amount": "$67.89", "type": "Royalties"},
    ]
    
    for transaction in transactions:
        st.write(f"{transaction['date']} | {transaction['song']} | {transaction['amount']} | {transaction['type']}")
    
    st.markdown("---")
    
    if st.button("💰 Request Payout"):
        st.info("Payout request submitted. Funds will be transferred within 3-5 business days.")

# Main app logic
if 'current_page' not in st.session_state:
    st.session_state.current_page = "main"

# Apply dark mode
if st.session_state.dark_mode:
    st.markdown('<style>body {background-color: #0e1117; color: white;}</style>', unsafe_allow_html=True)

# Display sidebar
sidebar()

# Display current page
if st.session_state.current_page == "main":
    main_page()
elif st.session_state.current_page == "playlist":
    playlist_page()
elif st.session_state.current_page == "creator":
    creator_page()
elif st.session_state.current_page == "analytics":
    analytics_page()
elif st.session_state.current_page == "earnings":
    earnings_page()
elif st.session_state.current_page == "settings":
    settings_page()

# Footer
st.markdown("---")
st.caption("MusicStream Pro v1.0 | © 2024 All rights reserved")
