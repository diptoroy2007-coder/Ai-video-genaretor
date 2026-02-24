import json
import os
import requests
import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, CompositeVideoClip, concatenate_videoclips, vfx

# API Configuration
API_URL = "https://simple-ai-image-genaretor.deptoroy91.workers.dev/"
API_KEY = os.getenv("API_KEY", "01828567716")

DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920)
}

def generate_image(prompt, size_ratio, scene_n):
    print(f"Generating Image for Scene {scene_n}...")
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    payload = {
        "prompt": prompt,
        "size": size_ratio,
        "model": "@cf/black-forest-labs/flux-1-schnell"
    }
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            img_path = f"scene_{scene_n}.jpg"
            with open(img_path, "wb") as f:
                f.write(response.content)
            return img_path
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def apply_motion(clip, motion_type, size):
    w, h = size
    # ইমেজকে ২০% বড় করা হয় যাতে প্যানিং করার সময় কালো বর্ডার না দেখা যায়
    base_scale = 1.2 
    
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        progress = t / clip.duration
        
        # ডিফল্ট স্কেল
        current_scale = base_scale
        
        if motion_type == "zoom-in":
            current_scale = 1.0 + (0.3 * progress) # ১.০ থেকে ১.৩ জুম
        elif motion_type == "zoom-out":
            current_scale = 1.3 - (0.3 * progress) # ১.৩ থেকে ১.০ জুম

        # ইমেজ রিসাইজ
        new_w, new_h = int(w * current_scale), int(h * current_scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # পজিশন ক্যালকুলেশন (প্যানিং)
        # সেন্টারিং
        curr_w, curr_h = img.size
        x_center = (curr_w - w) / 2
        y_center = (curr_h - h) / 2
        
        x_offset, y_offset = x_center, y_center

        if motion_type == "pan-right": # বাম থেকে ডানে মুভ (ক্যামেরা ডানে যাবে)
            x_offset = (curr_w - w) * progress
        elif motion_type == "pan-left":
            x_offset = (curr_w - w) * (1 - progress)
        elif motion_type == "pan-down": # ওপর থেকে নিচে মুভ
            y_offset = (curr_h - h) * progress
        elif motion_type == "pan-up":
            y_offset = (curr_h - h) * (1 - progress)
        elif motion_type == "ken-burns": # জুম + প্যান একসাথে
            current_scale = 1.0 + (0.2 * progress)
            img = img.resize((int(w*current_scale), int(h*current_scale)), Image.Resampling.LANCZOS)
            x_offset = (img.size[0] - w) * progress
            y_offset = (img.size[1] - h) * progress

        # ফাইনাল ক্রপ
        img = img.crop((x_offset, y_offset, x_offset + w, y_offset + h))
        return np.array(img.resize((w, h))) # নিশ্চিত করার জন্য আবার রিসাইজ

    return clip.fl(effect)

def build_video():
    # GitHub Action input থেকে ডাটা নেয়া
    json_str = os.getenv("JSON_INPUT")
    if not json_str:
        print("No JSON input found!")
        return
    
    data = json.loads(json_str)
    target_ratio = data["global_settings"].get("ratio", "16:9")
    W, H = DIMENSIONS.get(target_ratio, (1920, 1080))

    clips = []
    
    for idx, scene in enumerate(data["scenes"]):
        img_path = generate_image(scene["bg_prompt"], target_ratio, scene["scene_n"])
        
        if img_path:
            # ইমেজ ক্লিপ তৈরি
            duration = scene.get("duration", 5)
            clip = ImageClip(img_path).set_duration(duration)
            
            # মোশন অ্যাপ্লাই করা
            motion = scene.get("motion", "none")
            clip = apply_motion(clip, motion, (W, H))
            
            # ট্রানজিশন লজিক
            trans = scene.get("transition", "none")
            if trans == "crossfade":
                clip = clip.crossfadein(1.0)
            elif trans == "fade_to_black":
                clip = clip.fadein(1.0).fadeout(1.0)
            # 'none' হলে কিছুই করার দরকার নেই, সরাসরি যোগ হবে
            
            clips.append(clip)

    if not clips:
        print("No clips to render.")
        return

    print("Rendering Final Video...")
    # method="compose" ট্রানজিশনগুলোকে ওভারল্যাপ করতে সাহায্য করে
    # padding=-1 দিলে ১ সেকেন্ডের ওভারল্যাপ হয় crossfade এর জন্য
    final_video = concatenate_videoclips(clips, method="compose", padding=-1 if any(s.get("transition") == "crossfade" for s in data["scenes"]) else 0)
    
    final_video.write_videofile(
        "final_video.mp4", 
        fps=24, 
        codec="libx264", 
        audio=False, 
        preset="medium"
    )
    print("Video Generation Successful!")

if __name__ == "__main__":
    build_video()
