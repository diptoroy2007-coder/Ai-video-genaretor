import json
import os
import requests
import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, concatenate_videoclips
import traceback

# API Configuration
# প্রথমে এনভায়রনমেন্ট ভেরিয়েবল চেক করবে, না থাকলে হার্ডকোড করা কি ব্যবহার করবে
API_KEY = os.getenv("API_KEY")
if not API_KEY or API_KEY == "":
    API_KEY = "01828567716"  # আপনার ব্যাকআপ কি

API_URL = "https://simple-ai-image-genaretor.deptoroy91.workers.dev/"

# ডিবাগিং: API কি এর প্রথম ৩টি অক্ষর প্রিন্ট করবে নিশ্চিত হওয়ার জন্য (পুরোটা নয় নিরাপত্তার জন্য)
print(f"DEBUG: Using API Key starting with: {API_KEY[:3]}... (Total length: {len(API_KEY)})")

DIMENSIONS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}

def generate_image(prompt, size_ratio, scene_n):
    print(f"Generating Scene {scene_n}...")
    
    # হেডারটি আবার চেক করুন। কিছু সার্ভারে 'X-API-KEY' বড় হাতের হতে হয়।
    headers = {
        "Content-Type": "application/json",
        "x-api-key": str(API_KEY).strip() 
    }
    
    payload = {
        "prompt": prompt,
        "size": size_ratio,
        "model": "@cf/black-forest-labs/flux-1-schnell"
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            path = f"scene_{scene_n}.jpg"
            with open(path, "wb") as f:
                f.write(response.content)
            print(f"Success: Saved scene_{scene_n}.jpg")
            return path
        else:
            print(f"API Failed (Status {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

# ... বাকি apply_motion এবং build_video ফাংশন আগের মতোই থাকবে ...
# (নিশ্চিত করুন আগের কোড থেকে apply_motion এবং build_video অংশটুকু নিচে আছে)

def apply_motion(clip, motion_type, size):
    w, h = size
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        p = t / clip.duration
        s = 1.2 
        if motion_type == "zoom-in": s = 1.0 + (0.2 * p)
        elif motion_type == "zoom-out": s = 1.2 - (0.2 * p)
        nw, nh = int(w * s), int(h * s)
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        ox, oy = (nw - w) / 2, (nh - h) / 2
        if motion_type == "pan-right": ox = (nw - w) * p
        elif motion_type == "pan-left": ox = (nw - w) * (1 - p)
        elif motion_type == "pan-down": oy = (nh - h) * p
        elif motion_type == "pan-up": oy = (nh - h) * (1 - p)
        return np.array(img.crop((ox, oy, ox + w, oy + h)).resize((w, h)))
    return clip.fl(effect)

def build_video():
    try:
        json_str = os.getenv("JSON_INPUT")
        if not json_str:
            print("ERROR: JSON_INPUT is empty.")
            return
        data = json.loads(json_str)
        ratio = data["global_settings"].get("ratio", "16:9")
        W, H = DIMENSIONS.get(ratio, (1920, 1080))
        clips = []
        for scene in data["scenes"]:
            img_path = generate_image(scene["bg_prompt"], ratio, scene["scene_n"])
            if img_path:
                c = ImageClip(img_path).set_duration(scene.get("duration", 5))
                c = apply_motion(c, scene.get("motion", "none"), (W, H))
                if scene.get("transition") == "crossfade": c = c.crossfadein(1.0)
                clips.append(c)
        if clips:
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile("final_video.mp4", fps=24, codec="libx264", audio=False, preset="ultrafast", threads=2)
            print("Video generated successfully!")
    except Exception as e:
        print(traceback.format_exc())

if __name__ == "__main__":
    build_video()
