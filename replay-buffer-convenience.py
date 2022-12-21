# Requires Python 3.6 for OBS (restriction by OBS itself).
# Also requires the following Python packages to be installed globally:
# - psutil
# - playsound

# TODO
# - Warning, when fullscreen application/game is not captured (black screen)

import os
from collections import OrderedDict
import threading
import time

import psutil
from playsound import playsound
import obspython as obs

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
    obs.obs_properties_add_bool(props, "enable_voice_save", "Voice on replay buffer save")
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

def check_replay_buffer(application_paths):
    if is_any_executable_running(application_paths):
        if not obs.obs_frontend_replay_buffer_active():
            obs.obs_frontend_replay_buffer_start()
    else:
        if obs.obs_frontend_replay_buffer_active():
            obs.obs_frontend_replay_buffer_stop()

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

def script_load(settings):
    obs.obs_frontend_add_event_callback(on_event)
    global SCRIPT_SETTINGS
    set_script_settings(settings)
    worker = threading.Thread(target=background_worker, args=())
    worker.setDaemon(True)
    global SCRIPT_WORKER_THREAD_CANCEL
    SCRIPT_WORKER_THREAD_CANCEL = False
    worker.start()

def script_unload(settings):
    obs.obs_frontend_remove_event_callback(on_event)
    global SCRIPT_WORKER_THREAD_CANCEL
    SCRIPT_WORKER_THREAD_CANCEL = True

def on_event(event):
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STARTED:
        play_audiofile(os.path.abspath('../../data/obs-plugins/frontend-tools/scripts/front-end-feedback/replay_start.mp3'))
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STOPPED:
        play_audiofile(os.path.abspath('../../data/obs-plugins/frontend-tools/scripts/front-end-feedback/replay_stop.mp3'))
    if event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        play_audiofile(os.path.abspath('../../data/obs-plugins/frontend-tools/scripts/front-end-feedback/replay_saved.mp3'))

def play_audiofile(path):
    thread = threading.Thread(target=playsound, args=(path,))
    thread.setDaemon(True)
    thread.start()
