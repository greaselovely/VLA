import os
import cv2
import json
import cursor
import hashlib
import logging
import requests
import numpy as np
from sys import exit
from time import sleep
from pathlib import Path
from random import choice
from wurlitzer import pipes
from datetime import datetime
from http.client import IncompleteRead

from moviepy.editor import ImageSequenceClip, AudioFileClip, concatenate_videoclips

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

"""
TO DO
-clean up function
    wait to allow the video to be reviewed
    asking if we want to remove the images

"""

IMAGE_URL = "https://public.nrao.edu/wp-content/uploads/temp/vla_webcam_temp.jpg"
WEBPAGE = "https://public.nrao.edu/vla-webcam/"

USER_AGENTS = [
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Firefox/90.0",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:88.0) Firefox/88.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Firefox/92.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:96.0) Firefox/96.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 11; Mobile; rv:100.0) Firefox/100.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 Edg/94.0.992.50",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Mobile Safari/537.36"
]

home = Path.home()
LOGGING_FOLDER = os.path.join(home, "VLA/logging")
os.makedirs(LOGGING_FOLDER, exist_ok=True)
LOGGING_FILE = os.path.join(LOGGING_FOLDER, "vla_log.txt")
logging.basicConfig(
    level = logging.INFO,  # Set the logging level (INFO, WARNING, ERROR, etc.)
    filename = LOGGING_FILE,
    format = '%(asctime)s - %(levelname)s - %(message)s'
)

class ImageDownloader:
    """
    Class to handle downloading images and managing hash collisions, while explicitly using the session passed to each download attempt.
    """

    def __init__(self, session, out_path):
        self.out_path = Path(out_path)
        self.hash_collisions_path = self.out_path / "hash_collisions"  # Directory for hash collisions
        self.session = session
        self.prev_image_filename = None
        self.prev_image_size = None
        self.prev_image_hash = None
        # self.hash_collisions_path.mkdir(exist_ok=True)  # Ensure the directory exists

    def compute_hash(self, image_content):
        return hashlib.sha256(image_content).hexdigest()

    def download_image(self, session, IMAGE_URL):
        today_short_date = datetime.now().strftime("%m%d%Y")
        today_short_time = datetime.now().strftime("%H%M%S")
        
        r = session.get(IMAGE_URL, verify=False)
        if r is None or r.status_code != 200:
            logging.error("Image was not downloaded; r = None or not 200")
            return None

        # logging.info(f"Server response headers: {r.headers}")

        image_content = r.content
        image_size = len(image_content)
        image_hash = self.compute_hash(image_content)

        logging.info(f"Download Image Func: {r.status_code}. Hash {image_hash}")

        if image_size == 0:
            logging.error("Image was not downloaded; zero size")
            return None

        if self.prev_image_hash == image_hash:
            """
            uncomment if you want to inspect the images by hand.  
            Also uncomment the hash_collision_path above under __init__.
            """
            # FileName = f'{today_short_date}_{today_short_time}.jpg'
            # collision_file_path = self.hash_collisions_path / FileName
            # with open(collision_file_path, 'wb') as f:
            #     f.write(image_content)
            logging.error(f"Image was not saved; same hash as previous {image_hash}")
            return None

        FileName = f'vla.{today_short_date}.{today_short_time}.jpg'
        with open(self.out_path / FileName, 'wb') as f:
            f.write(image_content)
        self.prev_image_filename = FileName
        self.prev_image_size = image_size
        self.prev_image_hash = image_hash  # Ensure this is updated only here
        return image_size  # Image saved, return size

def load_config():
    """
    Loads configuration settings from a 'config.json' file.

    This function tries to open and read a 'config.json' file located in the same directory as the script.
    If the file is not found, it creates a new one with default proxy settings.
    If the file is found but contains invalid JSON, an error is logged and None is returned.

    Returns:
        dict or None: A dictionary with configuration settings if successful, None otherwise.
    """
    file_name = 'config.json'
    local_path = Path(__file__).resolve().parent
    config_path = Path.joinpath(local_path, file_name)

    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError as e:
        """
        We'll build an empty config.json file.
        Edit to use proxies
        ie: "http" : "http://127.0.0.1:8080", "https" : "http://127.0.0.1:8080"
        """
        logging.error(f"config.json problem; {e}")
        config_init_starter = {"proxies" : {"http" : "", "https": ""}}
        with open(config_path, 'w') as file:
            json.dump(config_init_starter, file, indent=2)
         # recursion, load the config file since it wasn't found earlier
        return load_config()
    except json.JSONDecodeError as e:
        logging.error(f"JSON Decode error: {e}")
        print(f"Error decoding JSON in '{config_path}'.")
        return None

def clear():
    """
    Clears the terminal screen.

    This function checks the operating system and uses the appropriate command to clear the terminal screen.
    It uses 'cls' for Windows (nt) and 'clear' for other operating systems.
    """
    os.system("cls" if os.name == "nt" else "clear")

def activity(char, images_folder, image_size):
    """
    Displays the current status of the image downloading activity in the terminal.

    This function is called to print the current iteration number, the total count of 
    JPEG images in the specified folder, and the size of the last downloaded image. 
    If the last downloaded image size is zero, it indicates that the image was not saved.

    Args:
        char (int): The current iteration number of the downloading loop.
        images_folder (str): Path to the folder where images are being saved.

    Returns:
        None: This function does not return anything. It only prints to stdout.
    """
    clear()
    files = os.listdir(images_folder)
    jpg_count = sum(1 for file in files if file.lower().endswith('.jpg'))
    print(f"Iter: {char}\nImage Count: {jpg_count}\nImage Size: {image_size}\n", end="\r", flush=True)

def create_session(webpage, verify=False):
    """
    Initializes a session and verifies its ability to connect to a given webpage.
    
    Args:
        webpage (str): The URL to test the session's connectivity.
        verify (bool): Whether to verify the SSL certificate.

    Returns:
        A requests.Session object if successful, None otherwise.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": choice(USER_AGENTS),
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

    # Configure proxies if they are set in config
    proxies = config.get('proxies', {})
    if proxies:
        session.proxies.update(proxies)

    # Perform an initial request to verify connectivity
    try:
        response = session.get(webpage, verify=verify, timeout=10)
        response.raise_for_status()  # Raises a HTTPError for bad responses
        logging.info(f"Session Created: {session.cookies.get_dict()}, {session.headers.values()}")
        return session
    except (requests.RequestException, requests.HTTPError) as e:
        logging.error(f"Failed to connect to {webpage} with session: {e}")
        return None

def make_request(session, verify=False):
    """
    Makes an HTTP request using the specified session and handles retries.

    This function attempts to make a GET request using the given session. 
    If proxies are configured, they are used in the request. The function retries 
    the request up to a maximum number of times in case of connection errors.

    Args:
        session (requests.Session): The session object to be used for making the request.
        verify (bool): Flag to determine whether to verify the server's TLS certificate.

    Returns:
        requests.Response or None: The response object if the request is successful, 
                                   None if there are connection errors or exceptions.
    """
    global config
    proxies = config.get('proxies', {})
    http_proxy = proxies.get('http', '')
    https_proxy = proxies.get('https', '')
    max_retries = 3
    for _ in range(max_retries):
        try:
            if http_proxy and https_proxy:
                response = requests.get(session, proxies=proxies, verify=verify)
                response.raise_for_status()
                return response
            else:
                response = requests.get(session, verify=verify)
                response.raise_for_status()
                return response
        except IncompleteRead as e:
            logging.error(f"Incomplete Read (make_request()): {e}")
            print(f"IncompleteRead Error: {e}")
            return None
        except requests.RequestException as e:
            logging.error(f"Request Exception (make_request()): {e}")
            print(f"RequestException Error: {e}")
            return None
    return None

def create_images_dict(images_folder) -> list:
    """
    Creates a dictionary of image file paths from the specified folder, filtered by the provided date.

    This function filters images by the date included in their filenames, processes each image using cv2 
    to check for errors, and compiles a list of valid image file paths. It uses wurlitzer pipes to capture 
    any error messages from cv2. Images with errors detected by cv2 are excluded from the returned list.

    Args:
        images_folder (str): The directory where the images are stored.
        today_short_date (str): The date string used to filter images relevant to the current day.

    Returns:
        list: A list of valid image file paths, excluding any that cv2 identifies as having errors.
    """
    images = sorted([img for img in os.listdir(images_folder) if img.endswith(".jpg")]) 
    images_dict = {}

    for n, image in enumerate(images):
        print(f"[i]\t{n}", end='\r')
        full_image = os.path.join(images_folder, image)
        with pipes() as (out, err):
            cv2.imread(full_image)
        err.seek(0)
        error_message = err.read()
        images_dict[full_image] = error_message

    valid_files = [file_path for file_path, error_message in images_dict.items() if error_message == ""]
    return valid_files

def calculate_video_duration(num_images, fps) -> int:
    """
    Calculates the expected duration of a time-lapse video.

    Args:
        num_images (int): The number of images to be included in the time-lapse video.
        fps (int): The frames per second rate for the time-lapse video.

    Returns:
        int: The expected duration of the time-lapse video in milliseconds.
    """
    duration_sec = num_images / fps
    duration_ms = int(duration_sec * 1000)
    return duration_ms

def audio_download(duration_threshold=150000) -> tuple[str, str]:
    """
    Downloads a random song from a specified URL, meeting a minimum duration criterion.

    This function randomly selects a song from the "soundtracks.loudly.com/songs" API,
    ensuring the song's duration exceeds a specified threshold. If the first chosen song
    does not meet the duration threshold, the function retries up to three times to find
    a suitable song. If a song meeting the criteria is found, it is downloaded and saved
    in a specified subdirectory.

    Parameters:
    - duration_threshold (int): The minimum duration (in milliseconds) required for the song to be considered for download. 
                                Default value is 150,000 milliseconds (2 minutes and 30 seconds).

    Returns:
    - tuple: A tuple containing the name of the downloaded audio file and its full path. 
             Returns None if no song meeting the criteria could be found or if an error occurs.

    Raises:
    - requests.RequestException: If an HTTP request error occurs during the song selection or download process.

    Note:
    The function prints messages to the console indicating the status of the download or any errors encountered.
    """
    try:
        user_agent = choice(USER_AGENTS)
        headers = {"User-Agent": user_agent}
        url = "https://soundtracks.loudly.com/songs"
        r = requests.get(url, headers=headers)
        r.raise_for_status()  # Raises stored HTTPError, if one occurred.
        
        last_page = r.json().get('pagination_data', {}).get('last_page', 20)
        page = choice(range(1, last_page + 1))
        url = f"https://soundtracks.loudly.com/songs?page={page}"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        
        data = r.json()
        songs = data.get('items', [])
        if not songs:
            print("No songs found.")
            return
        
        song = choice(songs)
        song_duration = song.get('duration', 0)
        
        # If the song duration is less than the duration_threshold, retry fetching a song
        attempts = 1
        while song_duration <= duration_threshold:
            print(f"[i]\tSong Attempts: {attempts}", end='\r')
            song = choice(songs)
            song_duration = song.get('duration', 0)
            attempts += 1
            if attempts > 10:
                print(f"[!]\tIt's possible there are no songs")
            
        
        if song_duration <= duration_threshold:
            print(f"\n\n[!]\tFailed to find a song longer than {duration_threshold}. Exiting.\n\n")
            sys.exit()
        
        song_download_path = song.get('music_file_path')
        if not song_download_path:
            print("Song download path not found.")
            return
        
        # Download song content
        r = requests.get(song_download_path)
        r.raise_for_status()
        
        # Prepare filename and save
        song_name = song.get('title', 'Unknown Song').replace('/', '_')  # Replace slashes to avoid path issues
        audio_name = f"{song_name}.mp3"
        audio_path = os.path.join(home, "VLA/audio")  # Saving in a subfolder
        full_audio_path = os.path.join(audio_path, audio_name)
        
        os.makedirs(audio_path, exist_ok=True)
        with open(full_audio_path, 'wb') as f:
            f.write(r.content)
            
        print(f"[>]\tDownloaded: {audio_name}")

        return audio_name, full_audio_path
    
    except requests.RequestException as e:
        print(f"[!]\tAn error occurred:\n[!]\t{e}")

def create_time_lapse(valid_files, video_path, fps, audio_path, crossfade_seconds=3, end_black_seconds=3):
    """
    Creates a time-lapse video from a series of images, featuring fade-in from black, and adds an audio track with fade-in at the beginning and fade-out at the end.
    Args:
        valid_files (list): List of paths to image files for the time-lapse.
        output_path (str): Path where the time-lapse video will be saved.
        fps (int): Frames per second for the video.
        audio_path (str): Path to the audio file to be used in the video.
        crossfade_seconds (int, optional): Duration of the crossfade to black at the video's end.
        end_black_seconds (int, optional): Duration of the black screen at the video's end.
    """
    # Create the video clip from images
    video_clip = ImageSequenceClip(valid_files, fps=fps)

    # Load the audio file
    audio_clip = AudioFileClip(audio_path)

    # Calculate total video duration
    total_video_duration = video_clip.duration

    # Add a fade-in from black effect to the video
    video_clip = video_clip.fadein(crossfade_seconds)

    # Add a fade-out to black effect to the video
    video_clip = video_clip.fadeout(crossfade_seconds)

    # Cut the audio to match the video duration (if longer)
    audio_clip = audio_clip.subclip(0, total_video_duration)

    # Apply audio fade-in and fade-out effects
    audio_clip = audio_clip.audio_fadein(crossfade_seconds).audio_fadeout(crossfade_seconds)

    # Set the processed audio to the video
    video_clip = video_clip.set_audio(audio_clip)

    # Add end black screen to the video by creating a black frame and concatenating it to the end
    black_frame_clip = ImageSequenceClip([np.zeros((video_clip.h, video_clip.w, 3))], fps=fps).set_duration(end_black_seconds)
    final_clip = concatenate_videoclips([video_clip, black_frame_clip])

    # Write the final video file to disk
    final_clip.write_videofile(video_path, codec="libx264", audio_codec="aac")

    # Release resources
    video_clip.close()
    audio_clip.close()
    final_clip.close()


def main():
    """
    The main function of the script. It orchestrates the process of downloading images,
    creating a time-lapse video, and handling exceptions.

    This function sets up the necessary folders, initializes a session, and continuously
    downloads images at a set interval. In case of a keyboard interrupt, it proceeds to 
    validate the downloaded images and create a time-lapse video from them. Any errors 
    encountered during image processing or video creation are logged and displayed.
    """
    try:
        clear()
        cursor.hide()
        IMAGES_FOLDER = os.path.join(home, "VLA/images")
        VIDEO_FOLDER = os.path.join(home, "VLA")
        global config
        config = load_config()
        
        os.makedirs(IMAGES_FOLDER, exist_ok=True)
        
        session = create_session(WEBPAGE)
        
        downloader = ImageDownloader(session, IMAGES_FOLDER)

        i = 1
        while True:
            try:
                SECONDS = choice(range(15,22))
                image_size = downloader.download_image(session, IMAGE_URL)
                # If we don't save the image because the hash is the same
                # then the image_size is None.  This is strictly console
                # notification and probably should be deprecated.
                if image_size is not None: 
                    activity(i, IMAGES_FOLDER, image_size)
                else:
                    clear()
                    print(f"Error downloading image at iteration: {i}")
                sleep(SECONDS)
                
                i += 1
            except requests.exceptions.RequestException as e:
                logging.error(f"Session timeout or error detect, re-establishing session: {e}")
                print(f"Session timeout or error detect, re-establishing session...\n{e}\n")
                session = create_session(WEBPAGE)
                downloader.download_image(session, IMAGE_URL)

    except KeyboardInterrupt:
        try:
            fps = 10
            today_short_date = datetime.now().strftime("%m%d%Y")
            video_path = os.path.join(VIDEO_FOLDER, f"VLA.{today_short_date}.mp4")
            logging.info(f"Validating Images")
            print("\n[i]\tValidating Images...")
            valid_files = create_images_dict(IMAGES_FOLDER)
            duration_threshold = calculate_video_duration(len(valid_files), fps)
            logging.info(f"Video Duration: {duration_threshold}")
            audio_name, full_audio_path = audio_download(duration_threshold)
            print(f"[i]\tCreating Time Lapse Video\n{'#' * 50}")
            logging.info(f"Creating Time Lapse")
            create_time_lapse(valid_files, video_path, fps, full_audio_path, crossfade_seconds=3, end_black_seconds=3)
            logging.info(f"Time Lapse Saved: {video_path}")
            print(f"{'#' * 50}\n[i]\tTime Lapse Saved:\n[>]\t{video_path}")

        except Exception as e:
            logging.error(f"Keyboard Interrupt; Image Processing Problem: {e}")
            print(f"\n\n[!]\tError processing images to video:\n[i]\t{e}")
        finally:
            cursor.show()

            
if __name__ == "__main__":
    main()
