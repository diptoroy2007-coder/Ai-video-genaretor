import json
import os
import requests
import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, concatenate_videoclips
import traceback

API_URL = "https://simple-ai-image-genaretor.deptoroy91.workers.dev/"
API_KEY = os.getenv("API_KEY", "01828567716")

DIMENSIONS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}

def generate_image(prompt, size_ratio, scene_n):
    print(f"Generating Scene {scene_n}...")
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    payload = {"prompt": prompt, "size": size_ratio, "model": "@cf/black-forest-labs/flux-1-schnell"}
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            path = f"scene_{scene_n}.jpg"
            with open(path, "wb") as f: 
                f.write(response.content)
            if os.path.getsize(path) > 0:
                print(f"Successfully saved {path}")
                return path
        else:
            print(f"API Failed for Scene {scene_n}: {response.status_code}")
    except Exception as e:
        print(f"Request error: {e}")
    return None

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
            print("ERROR: JSON_INPUT environment variable is empty.")
            return
            
        data = json.loads(json_str)
        ratio = data["global_settings"].get("ratio", "16:9")
        W, H = DIMENSIONS.get(ratio, (1920, 1080))
        
        clips = []
        for scene in data["scenes"]:
            img_path = generate_image(scene["bg_prompt"], ratio, scene["scene_n"])
            if img_path:
                # মেমরি বাঁচাতে ইমেজকে ছোট করে লোড করা হচ্ছে যদি প্রয়োজন হয়
                c = ImageClip(img_path).set_duration(scene.get("duration", 5))
                c = apply_motion(c, scene.get("motion", "none"), (W, H))
                
                trans = scene.get("transition", "none")
                if trans == "crossfade":
                    c = c.crossfadein(1.0)
                elif trans == "fade_to_black":
                    c = c.fadein(0.5).fadeout(0.5)
                
                clips.append(c)
        
        if not clips:
            print("ERROR: No clips were generated successfully.")
            return

        print(f"Total clips to render: {len(clips)}")
        print("Starting concatenation...")
        
        # padding=0 রাখা নিরাপদ, crossfadeিন অটো কাজ করবে compose মেথডে
        final = concatenate_videoclips(clips, method="compose")
        
        print("Rendering final video file (this may take a while)...")
        final.write_videofile(
            "final_video.mp4", 
            fps=24, 
            codec="libx264", 
            audio=False, 
            preset="ultrafast", # দ্রুত রেন্ডারের জন্য
            threads=2           # র‍্যাম বাঁচাতে থ্রেড লিমিট করা হলো
        )
        print("SUCCESS: final_video.mp4 generated.")

    except Exception as e:
        print("\n--- CRITICAL ERROR ---")
        print(traceback.format_exc())

if __name__ == "__main__":
    build_video()
