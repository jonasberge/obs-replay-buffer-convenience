# Requires Python 3.6 for OBS (restriction by OBS itself).
# Does not need any packages installed globally, as the path is modified below
# and the required packages are copied and installed to the OBS scripts folder.

# TODO
# - Warning, when fullscreen application/game is not captured (black screen) - is that possible?
# - Option: Start replay buffer on startup (always on, no automation)
# - Option: Remember last replay buffer state

import os
from collections import OrderedDict
import threading
import time
import sys
import wave

import obspython as obs

# Relative root directory of the script in the OBS folder
SCRIPT_ROOT_REL = '../../data/obs-plugins/frontend-tools/scripts'

SCRIPT_NAME = 'replay-buffer-convenience'
SCRIPT_FILES_DIR = os.path.join(SCRIPT_ROOT_REL, SCRIPT_NAME)
SCRIPT_LOCAL_PKGDIR = os.path.join(SCRIPT_FILES_DIR, 'python-packages')

# Add the local package directory to the PYTHONPATH for below package dependencies.
sys.path.append(os.path.abspath(SCRIPT_LOCAL_PKGDIR))

import psutil
import pyaudio

SCRIPT_PROPS = None
SCRIPT_SETTINGS = None

SCRIPT_WORKER_THREAD_CANCEL = False
SCRIPT_WORKER_THREAD_RELOAD = False

def set_script_settings(settings):
    global SCRIPT_SETTINGS
    obs.obs_data_set_default_int(settings, "check_frequency_sec", 4)
    obs.obs_data_set_default_bool(settings, "enable_automation", True)
    obs.obs_data_set_default_bool(settings, "enable_voice_start", True)
    obs.obs_data_set_default_bool(settings, "enable_voice_stop", True)
    obs.obs_data_set_default_bool(settings, "enable_voice_save", True)
    SCRIPT_SETTINGS = settings

def script_update(settings):
    set_script_settings(settings)
    global SCRIPT_WORKER_THREAD_RELOAD
    SCRIPT_WORKER_THREAD_RELOAD = True

def script_description():
	return "Enables the replay buffer if one of the configured applications is running." \
        + "\n\nIMPORTANT: When adding an application to the list via the below button, restart OBS to see the changes reflected in the UI!" \
        + "\n\nPlays a voice line whenever a replay buffer event occurs, if checkboxes are ticked."

def on_add_button_pressed(props, prop, *args, **kwargs):
    global SCRIPT_PROPS
    global SCRIPT_SETTINGS
    application_path = obs.obs_data_get_string(SCRIPT_SETTINGS, "application_path")
    current_paths_string = obs.obs_data_get_string(SCRIPT_SETTINGS, "application_paths")
    current_paths = OrderedDict.fromkeys(current_paths_string.split(';'))
    if '' in current_paths:
        current_paths.pop('')
    if application_path in current_paths:
        current_paths.pop(application_path)
    current_paths[application_path] = None
    new_paths_value = ';'.join(list(current_paths.keys()))
    obs.obs_data_set_string(SCRIPT_SETTINGS, "application_paths", new_paths_value)
    obs.obs_properties_apply_settings(SCRIPT_PROPS, SCRIPT_SETTINGS)
    # there seems to be no way to update the UI to reflect the changes...
    # apply_settings doesn't do it.

def on_reset_button_pressed(props, prop, *args, **kwargs):
    global SCRIPT_PROPS
    global SCRIPT_SETTINGS
    obs.obs_data_set_string(SCRIPT_SETTINGS, "application_paths", "")
    obs.obs_properties_apply_settings(SCRIPT_PROPS, SCRIPT_SETTINGS)

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_bool(props, "enable_automation", "Enable automation")
    obs.obs_properties_add_bool(props, "enable_voice_start", "Voice on replay buffer start")
    obs.obs_properties_add_bool(props, "enable_voice_stop", "Voice on replay buffer stop")
    obs.obs_properties_add_bool(props, "enable_voice_saved", "Voice on replay buffer save")
    prop = obs.obs_properties_add_int_slider(props, "check_frequency_sec", "Check frequency (seconds)", 1, 30, 1)
    obs.obs_property_set_long_description(prop, "Sets how frequently the script checks if one of the configured applications is running. A lower value will check more frequently, but that uses more system resources. A good rule of thumb is to set it to the time it takes from starting the game to the point at which events occur that you want to be clipped, e.g. 10 seconds.")
    obs.obs_properties_add_path(props, "application_path", "Application path", obs.OBS_PATH_FILE, "*.exe", "/")
    prop = obs.obs_properties_add_button(props, "add_path", "Add path to list", on_add_button_pressed)
    obs.obs_property_set_long_description(prop, "Adds the selected path to the paths in the list below. Restart OBS to see the changes reflected in the user interface!")
    prop = obs.obs_properties_add_text(props, "application_paths", "Applications, separated by semicolons", obs.OBS_TEXT_MULTILINE)
    obs.obs_property_set_long_description(prop, "If one of these applications is running, the replay buffer will be enabled.")
    obs.obs_properties_add_button(props, "clear_paths", "Clear all paths", on_reset_button_pressed)
    global SCRIPT_PROPS
    SCRIPT_PROPS = props
    return props

def is_any_executable_running(paths):
    if len(paths) == 0:
        return
    paths_normed = set(os.path.normpath(p) for p in paths)
    for process in psutil.process_iter():
        try:
            cmdline_path = process.cmdline()[0]
            process_path = os.path.abspath(cmdline_path)
            if os.path.normpath(process_path) in paths_normed:
                return True
        except Exception:
            pass
    return False

# Error threshold in microseconds
REPBUF_ERROR_THRESHOLD_T_US = 2500

LAST_REPBUF_EVENT_T_US = None
LAST_REPBUF_AUTOACTION_T_US = None
LAST_EXECUTABLE_STATE = None
LAST_EXECUTABLE_STATE_CHANGE_T_US = None

def time_micros():
    return time.time() * 1000 * 1000

def check_replay_buffer(application_paths):
    is_on = obs.obs_frontend_replay_buffer_active()
    is_exe_running = is_any_executable_running(application_paths)
    should_enable = is_exe_running and not is_on
    should_disable = not is_exe_running and is_on

    global LAST_REPBUF_AUTOACTION_T_US

    has_user_action = False
    if LAST_REPBUF_EVENT_T_US is not None:
        if LAST_REPBUF_AUTOACTION_T_US is None:
            # We haven't yet made an automatic action, but the state has been changed.
            # It must have been a user action.
            has_user_action = True
        elif abs(LAST_REPBUF_EVENT_T_US - LAST_REPBUF_AUTOACTION_T_US) > REPBUF_ERROR_THRESHOLD_T_US:
            # The last replay buffer event was not caused by an automatic action,
            # so it must have been a user action.
            if LAST_REPBUF_EVENT_T_US > LAST_REPBUF_AUTOACTION_T_US:
                # The last event should have happened after the last auto action.
                has_user_action = True

    global LAST_EXECUTABLE_STATE
    global LAST_EXECUTABLE_STATE_CHANGE_T_US
    if LAST_EXECUTABLE_STATE is None or LAST_EXECUTABLE_STATE != is_exe_running:
        LAST_EXECUTABLE_STATE_CHANGE_T_US = time_micros()
    LAST_EXECUTABLE_STATE = is_exe_running

    if has_user_action and LAST_REPBUF_EVENT_T_US > LAST_EXECUTABLE_STATE_CHANGE_T_US:
        # There is a user action and the user's action time is after the last time
        # the state of any executables running changed.
        # We want to automatically change the replay buffer state if said state changes,
        # despite any user action.
        # In other words, the user action sticks until the executable running state changes.
        if not is_on and should_enable or is_on and should_disable:
            # In this case we would work against the user action, so cancel.
            return

    if should_enable:
        obs.obs_frontend_replay_buffer_start()
        LAST_REPBUF_AUTOACTION_T_US = time_micros()
    
    if should_disable:
        obs.obs_frontend_replay_buffer_stop()
        LAST_REPBUF_AUTOACTION_T_US = time_micros()

def background_worker():
    global SCRIPT_WORKER_THREAD_RELOAD
    global SCRIPT_WORKER_THREAD_CANCEL
    global SCRIPT_SETTINGS
    while True:
        application_paths = obs.obs_data_get_string(SCRIPT_SETTINGS, "application_paths").split(';')
        check_frequency_sec = obs.obs_data_get_int(SCRIPT_SETTINGS, "check_frequency_sec")
        print("Using the following application paths: " + repr(application_paths))
        print("Using the following check frequency: " + str(check_frequency_sec))
        while True:
            if obs.obs_data_get_bool(SCRIPT_SETTINGS, "enable_automation"):
                check_replay_buffer(application_paths)
            time.sleep(check_frequency_sec)
            if SCRIPT_WORKER_THREAD_RELOAD or SCRIPT_WORKER_THREAD_CANCEL:
                break
        SCRIPT_WORKER_THREAD_RELOAD = False
        if SCRIPT_WORKER_THREAD_CANCEL:
            break
    SCRIPT_WORKER_THREAD_CANCEL = False

AUDIO_PLAYERS = dict()
AUDIO_FILES = {
    'start': os.path.join(SCRIPT_FILES_DIR, 'replay_start.wav'),
    'saved': os.path.join(SCRIPT_FILES_DIR, 'replay_saved.wav'),
    'stop': os.path.join(SCRIPT_FILES_DIR, 'replay_stop.wav'),
}

def script_load(settings):
    obs.obs_frontend_add_event_callback(on_event)
    global SCRIPT_SETTINGS
    set_script_settings(settings)
    create_audio_players()
    worker = threading.Thread(target=background_worker, args=())
    worker.setDaemon(True)
    global SCRIPT_WORKER_THREAD_CANCEL
    SCRIPT_WORKER_THREAD_CANCEL = False
    worker.start()

def script_unload():
    obs.obs_frontend_remove_event_callback(on_event)
    global SCRIPT_WORKER_THREAD_CANCEL
    SCRIPT_WORKER_THREAD_CANCEL = True
    destroy_audio_players()

def create_audio_players():
    global AUDIO_FILES
    global AUDIO_PLAYERS
    pyaudio_instance = pyaudio.PyAudio()
    for name, filename in AUDIO_FILES.items():
        player = AudioPlayer(filename, pyaudio_instance)
        AUDIO_PLAYERS[name] = player
        player.open()

def destroy_audio_players():
    global AUDIO_PLAYERS
    for player in AUDIO_PLAYERS.values():
        player.close()
    AUDIO_PLAYERS = dict()

def on_event(event):
    global LAST_REPBUF_EVENT_T_US
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STARTING:
        LAST_REPBUF_EVENT_T_US = time_micros()
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STOPPING:
        LAST_REPBUF_EVENT_T_US = time_micros()

    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STARTED:
        if obs.obs_data_get_bool(SCRIPT_SETTINGS, "enable_voice_start"):
            play_voiceline('start')
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STOPPED:
        if obs.obs_data_get_bool(SCRIPT_SETTINGS, "enable_voice_stop"):
            play_voiceline('stop')
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        if obs.obs_data_get_bool(SCRIPT_SETTINGS, "enable_voice_saved"):
            play_voiceline('saved')

def play_voiceline(audio_player_name):
    global AUDIO_PLAYERS
    audio_player = AUDIO_PLAYERS[audio_player_name]
    thread = threading.Thread(target=lambda: audio_player.play())
    thread.setDaemon(True)
    thread.start()

class AudioPlayer:
    DEFAULT_CHUNKSIZE = 1024

    def __init__(self, wav_filename, pyaudio_instance = pyaudio.PyAudio(), chunksize = DEFAULT_CHUNKSIZE):
        self._source_filename = wav_filename
        self._pyaudio = pyaudio_instance
        self._sampwidth = None
        self._nchannels = None
        self._framerate = None
        self._chunks = []
        self._chunksize = chunksize
    
    def open(self):
        self._read_file()
    
    def _read_file(self):
        wf = wave.open(self._source_filename, 'rb')
        self._sampwidth = wf.getsampwidth()
        self._nchannels = wf.getnchannels()
        self._framerate = wf.getframerate()
        data = wf.readframes(self._chunksize)
        while len(data):
            self._chunks.append(data)
            data = wf.readframes(self._chunksize)
    
    def play(self):
        p = self._pyaudio
        stream = p.open(format=p.get_format_from_width(self._sampwidth),
            channels=self._nchannels,
            rate=self._framerate,
            output=True)
        for chunk in self._chunks:
            stream.write(chunk)
        stream.stop_stream()
        stream.close()
    
    def close(self):
        self._pyaudio.terminate()
