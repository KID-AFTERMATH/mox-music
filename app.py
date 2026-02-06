import streamlit as st
import os
from pathlib import Path
import tempfile
import zipfile
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
        border: 1px solid #e0e0e0;
        background-color: #f8f9fa;
    }
    .song-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .dark-mode {
        background-color: #0e1117;
        color: white;
    }
    .dark-mode .song-card {
        background-color: #2d2d2d;
        border: 1px solid #444;
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
        margin: 20px 0;
    }
    .playlist-item {
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        background-color: #f0f2f6;
    }
    .dark-mode .playlist-item {
        background-color: #262730;
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
    st.session_state.user_playlists = {"Favorites": []}
if 'current_playlist' not in st.session_state:
    st.session_state.current_playlist = "Favorites"

class MusicDownloader:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        # Initialize Spotify client if credentials are available
        if self.spotify_client_id and self.spotify_client_secret:
            try:
                self.sp = spotipy.Spotify(
                    auth_manager=SpotifyClientCredentials(
                        client_id=self.spotify_client_id,
                        client_secret=self.spotify_client_secret
                    )
                )
            except:
                self.sp = None
                st.warning("Spotify credentials are invalid. Spotify features will be limited.")
        else:
            self.sp = None
            st.info("Spotify API credentials not configured. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env file for full Spotify support")
    
    def download_youtube(self, url, quality='highest'):
        """Download audio from YouTube/YouTube Music"""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(self.temp_dir, exist_ok=True)
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
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
                    'source': 'YouTube',
                    'url': url
                }
                
                return mp3_filename, metadata
        except Exception as e:
            st.error(f"Error downloading from YouTube: {str(e)}")
            return None, None
    
    def search_youtube(self, query, limit=10):
        """Search YouTube for songs"""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
                'default_search': 'ytsearch',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                
                videos = []
                for entry in results.get('entries', []):
                    if entry:  # Check if entry is not None
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
            st.error(f"Error searching YouTube: {str(e)}")
            return []
    
    def search_spotify(self, query, limit=10):
        """Search Spotify for songs"""
        if not self.sp:
            return []  # Return empty list if Spotify client not available
        
        try:
            results = self.sp.search(q=query, limit=limit, type='track')
            
            tracks = []
            for track in results['tracks']['items']:
                thumbnail = track['album']['images'][0]['url'] if track['album']['images'] else ''
                track_info = {
                    'title': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'album': track['album']['name'],
                    'duration': track['duration_ms'] // 1000,
                    'thumbnail': thumbnail,
                    'url': track['external_urls']['spotify'],
                    'spotify_id': track['id'],
                    'source': 'Spotify'
                }
                tracks.append(track_info)
            
            return tracks
        except Exception as e:
            st.error(f"Error searching Spotify: {str(e)}")
            return []
    
    def download_spotify(self, track_url):
        """Download Spotify track by searching on YouTube"""
        try:
            if self.sp:
                # Extract track info from Spotify
                track_id = track_url.split('/')[-1].split('?')[0]
                track = self.sp.track(track_id)
                
                # Search for the track on YouTube
                search_query = f"{track['name']} {track['artists'][0]['name']} official audio"
                youtube_results = self.search_youtube(search_query, limit=1)
                
                if youtube_results:
                    return self.download_youtube(youtube_results[0]['url'])
            
            return None, None
        except Exception as e:
            st.error(f"Error processing Spotify track: {str(e)}")
            return None, None

# Initialize downloader
downloader = MusicDownloader()

def create_zip_archive(files, archive_name):
    """Create ZIP archive of multiple files"""
    zip_path = os.path.join(downloader.temp_dir, f"{archive_name}.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            if os.path.exists(file):
                # Add file to zip with just the filename (not full path)
                zipf.write(file, os.path.basename(file))
    
    return zip_path

def display_song_card(song, index):
    """Display song in a card format"""
    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
    
    with col1:
        if song.get('thumbnail'):
            try:
                st.image(song['thumbnail'], width=50)
            except:
                pass
        st.write(f"**{song.get('title', 'Unknown')}**")
        st.caption(f"Artist: {song.get('artist', 'Unknown')}")
    
    with col2:
        if song.get('duration'):
            minutes = song['duration'] // 60
            seconds = song['duration'] % 60
            st.write(f"Duration: {minutes}:{seconds:02d}")
        st.caption(f"Source: {song.get('source', 'Unknown')}")
    
    with col3:
        if st.button("▶️ Play", key=f"play_{index}", use_container_width=True):
            st.session_state.current_song = song
    
    with col4:
        if st.button("⬇️ Download", key=f"download_{index}", use_container_width=True):
            return song
    
    return None

def main_page():
    """Main search and download page"""
    st.title("🎵 MusicStream Pro")
    st.markdown("---")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Search Results", len(st.session_state.search_results))
    with col2:
        st.metric("Playlist Songs", len(st.session_state.playlist))
    with col3:
        st.metric("My Playlists", len(st.session_state.user_playlists))
    
    st.markdown("---")
    
    # Search section
    st.subheader("🔍 Search Music")
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        search_query = st.text_input("Search for songs, albums, or artists:", placeholder="Enter song name, artist, or album...")
    
    with col2:
        platform = st.selectbox(
            "Platform",
            ["All", "YouTube", "Spotify"]
        )
    
    with col3:
        search_btn = st.button("🔍 Search", use_container_width=True)
    
    if search_btn and search_query:
        with st.spinner(f"Searching {platform} for '{search_query}'..."):
            results = []
            if platform in ["All", "YouTube"]:
                youtube_results = downloader.search_youtube(search_query)
                results.extend(youtube_results)
            if platform in ["All", "Spotify"] and downloader.sp:
                spotify_results = downloader.search_spotify(search_query)
                results.extend(spotify_results)
            
            if results:
                st.session_state.search_results = results
                st.success(f"Found {len(results)} results!")
            else:
                st.warning("No results found. Try a different search term.")
    
    # Display search results
    if st.session_state.search_results:
        st.subheader(f"📋 Search Results ({len(st.session_state.search_results)} songs)")
        
        for idx, song in enumerate(st.session_state.search_results):
            with st.container():
                song_to_download = display_song_card(song, idx)
                if song_to_download:
                    with st.spinner(f"Downloading {song.get('title')}..."):
                        download_song(song)
                st.markdown("---")
    
    # Currently playing section
    if 'current_song' in st.session_state:
        st.markdown("---")
        st.subheader("🎧 Now Playing")
        song = st.session_state.current_song
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if song.get('thumbnail'):
                try:
                    st.image(song['thumbnail'], width=200)
                except:
                    st.image("https://via.placeholder.com/200x200?text=No+Image", width=200)
        
        with col2:
            st.write(f"### {song.get('title', 'Unknown')}")
            st.write(f"#### *{song.get('artist', 'Unknown')}*")
            st.write(f"**Source:** {song.get('source', 'Unknown')}")
            
            if song.get('duration'):
                minutes = song['duration'] // 60
                seconds = song['duration'] % 60
                st.write(f"**Duration:** {minutes}:{seconds:02d}")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                # Add to current playlist
                current_playlist_name = st.session_state.current_playlist
                if st.button("➕ Add to Playlist", use_container_width=True):
                    if song not in st.session_state.user_playlists.get(current_playlist_name, []):
                        st.session_state.user_playlists[current_playlist_name].append(song)
                        st.success(f"Added to '{current_playlist_name}'!")
                    else:
                        st.warning("Song already in playlist!")
            
            with col_btn2:
                # Download button
                if st.button("⬇️ Download", use_container_width=True):
                    download_song(song)
            
            with col_btn3:
                if st.button("Clear Player", use_container_width=True):
                    del st.session_state.current_song
                    st.rerun()

def download_song(song):
    """Download a single song"""
    try:
        if song['source'] == 'YouTube':
            file_path, metadata = downloader.download_youtube(song['url'])
        elif song['source'] == 'Spotify':
            file_path, metadata = downloader.download_spotify(song['url'])
        else:
            st.error("Unsupported source")
            return
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                file_data = f.read()
                st.download_button(
                    label=f"📥 Download {os.path.basename(file_path)}",
                    data=file_data,
                    file_name=os.path.basename(file_path),
                    mime="audio/mpeg",
                    key=f"download_{song.get('title', 'song')}"
                )
            st.success("✅ Download ready!")
        else:
            st.error("Failed to download song")
    except Exception as e:
        st.error(f"Download error: {str(e)}")

def playlist_page():
    """Playlist management page"""
    st.title("📋 My Playlists")
    st.markdown("---")
    
    # Create new playlist
    with st.expander("➕ Create New Playlist"):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_playlist_name = st.text_input("Playlist name:")
        with col2:
            if st.button("Create", use_container_width=True) and new_playlist_name:
                if new_playlist_name not in st.session_state.user_playlists:
                    st.session_state.user_playlists[new_playlist_name] = []
                    st.session_state.current_playlist = new_playlist_name
                    st.success(f"Playlist '{new_playlist_name}' created!")
                else:
                    st.warning("Playlist already exists!")
    
    # Select current playlist
    if st.session_state.user_playlists:
        playlist_names = list(st.session_state.user_playlists.keys())
        selected_playlist = st.selectbox(
            "🎵 Select Playlist",
            playlist_names,
            index=playlist_names.index(st.session_state.current_playlist) if st.session_state.current_playlist in playlist_names else 0
        )
        st.session_state.current_playlist = selected_playlist
        
        # Display playlist info
        playlist = st.session_state.user_playlists.get(selected_playlist, [])
        
        if playlist:
            st.subheader(f"🎶 {selected_playlist} ({len(playlist)} songs)")
            
            # Playlist actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("▶️ Play All", use_container_width=True):
                    st.session_state.current_song = playlist[0] if playlist else None
            
            with col2:
                if st.button("🗑️ Clear Playlist", use_container_width=True):
                    st.session_state.user_playlists[selected_playlist] = []
                    st.rerun()
            
            with col3:
                if st.button("💾 Export Playlist", use_container_width=True):
                    export_playlist(playlist, selected_playlist)
            
            st.markdown("---")
            
            # Display playlist songs
            for idx, song in enumerate(playlist):
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    
                    with col1:
                        st.write(f"**{song.get('title', 'Unknown')}**")
                        st.caption(f"Artist: {song.get('artist', 'Unknown')}")
                    
                    with col2:
                        st.caption(f"Source: {song.get('source', 'Unknown')}")
                    
                    with col3:
                        if st.button("▶️ Play", key=f"play_p_{idx}", use_container_width=True):
                            st.session_state.current_song = song
                    
                    with col4:
                        if st.button("❌ Remove", key=f"remove_{idx}", use_container_width=True):
                            playlist.pop(idx)
                            st.rerun()
                    
                    st.markdown("---")
            
            # Batch download options
            st.subheader("📦 Batch Download")
            st.info(f"You can download all {len(playlist)} songs from this playlist at once.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗜️ Download as ZIP", use_container_width=True):
                    download_playlist(playlist, "zip")
            with col2:
                if st.button("💿 Download as MP3s", use_container_width=True):
                    download_playlist(playlist, "individual")
        else:
            st.info("This playlist is empty. Add songs from the search results!")
    else:
        st.info("No playlists yet. Create your first playlist!")

def export_playlist(playlist, playlist_name):
    """Export playlist as JSON file"""
    playlist_data = {
        'name': playlist_name,
        'created': datetime.now().isoformat(),
        'songs': playlist
    }
    
    # Convert to JSON string
    json_data = json.dumps(playlist_data, indent=2)
    
    st.download_button(
        label="📥 Download Playlist JSON",
        data=json_data,
        file_name=f"{playlist_name}_playlist.json",
        mime="application/json"
    )

def download_playlist(playlist, format_type):
    """Download entire playlist"""
    if not playlist:
        st.warning("Playlist is empty!")
        return
    
    with st.spinner(f"Preparing {len(playlist)} songs for download..."):
        files = []
        successful_downloads = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, song in enumerate(playlist):
            status_text.text(f"Downloading {idx+1}/{len(playlist)}: {song.get('title', 'Song')}")
            
            try:
                if song['source'] == 'YouTube':
                    file_path, _ = downloader.download_youtube(song['url'])
                elif song['source'] == 'Spotify':
                    file_path, _ = downloader.download_spotify(song['url'])
                else:
                    continue
                
                if file_path and os.path.exists(file_path):
                    files.append(file_path)
                    successful_downloads += 1
            except Exception as e:
                st.warning(f"Failed to download {song.get('title')}: {str(e)}")
            
            progress_bar.progress((idx + 1) / len(playlist))
        
        status_text.text(f"Successfully downloaded {successful_downloads}/{len(playlist)} songs")
        
        if successful_downloads > 0:
            if format_type == "individual":
                # Create a ZIP for multiple files
                if successful_downloads > 1:
                    archive_path = create_zip_archive(files, f"{st.session_state.current_playlist}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    with open(archive_path, 'rb') as f:
                        st.download_button(
                            label=f"📥 Download {successful_downloads} songs as ZIP",
                            data=f.read(),
                            file_name=f"{st.session_state.current_playlist}.zip",
                            mime="application/zip"
                        )
                else:
                    # Single file download
                    with open(files[0], 'rb') as f:
                        st.download_button(
                            label=f"📥 Download {os.path.basename(files[0])}",
                            data=f.read(),
                            file_name=os.path.basename(files[0]),
                            mime="audio/mpeg"
                        )
            elif format_type == "zip":
                archive_path = create_zip_archive(files, f"{st.session_state.current_playlist}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                with open(archive_path, 'rb') as f:
                    st.download_button(
                        label=f"📥 Download {successful_downloads} songs as ZIP",
                        data=f.read(),
                        file_name=f"{st.session_state.current_playlist}.zip",
                        mime="application/zip"
                    )
            
            st.success(f"✅ {successful_downloads} songs ready for download!")
        else:
            st.error("No songs were successfully downloaded.")

def creator_page():
    """Creator mode for artists"""
    st.title("🎤 Creator Mode")
    st.markdown("---")
    
    st.info("""
    Welcome to Creator Mode! Here you can:
    - Upload your own music
    - Add metadata to your songs
    - Promote your music (optional)
    - Track your uploads
    """)
    
    # Upload section
    st.subheader("📤 Upload Your Music")
    
    with st.form("upload_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            song_title = st.text_input("Song Title *", placeholder="Enter song title")
            artist_name = st.text_input("Artist Name *", placeholder="Your artist name")
            album_name = st.text_input("Album Name", placeholder="Album name (optional)")
        
        with col2:
            genre = st.selectbox("Genre", [
                "Select genre", "Pop", "Rock", "Hip Hop", "Jazz", "Classical",
                "Electronic", "R&B", "Country", "Metal", "Other"
            ])
            release_date = st.date_input("Release Date")
        
        uploaded_file = st.file_uploader(
            "Upload Audio File *",
            type=['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg'],
            help="Supported formats: MP3, WAV, FLAC, M4A, AAC, OGG"
        )
        
        # File info
        if uploaded_file:
            st.info(f"File: {uploaded_file.name} | Size: {uploaded_file.size / 1024 / 1024:.2f} MB")
        
        # Promotion options
        st.markdown("### 💫 Promotion Options (Optional)")
        promote = st.checkbox("Promote this song to increase visibility")
        
        if promote:
            st.warning("""
            **Important:** Promotion features require payment integration setup.
            For demo purposes, this is simulated.
            """)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Basic Promotion", "$9.99", "+1000 streams")
                basic_selected = st.button("Select Basic", key="basic_btn")
            with col2:
                st.metric("Premium Promotion", "$29.99", "+5000 streams")
                premium_selected = st.button("Select Premium", key="premium_btn")
            with col3:
                st.metric("VIP Promotion", "$99.99", "+25000 streams")
                vip_selected = st.button("Select VIP", key="vip_btn")
            
            promotion_tier = "None"
            if basic_selected:
                promotion_tier = "Basic"
                st.session_state.promotion_tier = "Basic"
            elif premium_selected:
                promotion_tier = "Premium"
                st.session_state.promotion_tier = "Premium"
            elif vip_selected:
                promotion_tier = "VIP"
                st.session_state.promotion_tier = "VIP"
            
            if promotion_tier != "None":
                st.success(f"Selected: {promotion_tier} Promotion")
        
        submitted = st.form_submit_button("Upload Song")
        
        if submitted:
            if not (song_title and artist_name and uploaded_file):
                st.error("Please fill all required fields (*)")
            else:
                # Save uploaded file
                temp_file = os.path.join(downloader.temp_dir, uploaded_file.name)
                with open(temp_file, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
                
                # Store song info
                song_data = {
                    'title': song_title,
                    'artist': artist_name,
                    'album': album_name if album_name else "Single",
                    'genre': genre if genre != "Select genre" else "Other",
                    'release_date': str(release_date),
                    'file_name': uploaded_file.name,
                    'file_size': uploaded_file.size,
                    'upload_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'promoted': promote,
                    'promotion_tier': st.session_state.get('promotion_tier', 'None') if promote else 'None'
                }
                
                st.session_state.artist_songs.append(song_data)
                
                # Show success message
                st.success(f"✅ Successfully uploaded '{song_title}'!")
                
                if promote and song_data['promotion_tier'] != 'None':
                    st.info(f"🎯 Your song will be promoted with {song_data['promotion_tier']} tier.")
    
    # Display uploaded songs
    if st.session_state.artist_songs:
        st.markdown("---")
        st.subheader("📋 Your Uploaded Songs")
        
        for idx, song in enumerate(st.session_state.artist_songs):
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{song['title']}**")
                    st.caption(f"Artist: {song['artist']} | Album: {song['album']}")
                    st.caption(f"Genre: {song['genre']} | Uploaded: {song['upload_date']}")
                
                with col2:
                    if song['promoted']:
                        st.success(f"Promoted: {song['promotion_tier']}")
                    else:
                        st.info("Not promoted")
                    
                    file_size_mb = song['file_size'] / 1024 / 1024
                    st.caption(f"File: {song['file_name']} ({file_size_mb:.2f} MB)")
                
                with col3:
                    if st.button("Manage", key=f"manage_{idx}"):
                        st.session_state.manage_song_idx = idx
                
                st.markdown("---")

def analytics_page():
    """Analytics page for creators"""
    st.title("📊 Analytics Dashboard")
    st.markdown("---")
    
    if st.session_state.artist_songs:
        total_songs = len(st.session_state.artist_songs)
        promoted_songs = sum(1 for song in st.session_state.artist_songs if song['promoted'])
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Songs", total_songs)
        
        with col2:
            st.metric("Promoted Songs", promoted_songs)
        
        with col3:
            # Simulated metrics
            total_streams = total_songs * 1234
            st.metric("Total Streams", f"{total_streams:,}")
        
        with col4:
            # Simulated earnings
            estimated_earnings = promoted_songs * 50 + total_songs * 10
            st.metric("Estimated Earnings", f"${estimated_earnings}")
        
        st.markdown("---")
        st.subheader("📈 Song Performance")
        
        # Display song analytics
        for idx, song in enumerate(st.session_state.artist_songs):
            with st.expander(f"{song['title']} by {song['artist']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Simulated analytics
                    streams = 1000 + idx * 500
                    downloads = 100 + idx * 50
                    likes = 50 + idx * 25
                    
                    st.write(f"**Streams:** {streams:,}")
                    st.write(f"**Downloads:** {downloads:,}")
                    st.write(f"**Likes:** {likes:,}")
                    
                    # Popularity gauge
                    popularity = min(100, 30 + idx * 15)
                    st.progress(popularity / 100, text=f"Popularity: {popularity}%")
                
                with col2:
                    # Engagement metrics
                    engagement_rate = f"{(downloads/streams*100):.1f}%" if streams > 0 else "0%"
                    st.metric("Engagement Rate", engagement_rate)
                    
                    if song['promoted']:
                        st.success(f"✅ {song['promotion_tier']} Promotion Active")
                        roi = f"{(streams * 0.003):.2f}"  # Simulated ROI
                        st.metric("Est. ROI", f"${roi}")
    else:
        st.info("No songs uploaded yet. Upload your first song in Creator Mode to see analytics!")
        
        # Show sample analytics for demo
        st.markdown("---")
        st.subheader("📊 Sample Analytics (Demo)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Songs", "0", "Upload songs to start tracking")
        with col2:
            st.metric("Total Streams", "0", "Streams will appear here")
        with col3:
            st.metric("Estimated Earnings", "$0.00", "Earnings from streams")

def earnings_page():
    """Earnings page for creators"""
    st.title("💰 Earnings & Payouts")
    st.markdown("---")
    
    # Summary cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Earnings", "$1,234.56", "+$123.45 this month")
    
    with col2:
        st.metric("Available Balance", "$456.78", "Ready for payout")
    
    with col3:
        st.metric("Next Payout", "15 days", "Monthly schedule")
    
    st.markdown("---")
    
    # Payout history (simulated)
    st.subheader("📋 Payout History")
    
    payout_history = [
        {"date": "2024-01-15", "amount": "$123.45", "status": "Paid", "method": "Bank Transfer"},
        {"date": "2023-12-15", "amount": "$98.76", "status": "Paid", "method": "PayPal"},
        {"date": "2023-11-15", "amount": "$87.65", "status": "Paid", "method": "Bank Transfer"},
    ]
    
    for payout in payout_history:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
        with col1:
            st.write(payout["date"])
        with col2:
            st.write(f"**{payout['amount']}**")
        with col3:
            if payout["status"] == "Paid":
                st.success("✅ Paid")
            else:
                st.warning("⏳ Pending")
        with col4:
            st.write(payout["method"])
        st.markdown("---")
    
    # Request payout section
    st.subheader("💸 Request Payout")
    
    with st.form("payout_form"):
        payout_amount = st.number_input("Payout Amount ($)", min_value=10.0, max_value=10000.0, value=100.0, step=10.0)
        payout_method = st.selectbox("Payout Method", ["Bank Transfer", "PayPal", "Stripe", "Cryptocurrency"])
        account_details = st.text_area("Account Details", placeholder="Enter your account email or details...")
        
        if st.form_submit_button("Request Payout"):
            if payout_amount >= 10.0 and account_details:
                st.success(f"✅ Payout request submitted for ${payout_amount:.2f} via {payout_method}!")
                st.info("💰 Payouts are processed within 3-5 business days.")
            else:
                st.error("Please enter valid payout amount and account details")

def settings_page():
    """Settings page"""
    st.title("⚙️ Settings")
    st.markdown("---")
    
    # Theme settings
    st.subheader("🎨 Theme Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        # Dark mode toggle
        dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode)
        
        if dark_mode != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_mode
            st.rerun()
    
    with col2:
        # Color theme
        theme_color = st.selectbox(
            "Accent Color",
            ["Blue", "Green", "Purple", "Red", "Orange"],
            index=0
        )
    
    # Audio settings
    st.subheader("🔊 Audio Settings")
    
    audio_quality = st.select_slider(
        "MP3 Quality",
        options=["64k", "128k", "192k", "256k", "320k"],
        value="192k"
    )
    
    # Download settings
    st.subheader("📥 Download Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        auto_download = st.toggle("Auto-start downloads", value=True)
        download_location = st.text_input(
            "Download Folder",
            value=os.path.join(str(Path.home()), "MusicDownloads")
        )
    
    with col2:
        create_subfolders = st.toggle("Create artist/album folders", value=True)
        keep_originals = st.toggle("Keep original files", value=False)
    
    # API Settings
    st.subheader("🔑 API Configuration")
    
    with st.expander("Spotify API Settings"):
        st.info("Get API keys from: https://developer.spotify.com/dashboard")
        
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
        
        if st.button("Test Spotify Connection"):
            if spotify_client_id and spotify_client_secret:
                try:
                    test_sp = spotipy.Spotify(
                        auth_manager=SpotifyClientCredentials(
                            client_id=spotify_client_id,
                            client_secret=spotify_client_secret
                        )
                    )
                    # Try a simple search
                    test_sp.search(q='test', limit=1)
                    st.success("✅ Spotify API connection successful!")
                except Exception as e:
                    st.error(f"❌ Connection failed: {str(e)}")
            else:
                st.warning("Please enter both Client ID and Secret")
    
    with st.expander("YouTube Settings"):
        youtube_api_key = st.text_input(
            "YouTube API Key (Optional)",
            value=os.getenv('YOUTUBE_API_KEY', ''),
            type="password"
        )
        st.caption("YouTube API key is optional but improves search results")
    
    # Save settings
    st.markdown("---")
    if st.button("💾 Save All Settings", type="primary", use_container_width=True):
        # Save to .env file
        env_lines = []
        env_file = Path('.env')
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                env_lines = f.readlines()
        
        # Update or add Spotify credentials
        updated_env = []
        spotify_id_found = spotify_secret_found = youtube_key_found = False
        
        for line in env_lines:
            if line.startswith('SPOTIFY_CLIENT_ID='):
                updated_env.append(f'SPOTIFY_CLIENT_ID={spotify_client_id}\n')
                spotify_id_found = True
            elif line.startswith('SPOTIFY_CLIENT_SECRET='):
                updated_env.append(f'SPOTIFY_CLIENT_SECRET={spotify_client_secret}\n')
                spotify_secret_found = True
            elif line.startswith('YOUTUBE_API_KEY='):
                updated_env.append(f'YOUTUBE_API_KEY={youtube_api_key}\n')
                youtube_key_found = True
            else:
                updated_env.append(line)
        
        if not spotify_id_found:
            updated_env.append(f'SPOTIFY_CLIENT_ID={spotify_client_id}\n')
        if not spotify_secret_found:
            updated_env.append(f'SPOTIFY_CLIENT_SECRET={spotify_client_secret}\n')
        if not youtube_key_found and youtube_api_key:
            updated_env.append(f'YOUTUBE_API_KEY={youtube_api_key}\n')
        
        with open(env_file, 'w') as f:
            f.writelines(updated_env)
        
        # Update session state
        st.session_state.audio_quality = audio_quality
        st.session_state.auto_download = auto_download
        
        st.success("✅ Settings saved successfully!")
        st.info("🔁 Restart the app for some changes to take effect")

def sidebar():
    """Sidebar navigation"""
    with st.sidebar:
        st.title("🎵 MusicStream")
        st.markdown("---")
        
        # Mode selection
        mode = st.radio(
            "Select Mode",
            ["🎵 Listener Mode", "🎤 Creator Mode"],
            index=0 if st.session_state.get('current_page', 'main') != 'creator' else 1
        )
        
        st.markdown("---")
        
        # Navigation based on mode
        if mode == "🎵 Listener Mode":
            page_options = {
                "🔍 Search & Play": "main",
                "📋 My Playlists": "playlist",
                "⚙️ Settings": "settings"
            }
            
            selected_page = st.radio(
                "Navigation",
                list(page_options.keys()),
                index=0 if st.session_state.get('current_page', 'main') == 'main' else 
                     1 if st.session_state.get('current_page', 'main') == 'playlist' else 2
            )
            
            st.session_state.current_page = page_options[selected_page]
        
        else:  # Creator Mode
            page_options = {
                "🎤 Upload Music": "creator",
                "📊 Analytics": "analytics",
                "💰 Earnings": "earnings"
            }
            
            selected_page = st.radio(
                "Navigation",
                list(page_options.keys()),
                index=0 if st.session_state.get('current_page', 'main') == 'creator' else 
                     1 if st.session_state.get('current_page', 'main') == 'analytics' else 2
            )
            
            st.session_state.current_page = page_options[selected_page]
        
        st.markdown("---")
        
        # Quick stats
        if st.session_state.current_page in ["main", "playlist"]:
            current_playlist = st.session_state.user_playlists.get(st.session_state.current_playlist, [])
            st.caption(f"🎶 Current Playlist: {len(current_playlist)} songs")
            st.caption(f"📥 Total Songs: {len(st.session_state.playlist)}")
        
        elif st.session_state.current_page == "creator":
            st.caption(f"📤 Uploaded Songs: {len(st.session_state.artist_songs)}")
        
        st.markdown("---")
        
        # App info
        st.caption("MusicStream Pro v1.0")
        st.caption("Stream & Download Music")

# Main app logic
if 'current_page' not in st.session_state:
    st.session_state.current_page = "main"

# Apply dark mode
if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0e1117;
            color: white;
        }
        .stTextInput > div > div > input {
            background-color: #262730;
            color: white;
        }
        .stSelectbox > div > div > select {
            background-color: #262730;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

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
footer_col1, footer_col2, footer_col3 = st.columns([2, 1, 1])
with footer_col1:
    st.caption("© 2024 MusicStream Pro. For educational purposes only.")
with footer_col2:
    if st.session_state.dark_mode:
        st.caption("🌙 Dark Mode")
    else:
        st.caption("☀️ Light Mode")
with footer_col3:
    st.caption(f"v1.0 | {datetime.now().strftime('%Y-%m-%d')}")
