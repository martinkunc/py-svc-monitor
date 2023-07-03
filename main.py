import tk
# from tkinter import *
import tkinter
import tkinter.ttk as ttk
import jstyleson
import math
import psutil
import os
import time
import threading
import logging
import requests
import urllib
import urllib3

# services status refresh is updated each (ms)
TICK_TIME = 500

root = None


def get_process_path(process_name: str) -> str:
    processes = filter(lambda p: psutil.Process(
        p).name() == process_name, psutil.pids())
    for pid in processes:
        try:
            path = psutil.Process(pid).cmdline()[1]
            abs_path = os.path.abspath(path)
            return abs_path
        except (IndexError, PermissionError):
            pass
    return None


def fill_config_details(svcs_config):
    svcs_count = len(svcs_config)
    for svc_idx in range(svcs_count):
        
        if "process" not in svcs_config[svc_idx]:
            continue
        process = svcs_config[svc_idx]["process"]
        process_name = process["name"]
        if not process["path"]:
            process["path"] = get_process_path(process_name)
        svcs_config[svc_idx]["_process_status"] = "-"


def start_all_svcs(svcs):
    svcs_count = len(svcs)
    for svc_idx in range(svcs_count):
        process = svcs[svc_idx]["process"]
        if not process:
            continue
        process_name = process["name"]
        if not process["path"]:
            process["path"] = get_process_path(process_name)

def get_process_status(process_name):
    
    is_running = False
    try:
      processes = list(filter(lambda p: psutil.Process(p).name() == process_name, psutil.pids()))
      if (len(processes) == 1):
        retries = 3
        while not is_running and retries > 0:
            try:
                is_running = psutil.Process(processes[0]).is_running()
            except Exception:
                retries -=1
      else:
          pass
    except Exception as e:
        pass
    return is_running

def load_config():
    with open('svcs.json') as svcs_file:
        config = svcs_file.read()
        parsed_config = jstyleson.loads(config)
        return parsed_config

def fix_url(url):
    default_scheme = "http"
    forced_scheme = False
    if '//' not in url:
        url = '%s%s' % (default_scheme+'://', url)
        forced_scheme = True
    parsed = urllib.parse.urlparse(url)
    if forced_scheme:
        if parsed.port == 433:
            parsed.scheme = 'https'
    url = urllib.parse.urlunparse(parsed)
    return url


def get_http_response_details(url):
    full_url = fix_url(url)
    #url = full_url.geturl()
    try:
        response = requests.get(full_url)
    except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
        ctx = e
        while ctx.__context__ is not None:
            ctx = ctx.__context__
        return (0, ctx.strerror, e.strerror)
    return (response.status_code, response.text, None)


def ui_tick(svcs):
    last_update_ui = svcs["last_update_ui"]
    if last_update_ui:
        last_update_ui.config(text=svcs["_last_update_ui"])

    for svcs_idx in range(len(svcs["config"])):
    
      svc_name = svcs["config"][svcs_idx]["name"]
      svc_process = None
      if "process" in svcs["config"][svcs_idx]:
        svc_process = svcs["config"][svcs_idx]["process"]

      if svc_process:
        if "_process_status" in svc_process:
            process_status = svc_process["_process_status"]
            process_status = "🟢IsRunning" if process_status else "🔴NotFound"
            svcs["svcs_ui"][svc_name].config(text=process_status )
      
      endpoints = svcs["config"][svcs_idx]["endpoints"]
      for ep_key in endpoints.keys():
        ep_config = endpoints[ep_key]
        url = svc_name = svcs["config"][svcs_idx]["url"] +  ep_config["suffix"]
        #svcs["svcs_ui"][svc_name]["endpoints"]
        if "response_ui" in endpoints[ep_key] and "response_details" in endpoints[ep_key]:
            response_details = endpoints[ep_key]["response_details"]
            response_icon = process_status = "🟢" if response_details[2] == None and response_details[0] == 200 else "🔴"
            long_details = response_details[1]
            if len(long_details) > 20:
                long_details = long_details[:20]+".."
            response_text = process_status = response_details[2] if response_details[2] != None else (str(response_details[0]) + long_details)
            endpoints[ep_key]["response_ui"].config(text=(response_icon + response_text))
    # calls itself every 200 milliseconds
    # to update the time display as needed
    # could use >200 ms, but display gets jerky
    root.after(TICK_TIME, lambda: ui_tick(svcs))



def background_update(svcs):
    quit_event = svcs["quit_event"]
    while not quit_event.wait(TICK_TIME / 1000):
      svcs["_last_update_ui"] = time.strftime('%H:%M:%S')

      for svcs_idx in range(len(svcs["config"])):
      
        svc_name = svcs["config"][svcs_idx]["name"]
        svc_process = None
        if "process" in svcs["config"][svcs_idx]:
            svc_process = svcs["config"][svcs_idx]["process"]
        if svc_process:
          svc_process["_process_status"] = get_process_status(svc_process["name"])
        endpoints = svcs["config"][svcs_idx]["endpoints"]
        for ep_key in endpoints.keys():
            ep_config = endpoints[ep_key]
            url = svc_name = svcs["config"][svcs_idx]["url"] +  ep_config["suffix"]
            endpoints[ep_key]["response_details"] = get_http_response_details(url)

def quit_app(root, svcs):
    quit_event = svcs["quit_event"]
    quit_event.set()
    try:
        root.destroy()
    except:
        pass


def main():
    global root
    global last_update_ui
    global svcs_ui

    svcs_ui = {}
    last_update_ui = None

    config = load_config()
    fill_config_details(config)
    svcs = {"config": config, "svcs_ui":{}}
    svcs["quit_event"] = threading.Event()
    svcs["_last_update_ui"] = "-"
    print(svcs)

    root = tkinter.Tk(className='Http Service monitor')
    root.geometry("800x600")
    # frm = ttk.Frame(root, padding=10)
    # frm.grid()

    # frm_main = ttk.Frame(root)
    frm = ttk.Frame(root, padding=10)
    frm.grid(column=0, row=0)

    svcs_grid_start = 1
    svcs_count = len(svcs["config"])
    max_endpoints = 0
    for svc_idx in range(svcs_count):
        svc_name = svcs["config"][svc_idx]["name"]
        svc_label = ttk.Label(frm, text=svc_name, padding=10)
        svc_label.grid(column=0, row=svc_idx + svcs_grid_start)
        svc_proc_status = ttk.Label(frm, text="-", padding=10)
        svc_proc_status.grid(column=1, row=svc_idx + svcs_grid_start)
        svcs["svcs_ui"][svc_name] = svc_proc_status
        col_idx = 2
        endpoints = svcs["config"][svc_idx]["endpoints"]
        max_endpoints = max(max_endpoints, len(endpoints))
        
        for ep_key in endpoints.keys():
            ep_name = ep_key
            ep_suffix = endpoints[ep_key]
            svc_endpoint = ttk.Label(frm, text=ep_name)
            svc_endpoint.grid(column=1+col_idx*2, row=svc_idx + svcs_grid_start)
            svc_endpoint_status = ttk.Label(frm, text="-")
            svc_endpoint_status.grid(column=1+col_idx*2+1, row=svc_idx + svcs_grid_start)
            endpoints[ep_key]["response_ui"] = svc_endpoint_status
            col_idx += 1
        # labels.append(svc_label)

    ttk.Button(frm, text="Start all", command=lambda: start_all_svcs(
        svcs)).grid(column=0, row=0)
    root.rowconfigure(svcs_count + 1, weight=5)

    last_update_ui = ttk.Label(frm, text="Last update: -", padding=10)
    last_update_ui.grid(column=1, row=0)
    svcs["last_update_ui"] = last_update_ui
    # frm_bottom = ttk.Frame(root)
    # frm_bottom.pack(fill="x", side="bottom")
    # frm_bottom.grid(row=1)
    # #frm_bottom.pack(fill="x", side="bottom")
    # frm_bottom.columnconfigure(svc_idx+1, weight=1)
    ttk.Button(frm, text="Quit", command=lambda: quit_app(root, svcs)).grid(
        column=max_endpoints + 1, row=svcs_count + svcs_grid_start + 1,  sticky="nsew")
    root.rowconfigure(svcs_count + 1, weight=5)
    # l1 = tkinter.Label(text="Test", fg="black", bg="white")
    # l2 = tkinter.Label(text="Test", fg="black", bg="white")

    ui_tick(svcs)
    x = threading.Thread(target=background_update, args=(svcs,))
    x.start()
    root.mainloop()
    quit_app(root, svcs)
    x.join()

if __name__ == "__main__":
    main()
