import json
import os
import requests
import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, concatenate_videoclips

API_URL = "https://simple-ai-image-genaretor.deptoroy91.workers.dev/"
API_KEY = os.getenv("API_KEY", "01828567716")

DIMENSIONS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}

def generate_image(prompt, size_ratio, scene_n):
    print(f"Generating Scene {scene_n}...")
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    payload = {"prompt": prompt, "size": size_ratio, "model": "@cf/black-forest-labs/flux-1-schnell"}
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            path = f"scene_{scene_n}.jpg"
            with open(path, "wb") as f: f.write(response.content)
            return path
    except: return None
    return None

def apply_motion(clip, motion_type, size):
    w, h = size
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        p = t / clip.duration
        s = 1.2 # Base scale
        if motion_type == "zoom-in": s = 1.0 + (0.3 * p)
        elif motion_type == "zoom-out": s = 1.3 - (0.3 * p)
        
        nw, nh = int(w * s), int(h * s)
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        ox, oy = (nw - w) / 2, (nh - h) / 2 # Center
        if motion_type == "pan-right": ox = (nw - w) * p
        elif motion_type == "pan-left": ox = (nw - w) * (1 - p)
        elif motion_type == "pan-down": oy = (nh - h) * p
        elif motion_type == "pan-up": oy = (nh - h) * (1 - p)
        
        return np.array(img.crop((ox, oy, ox + w, oy + h)).resize((w, h)))
    return clip.fl(effect)

def build_video():
    json_str = os.getenv("JSON_INPUT")
    if not json_str: return
    data = json.loads(json_str)
    ratio = data["global_settings"].get("ratio", "16:9")
    W, H = DIMENSIONS.get(ratio, (1920, 1080))
    
    clips = []
    for idx, scene in enumerate(data["scenes"]):
        img = generate_image(scene["bg_prompt"], ratio, scene["scene_n"])
        if img:
            c = ImageClip(img).set_duration(scene.get("duration", 5))
            c = apply_motion(c, scene.get("motion", "none"), (W, H))
            trans = scene.get("transition", "none")
            if trans == "crossfade": c = c.crossfadein(1.0)
            elif trans == "fade_to_black": c = c.fadein(1.0).fadeout(1.0)
            clips.append(c)

    if clips:
        # Crossfade থাকলে padding ব্যবহার করে ওভারল্যাপ করা হয়
        final = concatenate_videoclips(clips, method="compose", padding=-1 if any(s.get("transition") == "crossfade" for s in data["scenes"]) else 0)
        final.write_videofile("final_video.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast")

if __name__ == "__main__":
    build_video()
