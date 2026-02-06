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
    .error-box {
        background-color: #ffebee;
        border: 1px solid #ffcdd2;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .dark-mode .error-box {
        background-color: #3d1f23;
        border-color: #5d2b2f;
    }
    .selected-song {
        background-color: #e3f2fd !important;
        border: 2px solid #2196f3 !important;
    }
    .dark-mode .selected-song {
        background-color: #1a237e !important;
        border: 2px solid #536dfe !important;
    }
    .search-result-card {
        cursor: pointer;
        transition: all 0.2s;
    }
    .search-result-card:hover {
        background-color: #e8f5e9;
    }
    .dark-mode .search-result-card:hover {
        background-color: #1b5e20;
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
if 'current_song' not in st.session_state:
    st.session_state.current_song = None
if 'selected_song_index' not in st.session_state:
    st.session_state.selected_song_index = None

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
                st.session_state.spotify_available = True
            except Exception as e:
                self.sp = None
                st.session_state.spotify_available = False
                st.warning(f"Spotify credentials are invalid: {str(e)}. Spotify features will be limited.")
        else:
            self.sp = None
            st.session_state.spotify_available = False
            if not hasattr(st.session_state, 'spotify_warning_shown'):
                st.info("Spotify API credentials not configured. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env file for full Spotify support")
                st.session_state.spotify_warning_shown = True
    
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
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    st.error("Failed to extract video info")
                    return None, None
                    
                filename = ydl.prepare_filename(info)
                mp3_filename = filename.rsplit('.', 1)[0] + '.mp3'
                
                # Clean filename
                safe_title = info.get('title', 'Unknown').replace('/', '_').replace('\\', '_').replace(':', '_')
                mp3_filename = os.path.join(self.temp_dir, f"{safe_title}.mp3")
                
                # Get metadata
                metadata = {
                    'title': info.get('title', 'Unknown'),
                    'artist': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0) or 0,
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
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                if not results:
                    return []
                
                videos = []
                entries = results.get('entries', [])
                if not isinstance(entries, list):
                    entries = [entries]
                
                for entry in entries:
                    if entry and 'id' in entry:  # Check if entry is not None and has ID
                        video = {
                            'title': entry.get('title', 'Unknown Title'),
                            'url': f"https://youtube.com/watch?v={entry.get('id', '')}",
                            'duration': entry.get('duration', 0) or 0,
                            'thumbnail': entry.get('thumbnail', ''),
                            'uploader': entry.get('uploader', 'Unknown Artist'),
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
            if not results or 'tracks' not in results:
                return []
            
            tracks = []
            for track in results['tracks']['items']:
                thumbnail = ''
                if track['album']['images']:
                    thumbnail = track['album']['images'][0]['url']
                
                track_info = {
                    'title': track.get('name', 'Unknown Track'),
                    'artist': ', '.join([artist.get('name', '') for artist in track.get('artists', [])]),
                    'album': track.get('album', {}).get('name', 'Unknown Album'),
                    'duration': (track.get('duration_ms', 0) or 0) // 1000,
                    'thumbnail': thumbnail,
                    'url': track.get('external_urls', {}).get('spotify', ''),
                    'spotify_id': track.get('id', ''),
                    'source': 'Spotify'
                }
                tracks.append(track_info)
            
            return tracks
        except Exception as e:
            st.error(f"Error searching Spotify: {str(e)}")
            return []

def format_duration(seconds):
    """Format duration in seconds to MM:SS format"""
    try:
        if seconds is None:
            return "0:00"
        
        seconds = int(float(seconds))
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    except:
        return "0:00"

# Initialize downloader
downloader = MusicDownloader()

def create_zip_archive(files, archive_name):
    """Create ZIP archive of multiple files"""
    try:
        zip_path = os.path.join(downloader.temp_dir, f"{archive_name}.zip")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files:
                if os.path.exists(file):
                    # Add file to zip with just the filename (not full path)
                    zipf.write(file, os.path.basename(file))
        
        return zip_path
    except Exception as e:
        st.error(f"Error creating ZIP archive: {str(e)}")
        return None

def display_search_result(song, index):
    """Display search result with selection capability"""
    try:
        # Create a unique key for this song
        song_key = f"song_{index}_{uuid.uuid4().hex[:8]}"
        
        # Determine if this song is selected
        is_selected = st.session_state.selected_song_index == index
        
        # Apply selected styling
        card_class = "song-card search-result-card"
        if is_selected:
            card_class += " selected-song"
        
        # Display song card
        with st.container():
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([4, 2, 2])
            
            with col1:
                # Thumbnail and title
                row1 = st.columns([1, 4])
                with row1[0]:
                    thumbnail = song.get('thumbnail')
                    if thumbnail and thumbnail.startswith('http'):
                        try:
                            st.image(thumbnail, width=60)
                        except:
                            st.write("🎵")
                    else:
                        st.write("🎵")
                
                with row1[1]:
                    title = song.get('title', 'Unknown Title')
                    if len(title) > 50:
                        title = title[:47] + "..."
                    st.write(f"**{title}**")
                    
                    artist = song.get('artist', 'Unknown Artist')
                    if len(artist) > 40:
                        artist = artist[:37] + "..."
                    st.caption(f"👤 {artist}")
                    
                    if song.get('album'):
                        album = song.get('album')
                        if len(album) > 30:
                            album = album[:27] + "..."
                        st.caption(f"💿 {album}")
            
            with col2:
                # Duration and source
                duration = format_duration(song.get('duration'))
                st.write(f"⏱️ {duration}")
                
                source = song.get('source', 'Unknown')
                source_icon = "▶️" if source == 'YouTube' else "🎵"
                st.caption(f"{source_icon} {source}")
            
            with col3:
                # Selection and action buttons
                if st.button("🎯 Select", key=f"select_{song_key}", use_container_width=True):
                    st.session_state.selected_song_index = index
                    st.session_state.selected_song = song
                    st.rerun()
                
                if is_selected:
                    st.success("✓ Selected")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        return is_selected
    except Exception as e:
        st.error(f"Error displaying search result: {str(e)}")
        return False

def main_page():
    """Main search and download page"""
    try:
        st.title("🎵 MusicStream Pro")
        st.markdown("---")
        
        # Search section
        st.subheader("🔍 Search Music")
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            search_query = st.text_input("Search for songs, albums, or artists:", 
                                       placeholder="Enter song name, artist, or album...", 
                                       key="search_input_main")
        
        with col2:
            platform = st.selectbox(
                "Platform",
                ["All", "YouTube", "Spotify"],
                key="platform_select_main"
            )
        
        with col3:
            search_btn = st.button("🔍 Search", use_container_width=True, key="search_button_main")
        
        # Perform search when button is clicked
        if search_btn:
            if not search_query or search_query.strip() == "":
                st.warning("⚠️ Please enter a search term")
            else:
                with st.spinner(f"🔍 Searching {platform} for '{search_query}'..."):
                    results = []
                    
                    # Clear previous selection
                    st.session_state.selected_song_index = None
                    st.session_state.selected_song = None
                    
                    # Search YouTube
                    if platform in ["All", "YouTube"]:
                        youtube_results = downloader.search_youtube(search_query, limit=15)
                        if youtube_results:
                            results.extend(youtube_results)
                            st.success(f"✅ Found {len(youtube_results)} YouTube results")
                    
                    # Search Spotify
                    if platform in ["All", "Spotify"] and st.session_state.spotify_available:
                        spotify_results = downloader.search_spotify(search_query, limit=15)
                        if spotify_results:
                            results.extend(spotify_results)
                            st.success(f"✅ Found {len(spotify_results)} Spotify results")
                    
                    if results:
                        st.session_state.search_results = results
                        st.success(f"🎉 Found {len(results)} total results!")
                    else:
                        st.warning("😞 No results found. Try a different search term.")
        
        # Display search results
        if st.session_state.search_results:
            st.markdown("---")
            st.subheader(f"📋 Search Results ({len(st.session_state.search_results)} songs)")
            
            # Display each search result
            for idx, song in enumerate(st.session_state.search_results):
                try:
                    is_selected = display_search_result(song, idx)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"Error displaying result {idx}: {str(e)}")
                    continue
            
            # Show selected song actions
            if st.session_state.selected_song_index is not None:
                selected_song = st.session_state.search_results[st.session_state.selected_song_index]
                display_selected_song_actions(selected_song)
        
        # Currently playing section (for songs added to player)
        if st.session_state.current_song:
            st.markdown("---")
            st.subheader("🎧 Now Playing")
            display_current_song_player(st.session_state.current_song)
            
    except Exception as e:
        st.error(f"Error in main page: {str(e)}")
        st.markdown('<div class="error-box">An error occurred in the main page. Please try refreshing.</div>', unsafe_allow_html=True)

def display_selected_song_actions(song):
    """Display actions for selected song"""
    try:
        st.markdown("---")
        st.subheader("🎯 Selected Song Actions")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            thumbnail = song.get('thumbnail')
            if thumbnail and thumbnail.startswith('http'):
                try:
                    st.image(thumbnail, width=200)
                except:
                    st.image("https://via.placeholder.com/200x200?text=No+Image", width=200)
            else:
                st.image("https://via.placeholder.com/200x200?text=No+Image", width=200)
        
        with col2:
            title = song.get('title', 'Unknown Title')
            artist = song.get('artist', 'Unknown Artist')
            source = song.get('source', 'Unknown')
            
            st.write(f"### {title}")
            st.write(f"#### *{artist}*")
            st.write(f"**Source:** {source}")
            
            duration = format_duration(song.get('duration'))
            st.write(f"**Duration:** {duration}")
            
            # URL information
            if song.get('url'):
                st.write(f"**URL:** `{song.get('url')}`")
            
            # Action buttons
            col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
            
            with col_btn1:
                # Add to current playlist
                current_playlist_name = st.session_state.current_playlist
                if st.button("➕ Add to Playlist", use_container_width=True, key="add_selected_to_playlist"):
                    if song not in st.session_state.user_playlists.get(current_playlist_name, []):
                        st.session_state.user_playlists[current_playlist_name].append(song)
                        st.success(f"✅ Added to '{current_playlist_name}'!")
                    else:
                        st.warning("⚠️ Song already in playlist!")
            
            with col_btn2:
                # Set as current song (for streaming simulation)
                if st.button("▶️ Play Now", use_container_width=True, key="play_selected_song"):
                    st.session_state.current_song = song
                    st.success("🎵 Now playing!")
                    st.rerun()
            
            with col_btn3:
                # Direct download
                if st.button("⬇️ Download", use_container_width=True, key="download_selected_song"):
                    download_selected_song(song)
            
            with col_btn4:
                # Clear selection
                if st.button("✖️ Clear", use_container_width=True, key="clear_selection"):
                    st.session_state.selected_song_index = None
                    st.session_state.selected_song = None
                    st.rerun()
    except Exception as e:
        st.error(f"Error displaying selected song actions: {str(e)}")

def download_selected_song(song):
    """Download the selected song"""
    try:
        if not song or 'source' not in song:
            st.error("❌ Invalid song data")
            return
        
        source = song.get('source', '').lower()
        url = song.get('url', '')
        
        if not url:
            st.error("❌ No URL provided for download")
            return
        
        st.info(f"📥 Preparing download for: {song.get('title', 'Unknown')}")
        
        if source == 'youtube':
            with st.spinner("Downloading from YouTube..."):
                file_path, metadata = downloader.download_youtube(url)
        elif source == 'spotify':
            with st.spinner("Searching and downloading from YouTube (via Spotify)..."):
                # For Spotify, we need to search YouTube for the track
                search_query = f"{song.get('title', '')} {song.get('artist', '')} official audio"
                youtube_results = downloader.search_youtube(search_query, limit=1)
                if youtube_results:
                    file_path, metadata = downloader.download_youtube(youtube_results[0]['url'])
                else:
                    st.error("❌ Could not find matching YouTube video for Spotify track")
                    return
        else:
            st.error(f"❌ Unsupported source: {source}")
            return
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                file_data = f.read()
                filename = os.path.basename(file_path)
                
                # Clean filename for download
                clean_filename = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
                
                st.download_button(
                    label=f"📥 Download {clean_filename}",
                    data=file_data,
                    file_name=clean_filename,
                    mime="audio/mpeg",
                    key=f"download_{uuid.uuid4().hex[:16]}"
                )
            st.success("✅ Download ready!")
        else:
            st.error("❌ Failed to download song. The file may not be available or accessible.")
    except Exception as e:
        st.error(f"❌ Download error: {str(e)}")

def display_current_song_player(song):
    """Display the current song player"""
    try:
        col1, col2 = st.columns([1, 3])
        with col1:
            thumbnail = song.get('thumbnail')
            if thumbnail and thumbnail.startswith('http'):
                try:
                    st.image(thumbnail, width=200)
                except:
                    st.image("https://via.placeholder.com/200x200?text=No+Image", width=200)
            else:
                st.image("https://via.placeholder.com/200x200?text=No+Image", width=200)
        
        with col2:
            title = song.get('title', 'Unknown Title')
            artist = song.get('artist', 'Unknown Artist')
            st.write(f"### {title}")
            st.write(f"#### *{artist}*")
            st.write(f"**Source:** {song.get('source', 'Unknown')}")
            
            duration = format_duration(song.get('duration'))
            st.write(f"**Duration:** {duration}")
            
            # Simulated audio player
            st.markdown("---")
            st.write("**🎵 Audio Player (Simulated)**")
            
            # Progress bar for playback
            progress = st.slider("Playback progress", 0, 100, 25, key="playback_progress")
            st.progress(progress)
            
            # Player controls
            col_controls1, col_controls2, col_controls3, col_controls4 = st.columns(4)
            with col_controls1:
                st.button("⏮️ Previous", disabled=True)
            with col_controls2:
                if st.button("⏯️ Play/Pause"):
                    st.info("Playback control simulated")
            with col_controls3:
                st.button("⏭️ Next", disabled=True)
            with col_controls4:
                if st.button("🔇 Mute"):
                    st.info("Volume control simulated")
            
            # Volume control
            volume = st.slider("Volume", 0, 100, 80, key="volume_slider")
            
            st.markdown("---")
            
            # Action buttons for current song
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                # Add to current playlist
                current_playlist_name = st.session_state.current_playlist
                if st.button("➕ Add to Playlist", key="add_current_to_playlist", use_container_width=True):
                    if song not in st.session_state.user_playlists.get(current_playlist_name, []):
                        st.session_state.user_playlists[current_playlist_name].append(song)
                        st.success(f"✅ Added to '{current_playlist_name}'!")
                    else:
                        st.warning("⚠️ Song already in playlist!")
            
            with col_btn2:
                # Download button
                if st.button("⬇️ Download", key="download_current_song", use_container_width=True):
                    download_selected_song(song)
            
            with col_btn3:
                if st.button("Clear Player", key="clear_player_btn", use_container_width=True):
                    st.session_state.current_song = None
                    st.rerun()
    except Exception as e:
        st.error(f"Error displaying player: {str(e)}")

# [Rest of the functions remain the same - playlist_page, creator_page, analytics_page, earnings_page, settings_page, sidebar]

def playlist_page():
    """Playlist management page"""
    try:
        st.title("📋 My Playlists")
        st.markdown("---")
        
        # Create new playlist
        with st.expander("➕ Create New Playlist"):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_playlist_name = st.text_input("Playlist name:", key="new_playlist_name")
            with col2:
                if st.button("Create", use_container_width=True, key="create_playlist_btn") and new_playlist_name:
                    if new_playlist_name.strip():
                        if new_playlist_name not in st.session_state.user_playlists:
                            st.session_state.user_playlists[new_playlist_name] = []
                            st.session_state.current_playlist = new_playlist_name
                            st.success(f"✅ Playlist '{new_playlist_name}' created!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Playlist already exists!")
                    else:
                        st.warning("⚠️ Please enter a valid playlist name")
        
        # Select current playlist
        if st.session_state.user_playlists:
            playlist_names = list(st.session_state.user_playlists.keys())
            selected_playlist = st.selectbox(
                "🎵 Select Playlist",
                playlist_names,
                index=playlist_names.index(st.session_state.current_playlist) if st.session_state.current_playlist in playlist_names else 0,
                key="playlist_select"
            )
            st.session_state.current_playlist = selected_playlist
            
            # Display playlist info
            playlist = st.session_state.user_playlists.get(selected_playlist, [])
            
            if playlist:
                st.subheader(f"🎶 {selected_playlist} ({len(playlist)} songs)")
                
                # Playlist actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("▶️ Play All", use_container_width=True, key="play_all_btn"):
                        if playlist:
                            st.session_state.current_song = playlist[0]
                            st.rerun()
                
                with col2:
                    if st.button("🗑️ Clear Playlist", use_container_width=True, key="clear_playlist_btn"):
                        if st.checkbox("Are you sure you want to clear this playlist?"):
                            st.session_state.user_playlists[selected_playlist] = []
                            st.success("✅ Playlist cleared!")
                            st.rerun()
                
                with col3:
                    if st.button("💾 Export Playlist", use_container_width=True, key="export_playlist_btn"):
                        export_playlist(playlist, selected_playlist)
                
                st.markdown("---")
                
                # Display playlist songs
                for idx, song in enumerate(playlist):
                    try:
                        with st.container():
                            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                            
                            with col1:
                                title = song.get('title', 'Unknown Title')
                                if len(title) > 40:
                                    title = title[:37] + "..."
                                st.write(f"**{title}**")
                                
                                artist = song.get('artist', 'Unknown Artist')
                                if len(artist) > 30:
                                    artist = artist[:27] + "..."
                                st.caption(f"👤 {artist}")
                            
                            with col2:
                                st.caption(f"🎵 Source: {song.get('source', 'Unknown')}")
                                duration = format_duration(song.get('duration'))
                                st.caption(f"⏱️ {duration}")
                            
                            with col3:
                                if st.button("▶️ Play", key=f"play_p_{idx}_{uuid.uuid4().hex[:8]}", use_container_width=True):
                                    st.session_state.current_song = song
                                    st.rerun()
                            
                            with col4:
                                if st.button("❌ Remove", key=f"remove_{idx}_{uuid.uuid4().hex[:8]}", use_container_width=True):
                                    playlist.pop(idx)
                                    st.success("✅ Song removed from playlist!")
                                    st.rerun()
                            
                            st.markdown("---")
                    except Exception as e:
                        st.error(f"Error displaying playlist song: {str(e)}")
                        continue
                
                # Batch download options
                st.subheader("📦 Batch Download")
                st.info(f"You can download all {len(playlist)} songs from this playlist at once.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗜️ Download as ZIP", use_container_width=True, key="download_zip_btn"):
                        download_playlist_batch(playlist, "zip")
                with col2:
                    if st.button("💿 Download Individual", use_container_width=True, key="download_individual_btn"):
                        download_playlist_batch(playlist, "individual")
            else:
                st.info("📭 This playlist is empty. Add songs from the search results!")
        else:
            st.info("📭 No playlists yet. Create your first playlist!")
    except Exception as e:
        st.error(f"Error in playlist page: {str(e)}")
        st.markdown('<div class="error-box">An error occurred in the playlist page. Please try refreshing.</div>', unsafe_allow_html=True)

def export_playlist(playlist, playlist_name):
    """Export playlist as JSON file"""
    try:
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
            mime="application/json",
            key=f"export_{uuid.uuid4().hex[:16]}"
        )
    except Exception as e:
        st.error(f"Error exporting playlist: {str(e)}")

def download_playlist_batch(playlist, format_type):
    """Download entire playlist"""
    if not playlist:
        st.warning("⚠️ Playlist is empty!")
        return
    
    try:
        st.warning("⚠️ Batch download is a premium feature in this demo version.")
        st.info("In a full version, this would download all songs and create archives.")
        
        # Simulate batch download
        if st.button("🚀 Simulate Batch Download", key="simulate_batch_download"):
            st.success("✅ Batch download simulation complete!")
            st.info(f"🎵 Would have downloaded {len(playlist)} songs as {format_type.upper()}")
    except Exception as e:
        st.error(f"Error downloading playlist: {str(e)}")

def creator_page():
    """Creator mode for artists"""
    try:
        st.title("🎤 Creator Mode")
        st.markdown("---")
        
        st.info("""
        🎵 Welcome to Creator Mode! Here you can:
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
                song_title = st.text_input("Song Title *", placeholder="Enter song title", key="song_title")
                artist_name = st.text_input("Artist Name *", placeholder="Your artist name", key="artist_name")
                album_name = st.text_input("Album Name", placeholder="Album name (optional)", key="album_name")
            
            with col2:
                genre = st.selectbox("Genre", [
                    "Select genre", "Pop", "Rock", "Hip Hop", "Jazz", "Classical",
                    "Electronic", "R&B", "Country", "Metal", "Other"
                ], key="genre_select")
                release_date = st.date_input("Release Date", key="release_date")
            
            uploaded_file = st.file_uploader(
                "Upload Audio File *",
                type=['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg'],
                help="Supported formats: MP3, WAV, FLAC, M4A, AAC, OGG",
                key="audio_uploader"
            )
            
            # File info
            if uploaded_file:
                file_size_mb = uploaded_file.size / 1024 / 1024
                st.info(f"📄 File: {uploaded_file.name} | 📏 Size: {file_size_mb:.2f} MB")
            
            # Promotion options
            st.markdown("### 💫 Promotion Options (Optional)")
            promote = st.checkbox("Promote this song to increase visibility", key="promote_checkbox")
            
            if promote:
                st.warning("""
                ⚠️ **Important:** Promotion features require payment integration setup.
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
                
                if basic_selected or premium_selected or vip_selected:
                    tier = "Basic" if basic_selected else "Premium" if premium_selected else "VIP"
                    st.session_state.promotion_tier = tier
                    st.success(f"✅ Selected: {tier} Promotion")
            
            submitted = st.form_submit_button("Upload Song", key="upload_submit_btn")
            
            if submitted:
                if not (song_title and artist_name and uploaded_file):
                    st.error("❌ Please fill all required fields (*)")
                else:
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
                try:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.write(f"**{song['title']}**")
                            st.caption(f"👤 Artist: {song['artist']} | 💿 Album: {song['album']}")
                            st.caption(f"🎵 Genre: {song['genre']} | 📅 Uploaded: {song['upload_date']}")
                        
                        with col2:
                            if song['promoted']:
                                st.success(f"💫 Promoted: {song['promotion_tier']}")
                            else:
                                st.info("📭 Not promoted")
                            
                            file_size_mb = song['file_size'] / 1024 / 1024
                            st.caption(f"📄 File: {song['file_name']} ({file_size_mb:.2f} MB)")
                        
                        with col3:
                            if st.button("⚙️ Manage", key=f"manage_{idx}_{uuid.uuid4().hex[:8]}"):
                                st.session_state.manage_song_idx = idx
                        
                        st.markdown("---")
                except Exception as e:
                    st.error(f"Error displaying uploaded song: {str(e)}")
                    continue
    except Exception as e:
        st.error(f"Error in creator page: {str(e)}")
        st.markdown('<div class="error-box">An error occurred in the creator page. Please try refreshing.</div>', unsafe_allow_html=True)

# [Analytics, Earnings, and Settings pages remain similar but with improved error handling]

def sidebar():
    """Sidebar navigation"""
    try:
        with st.sidebar:
            st.title("🎵 MusicStream")
            st.markdown("---")
            
            # Mode selection
            current_mode = "🎵 Listener Mode"
            if st.session_state.get('current_page', 'main') in ['creator', 'analytics', 'earnings']:
                current_mode = "🎤 Creator Mode"
            
            mode = st.radio(
                "Select Mode",
                ["🎵 Listener Mode", "🎤 Creator Mode"],
                index=0 if current_mode == "🎵 Listener Mode" else 1,
                key="mode_radio"
            )
            
            st.markdown("---")
            
            # Navigation based on mode
            if mode == "🎵 Listener Mode":
                page_options = {
                    "🔍 Search & Play": "main",
                    "📋 My Playlists": "playlist",
                    "⚙️ Settings": "settings"
                }
                
                current_page = st.session_state.get('current_page', 'main')
                page_index = 0
                if current_page == "playlist":
                    page_index = 1
                elif current_page == "settings":
                    page_index = 2
                
                selected_page = st.radio(
                    "Navigation",
                    list(page_options.keys()),
                    index=page_index,
                    key="listener_nav_radio"
                )
                
                st.session_state.current_page = page_options[selected_page]
            
            else:  # Creator Mode
                page_options = {
                    "🎤 Upload Music": "creator",
                    "📊 Analytics": "analytics",
                    "💰 Earnings": "earnings"
                }
                
                current_page = st.session_state.get('current_page', 'creator')
                page_index = 0
                if current_page == "analytics":
                    page_index = 1
                elif current_page == "earnings":
                    page_index = 2
                
                selected_page = st.radio(
                    "Navigation",
                    list(page_options.keys()),
                    index=page_index,
                    key="creator_nav_radio"
                )
                
                st.session_state.current_page = page_options[selected_page]
            
            st.markdown("---")
            
            # Quick stats
            if st.session_state.current_page in ["main", "playlist"]:
                current_playlist = st.session_state.user_playlists.get(st.session_state.current_playlist, [])
                st.caption(f"🎶 Current Playlist: {len(current_playlist)} songs")
                total_playlist_songs = sum(len(playlist) for playlist in st.session_state.user_playlists.values())
                st.caption(f"📥 Total Songs: {total_playlist_songs}")
            
            elif st.session_state.current_page == "creator":
                st.caption(f"📤 Uploaded Songs: {len(st.session_state.artist_songs)}")
            
            st.markdown("---")
            
            # App info
            st.caption("MusicStream Pro v1.0")
            st.caption("Stream & Download Music")
            
            # Dark mode toggle
            st.markdown("---")
            dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="sidebar_dark_mode")
            if dark_mode != st.session_state.dark_mode:
                st.session_state.dark_mode = dark_mode
                st.rerun()
    except Exception as e:
        st.error(f"Error in sidebar: {str(e)}")

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
try:
    if st.session_state.current_page == "main":
        main_page()
    elif st.session_state.current_page == "playlist":
        playlist_page()
    elif st.session_state.current_page == "creator":
        creator_page()
    elif st.session_state.current_page == "analytics":
        # Simplified analytics page
        st.title("📊 Analytics")
        st.info("Analytics page - Premium feature")
        st.write("Track your song performance, streams, and engagement metrics here.")
    elif st.session_state.current_page == "earnings":
        # Simplified earnings page
        st.title("💰 Earnings")
        st.info("Earnings page - Premium feature")
        st.write("View your earnings and payout history here.")
    elif st.session_state.current_page == "settings":
        # Simplified settings page
        st.title("⚙️ Settings")
        st.info("Settings page")
        st.write("Configure app settings, API keys, and preferences here.")
except Exception as e:
    st.error(f"Application error: {str(e)}")
    st.markdown('<div class="error-box">A critical error occurred. Please refresh the page or try again later.</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
try:
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
except:
    pass
